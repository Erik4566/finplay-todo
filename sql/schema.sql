-- =============================================================================
--  FinPlay ToDo - Supabase schema
--  Spusti celý súbor v Supabase -> SQL Editor -> New query -> Run.
--  Je idempotentný: dá sa spustiť opakovane.
-- =============================================================================

create extension if not exists "pgcrypto";

-- -----------------------------------------------------------------------------
-- 1. Profily používateľov (1:1 s auth.users)
-- -----------------------------------------------------------------------------
create table if not exists public.profiles (
    id           uuid primary key references auth.users (id) on delete cascade,
    email        text not null,
    full_name    text,
    timezone     text default 'Europe/Bratislava',
    avatar_emoji text default '🙂',
    created_at   timestamptz not null default now()
);

-- Profil sa vytvorí automaticky po registrácii
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = public
as $fn$
begin
    insert into public.profiles (id, email, full_name)
    values (new.id, new.email, coalesce(new.raw_user_meta_data ->> 'full_name', new.email))
    on conflict (id) do nothing;
    return new;
end;
$fn$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
    after insert on auth.users
    for each row execute function public.handle_new_user();

-- -----------------------------------------------------------------------------
-- 2. Projekty a členovia
-- -----------------------------------------------------------------------------
create table if not exists public.projects (
    id          uuid primary key default gen_random_uuid(),
    owner_id    uuid not null references public.profiles (id) on delete cascade,
    name        text not null,
    description text,
    color       text default '#4F46E5',
    emoji       text default '📁',
    status      text not null default 'active',      -- active | paused | done
    archived_at timestamptz,
    created_at  timestamptz not null default now(),
    updated_at  timestamptz not null default now()
);

create table if not exists public.project_members (
    project_id uuid not null references public.projects (id) on delete cascade,
    user_id    uuid not null references public.profiles (id) on delete cascade,
    role       text not null default 'member',       -- owner | member | viewer
    created_at timestamptz not null default now(),
    primary key (project_id, user_id)
);

-- SECURITY DEFINER helper - zabraňuje rekurzii v RLS politikách
create or replace function public.is_project_member(p_project uuid, p_user uuid)
returns boolean
language sql
security definer set search_path = public
stable
as $fn$
    select exists (
        select 1 from public.project_members m
        where m.project_id = p_project and m.user_id = p_user
    ) or exists (
        select 1 from public.projects p
        where p.id = p_project and p.owner_id = p_user
    );
$fn$;

-- -----------------------------------------------------------------------------
-- 3. Úlohy
-- -----------------------------------------------------------------------------
create table if not exists public.tasks (
    id                uuid primary key default gen_random_uuid(),
    project_id        uuid references public.projects (id) on delete set null,
    owner_id          uuid not null references public.profiles (id) on delete cascade,

    title             text not null,
    description       text,

    -- Eisenhower: dôležitosť + urgentnosť (1-5)
    importance        int  not null default 3 check (importance between 1 and 5),
    urgency           int  not null default 3 check (urgency between 1 and 5),
    priority_label    text,

    status            text not null default 'todo',   -- inbox|todo|in_progress|blocked|done
    energy_level      text default 'medium',          -- low|medium|high
    context_tag       text,                           -- @počítač, @telefón, @vonku

    estimated_minutes int  default 30,
    due_at            timestamptz,
    start_at          timestamptz,
    completed_at      timestamptz,
    archived_at       timestamptz,

    -- opakovanie
    recurrence_rule   text,                           -- FREQ=WEEKLY;INTERVAL=1;BYDAY=MO,WE
    recurrence_parent uuid references public.tasks (id) on delete set null,

    -- externá synchronizácia
    google_event_id   text,
    ms_todo_task_id   text,

    position          int default 0,
    created_at        timestamptz not null default now(),
    updated_at        timestamptz not null default now()
);

create index if not exists tasks_project_idx on public.tasks (project_id);
create index if not exists tasks_owner_idx   on public.tasks (owner_id);
create index if not exists tasks_status_idx  on public.tasks (status);
create index if not exists tasks_due_idx     on public.tasks (due_at);
create index if not exists tasks_fts_idx     on public.tasks
    using gin (to_tsvector('simple', coalesce(title, '') || ' ' || coalesce(description, '')));

-- -----------------------------------------------------------------------------
-- 4. Kroky (povinný rozklad úlohy)
-- -----------------------------------------------------------------------------
create table if not exists public.task_steps (
    id                uuid primary key default gen_random_uuid(),
    task_id           uuid not null references public.tasks (id) on delete cascade,
    position          int  not null default 0,
    title             text not null,
    estimated_minutes int  default 10,
    is_done           boolean not null default false,
    done_at           timestamptz,
    created_at        timestamptz not null default now()
);
create index if not exists task_steps_task_idx on public.task_steps (task_id, position);

-- -----------------------------------------------------------------------------
-- 5. Priradenie osobám
-- -----------------------------------------------------------------------------
create table if not exists public.task_assignees (
    id         uuid primary key default gen_random_uuid(),
    task_id    uuid not null references public.tasks (id) on delete cascade,
    user_id    uuid references public.profiles (id) on delete cascade,
    email      text,                                 -- externá osoba bez účtu
    role       text default 'responsible',           -- responsible | accountable | informed
    created_at timestamptz not null default now()
);
create index if not exists task_assignees_task_idx on public.task_assignees (task_id);

-- -----------------------------------------------------------------------------
-- 6. Riziká a výzvy
-- -----------------------------------------------------------------------------
create table if not exists public.task_risks (
    id           uuid primary key default gen_random_uuid(),
    task_id      uuid not null references public.tasks (id) on delete cascade,
    kind         text not null default 'risk',       -- risk | challenge
    title        text not null,
    description  text,
    severity     int default 3 check (severity between 1 and 5),
    likelihood   int default 3 check (likelihood between 1 and 5),
    mitigation   text,
    source       text default 'human',               -- human | ai
    source_model text,
    created_by   uuid references public.profiles (id) on delete set null,
    created_at   timestamptz not null default now()
);
create index if not exists task_risks_task_idx on public.task_risks (task_id);

-- -----------------------------------------------------------------------------
-- 7. Spätná väzba od AI modelov
-- -----------------------------------------------------------------------------
create table if not exists public.ai_feedback (
    id         uuid primary key default gen_random_uuid(),
    task_id    uuid not null references public.tasks (id) on delete cascade,
    provider   text not null,                        -- anthropic | gemini | openai | mock
    model      text,
    kind       text not null default 'analysis',     -- analysis | steps | review
    summary    text,
    payload    jsonb,
    raw_text   text,
    latency_ms int,
    error      text,
    created_by uuid references public.profiles (id) on delete set null,
    created_at timestamptz not null default now()
);
create index if not exists ai_feedback_task_idx on public.ai_feedback (task_id, created_at desc);

-- -----------------------------------------------------------------------------
-- 8. Sledovanie času
-- -----------------------------------------------------------------------------
create table if not exists public.time_entries (
    id               uuid primary key default gen_random_uuid(),
    task_id          uuid not null references public.tasks (id) on delete cascade,
    user_id          uuid not null references public.profiles (id) on delete cascade,
    step_id          uuid references public.task_steps (id) on delete set null,
    started_at       timestamptz not null default now(),
    ended_at         timestamptz,
    duration_seconds int,
    note             text,
    created_at       timestamptz not null default now()
);
create index if not exists time_entries_task_idx on public.time_entries (task_id);
create index if not exists time_entries_open_idx on public.time_entries (user_id) where ended_at is null;

-- -----------------------------------------------------------------------------
-- 9. Upozornenia
-- -----------------------------------------------------------------------------
create table if not exists public.reminders (
    id           uuid primary key default gen_random_uuid(),
    task_id      uuid not null references public.tasks (id) on delete cascade,
    user_id      uuid not null references public.profiles (id) on delete cascade,
    remind_at    timestamptz not null,
    channel      text not null default 'app',        -- app | email
    message      text,
    sent_at      timestamptz,
    dismissed_at timestamptz,
    created_at   timestamptz not null default now()
);
create index if not exists reminders_due_idx on public.reminders (user_id, remind_at) where sent_at is null;

-- -----------------------------------------------------------------------------
-- 10. Zdieľanie e-mailom
-- -----------------------------------------------------------------------------
create table if not exists public.task_shares (
    id              uuid primary key default gen_random_uuid(),
    task_id         uuid not null references public.tasks (id) on delete cascade,
    shared_by       uuid references public.profiles (id) on delete set null,
    recipient_email text not null,
    message         text,
    status          text default 'pending',           -- pending | sent | failed
    error           text,
    sent_at         timestamptz,
    created_at      timestamptz not null default now()
);

-- -----------------------------------------------------------------------------
-- 11. Napojené účty (Google / Microsoft) a log synchronizácie
-- -----------------------------------------------------------------------------
create table if not exists public.integration_accounts (
    id            uuid primary key default gen_random_uuid(),
    user_id       uuid not null references public.profiles (id) on delete cascade,
    provider      text not null,                      -- google | microsoft
    account_email text,
    access_token  text,
    refresh_token text,
    expires_at    timestamptz,
    scope         text,
    extra         jsonb,
    created_at    timestamptz not null default now(),
    updated_at    timestamptz not null default now(),
    unique (user_id, provider)
);

create table if not exists public.sync_log (
    id          uuid primary key default gen_random_uuid(),
    user_id     uuid references public.profiles (id) on delete cascade,
    task_id     uuid references public.tasks (id) on delete cascade,
    provider    text not null,
    direction   text default 'push',                  -- push | pull
    external_id text,
    status      text default 'ok',                    -- ok | error | mock
    message     text,
    created_at  timestamptz not null default now()
);

-- -----------------------------------------------------------------------------
-- 12. Spätná väzba k aplikácii (nie k úlohám)
-- -----------------------------------------------------------------------------
create table if not exists public.feedback (
    id          uuid primary key default gen_random_uuid(),
    user_id     uuid not null references public.profiles (id) on delete cascade,
    kind        text not null default 'friction',   -- bug | idea | friction | question
    message     text not null,
    page        text,                               -- obrazovka, na ktorej to vzniklo
    blocking    boolean not null default false,
    images      jsonb,                              -- názvy súborov v data/feedback/
    context     jsonb,                              -- verzia, téma, krajina, backend
    status      text not null default 'new',        -- new | in_progress | done
    created_at  timestamptz not null default now(),
    resolved_at timestamptz
);
create index if not exists feedback_user_idx on public.feedback (user_id, created_at desc);

-- =============================================================================
--  Row Level Security
-- =============================================================================
alter table public.profiles             enable row level security;
alter table public.projects             enable row level security;
alter table public.project_members      enable row level security;
alter table public.tasks                enable row level security;
alter table public.task_steps           enable row level security;
alter table public.task_assignees       enable row level security;
alter table public.task_risks           enable row level security;
alter table public.ai_feedback          enable row level security;
alter table public.time_entries         enable row level security;
alter table public.reminders            enable row level security;
alter table public.task_shares          enable row level security;
alter table public.integration_accounts enable row level security;
alter table public.sync_log             enable row level security;

-- Profily: prihlásený vidí profily (kvôli priraďovaniu), mení len svoj
drop policy if exists profiles_select on public.profiles;
create policy profiles_select on public.profiles for select using (auth.uid() is not null);
drop policy if exists profiles_update on public.profiles;
create policy profiles_update on public.profiles for update using (id = auth.uid());
drop policy if exists profiles_insert on public.profiles;
create policy profiles_insert on public.profiles for insert with check (id = auth.uid());

-- Projekty
drop policy if exists projects_all on public.projects;
create policy projects_all on public.projects for all
    using (owner_id = auth.uid() or public.is_project_member(id, auth.uid()))
    with check (owner_id = auth.uid() or public.is_project_member(id, auth.uid()));

drop policy if exists project_members_all on public.project_members;
create policy project_members_all on public.project_members for all
    using (user_id = auth.uid() or public.is_project_member(project_id, auth.uid()))
    with check (public.is_project_member(project_id, auth.uid()));

-- Úlohy: vlastník, člen projektu alebo priradená osoba
create or replace function public.can_access_task(p_task uuid, p_user uuid)
returns boolean
language sql
security definer set search_path = public
stable
as $fn$
    select exists (
        select 1 from public.tasks t
        where t.id = p_task
          and ( t.owner_id = p_user
                or (t.project_id is not null and public.is_project_member(t.project_id, p_user))
                or exists (select 1 from public.task_assignees a
                           where a.task_id = t.id and a.user_id = p_user) )
    );
$fn$;

drop policy if exists tasks_all on public.tasks;
create policy tasks_all on public.tasks for all
    using (
        owner_id = auth.uid()
        or (project_id is not null and public.is_project_member(project_id, auth.uid()))
        or exists (select 1 from public.task_assignees a
                   where a.task_id = tasks.id and a.user_id = auth.uid())
    )
    with check (
        owner_id = auth.uid()
        or (project_id is not null and public.is_project_member(project_id, auth.uid()))
    );

-- Podriadené tabuľky dedia prístup od úlohy
do $blk$
declare tbl text;
begin
    foreach tbl in array array['task_steps', 'task_assignees', 'task_risks',
                               'ai_feedback', 'time_entries', 'reminders', 'task_shares']
    loop
        execute format('drop policy if exists %I_all on public.%I', tbl, tbl);
        execute format(
            'create policy %I_all on public.%I for all
                 using (public.can_access_task(task_id, auth.uid()))
                 with check (public.can_access_task(task_id, auth.uid()))', tbl, tbl);
    end loop;
end $blk$;

-- Napojené účty a log - striktne osobné
drop policy if exists integration_accounts_all on public.integration_accounts;
create policy integration_accounts_all on public.integration_accounts for all
    using (user_id = auth.uid()) with check (user_id = auth.uid());

drop policy if exists feedback_all on public.feedback;
create policy feedback_all on public.feedback for all
    using (user_id = auth.uid()) with check (user_id = auth.uid());

drop policy if exists sync_log_all on public.sync_log;
create policy sync_log_all on public.sync_log for all
    using (user_id = auth.uid()) with check (user_id = auth.uid());
