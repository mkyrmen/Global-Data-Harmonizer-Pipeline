BEGIN;
-- Global Data Harmonizer: core schema
-- RLS is enabled on every table; each owner only sees their own rows.

-- shared helper for updated_at
create or replace function public.set_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

-- profiles mirror auth.users
create table public.profiles (
  id          uuid primary key references auth.users (id) on delete cascade,
  display_name text,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

create trigger trg_profiles_updated_at
  before update on public.profiles
  for each row execute procedure public.set_updated_at();

-- automatic profile on signup
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = public
as $$
begin
  insert into public.profiles (id, display_name)
  values (new.id, coalesce(new.raw_user_meta_data ->> 'full_name', split_part(new.email, '@', 1)))
  on conflict (id) do nothing;
  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure public.handle_new_user();

-- a workspace groups source datasets and harmonization jobs
create table public.workspaces (
  id          uuid primary key default gen_random_uuid(),
  owner_id    uuid not null references auth.users (id) on delete cascade,
  name        text not null,
  description text,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

create trigger trg_workspaces_updated_at
  before update on public.workspaces
  for each row execute procedure public.set_updated_at();

-- uploaded raw source files (pairs with Storage bucket 'uploads')
create table public.raw_sources (
  id            uuid primary key default gen_random_uuid(),
  owner_id      uuid not null references auth.users (id) on delete cascade,
  workspace_id  uuid references public.workspaces (id) on delete set null,
  name          text not null,
  storage_path  text not null,
  row_count     int not null default 0,
  column_names  text[] not null default '{}',
  preview_json  jsonb not null default '[]',
  created_at    timestamptz not null default now()
);

create index idx_raw_sources_owner on public.raw_sources (owner_id);
create index idx_raw_sources_workspace on public.raw_sources (workspace_id);

-- which sources are included in the harmonization workspace (review + toggle + run)
create table public.workspace_sources (
  workspace_id  uuid not null references public.workspaces (id) on delete cascade,
  source_id     uuid not null references public.raw_sources (id) on delete cascade,
  include       boolean not null default true,
  sort_order    int not null default 0,
  primary key (workspace_id, source_id)
);

-- a pipeline execution: snapshot of config + source selection
create table public.harmonization_jobs (
  id              uuid primary key default gen_random_uuid(),
  owner_id        uuid not null references auth.users (id) on delete cascade,
  workspace_id    uuid references public.workspaces (id) on delete set null,
  name            text not null,
  config_json     jsonb not null default '{}',
  status          text not null default 'queued'
                    check (status in ('queued', 'running', 'succeeded', 'failed')),
  error_message   text,
  created_at      timestamptz not null default now(),
  started_at      timestamptz,
  completed_at    timestamptz
);

create index idx_jobs_owner on public.harmonization_jobs (owner_id);
create index idx_jobs_status on public.harmonization_jobs (status);

create table public.job_sources (
  job_id     uuid not null references public.harmonization_jobs (id) on delete cascade,
  source_id  uuid not null references public.raw_sources (id) on delete restrict,
  sort_order int not null default 0,
  primary key (job_id, source_id)
);

-- output of a successful job (canonical harmonized rows + metrics)
create table public.harmonized_datasets (
  id                 uuid primary key default gen_random_uuid(),
  job_id             uuid not null references public.harmonization_jobs (id) on delete cascade,
  owner_id           uuid not null references auth.users (id) on delete cascade,
  workspace_id       uuid references public.workspaces (id) on delete set null,
  row_count          int not null default 0,
  quality_before     float8,
  quality_after      float8,
  validation_status  text,
  data_json          jsonb not null default '[]',
  report_path        text,
  csv_path           text,
  created_at         timestamptz not null default now()
);

create index idx_datasets_owner on public.harmonized_datasets (owner_id);
create index idx_datasets_job on public.harmonized_datasets (job_id);

-- ----------------------------------------------------------------
-- Row Level Security
-- ----------------------------------------------------------------
alter table public.profiles            enable row level security;
alter table public.workspaces          enable row level security;
alter table public.raw_sources         enable row level security;
alter table public.workspace_sources   enable row level security;
alter table public.harmonization_jobs  enable row level security;
alter table public.job_sources         enable row level security;
alter table public.harmonized_datasets enable row level security;

create policy "profiles are readable by all authenticated users"
  on public.profiles for select to authenticated using (true);

create policy "users update their own profile"
  on public.profiles for update to authenticated
  using (auth.uid() = id) with check (auth.uid() = id);

create policy "owner selects own workspaces"
  on public.workspaces for select to authenticated
  using (auth.uid() = owner_id);

create policy "owner inserts own workspaces"
  on public.workspaces for insert to authenticated
  with check (auth.uid() = owner_id);

create policy "owner updates own workspaces"
  on public.workspaces for update to authenticated
  using (auth.uid() = owner_id);

create policy "owner deletes own workspaces"
  on public.workspaces for delete to authenticated
  using (auth.uid() = owner_id);

create policy "owner selects own sources"
  on public.raw_sources for select to authenticated
  using (auth.uid() = owner_id);

create policy "owner inserts own sources"
  on public.raw_sources for insert to authenticated
  with check (auth.uid() = owner_id);

create policy "owner updates own sources"
  on public.raw_sources for update to authenticated
  using (auth.uid() = owner_id);

create policy "owner deletes own sources"
  on public.raw_sources for delete to authenticated
  using (auth.uid() = owner_id);

create policy "shared workspace links"
  on public.workspace_sources for select to authenticated
  using (
    exists (
      select 1 from public.workspaces w
      where w.id = workspace_id and w.owner_id = auth.uid()
    )
  );

create policy "insert into workspaces you own"
  on public.workspace_sources for insert to authenticated
  with check (
    exists (
      select 1 from public.workspaces w
      where w.id = workspace_id and w.owner_id = auth.uid()
    )
  );

create policy "update workspace links you own"
  on public.workspace_sources for update to authenticated
  using (
    exists (
      select 1 from public.workspaces w
      where w.id = workspace_id and w.owner_id = auth.uid()
    )
  );

create policy "delete workspace links you own"
  on public.workspace_sources for delete to authenticated
  using (
    exists (
      select 1 from public.workspaces w
      where w.id = workspace_id and w.owner_id = auth.uid()
    )
  );

create policy "owner selects own jobs"
  on public.harmonization_jobs for select to authenticated
  using (auth.uid() = owner_id);

create policy "owner inserts own jobs"
  on public.harmonization_jobs for insert to authenticated
  with check (auth.uid() = owner_id);

create policy "owner updates own jobs"
  on public.harmonization_jobs for update to authenticated
  using (auth.uid() = owner_id);

create policy "owner deletes own jobs"
  on public.harmonization_jobs for delete to authenticated
  using (auth.uid() = owner_id);

create policy "job-source links visible to owner"
  on public.job_sources for select to authenticated
  using (
    exists (
      select 1 from public.harmonization_jobs j
      where j.id = job_id and j.owner_id = auth.uid()
    )
  );

create policy "job-source links insertable by owner"
  on public.job_sources for insert to authenticated
  with check (
    exists (
      select 1 from public.harmonization_jobs j
      where j.id = job_id and j.owner_id = auth.uid()
    )
  );

create policy "job-source links deletable by owner"
  on public.job_sources for delete to authenticated
  using (
    exists (
      select 1 from public.harmonization_jobs j
      where j.id = job_id and j.owner_id = auth.uid()
    )
  );

create policy "owner selects own datasets"
  on public.harmonized_datasets for select to authenticated
  using (auth.uid() = owner_id);

create policy "owner inserts own datasets"
  on public.harmonized_datasets for insert to authenticated
  with check (auth.uid() = owner_id);

create policy "owner updates own datasets"
  on public.harmonized_datasets for update to authenticated
  using (auth.uid() = owner_id);

create policy "owner deletes own datasets"
  on public.harmonized_datasets for delete to authenticated
  using (auth.uid() = owner_id);
-- Storage buckets + object-level access.
-- 'uploads'  : user uploads (dirty CSVs)
-- 'outputs'  : harmonized CSV / JSON report artifacts produced by jobs

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values
  ('uploads', 'uploads', false, 10485760, array['text/csv', 'application/vnd.ms-excel', 'application/json']),
  ('outputs', 'outputs', false, 10485760, array['text/csv', 'application/json', 'image/png'])
on conflict (id) do nothing;

create policy "users can read own uploads"
  on storage.objects for select to authenticated
  using (bucket_id = 'uploads' and owner = auth.uid());

create policy "users can upload to uploads"
  on storage.objects for insert to authenticated
  with check (bucket_id = 'uploads' and owner = auth.uid());

create policy "users can update own uploads"
  on storage.objects for update to authenticated
  using (bucket_id = 'uploads' and owner = auth.uid());

create policy "users can delete own uploads"
  on storage.objects for delete to authenticated
  using (bucket_id = 'uploads' and owner = auth.uid());

create policy "users can read own outputs"
  on storage.objects for select to authenticated
  using (bucket_id = 'outputs' and owner = auth.uid());

create policy "users can write own outputs"
  on storage.objects for insert to authenticated
  with check (bucket_id = 'outputs' and owner = auth.uid());

create policy "users can update own outputs"
  on storage.objects for update to authenticated
  using (bucket_id = 'outputs' and owner = auth.uid());

create policy "users can delete own outputs"
  on storage.objects for delete to authenticated
  using (bucket_id = 'outputs' and owner = auth.uid());
-- Seed helper: scaffolds a demo workspace for a user.
-- Designed to be called by the backend once the two demo CSV files have been
-- uploaded to Storage under `uploads/<uid>/...`.

create or replace function public.seed_demo_workspace(p_owner uuid, p_names text[])
returns uuid
language plpgsql
security definer set search_path = public
as $$
declare
  v_workspace uuid;
  v_source    uuid;
  v_name      text;
begin
  insert into public.workspaces (owner_id, name, description)
  values (p_owner, 'Demo Workspace', 'Harmonizes the two bundled demo sources.')
  returning id into v_workspace;

  foreach v_name in array p_names loop
    insert into public.raw_sources (owner_id, workspace_id, name, storage_path)
    values (p_owner, v_workspace, v_name, format('uploads/%s/%s', p_owner, v_name))
    returning id into v_source;

    insert into public.workspace_sources (workspace_id, source_id, include, sort_order)
    select v_workspace, id, true, row_number() over (order by created_at) - 1
    from public.raw_sources
    where workspace_id = v_workspace;
  end loop;

  return v_workspace;
end;
$$;

revoke all on function public.seed_demo_workspace(uuid, text[]) from public;
grant execute on function public.seed_demo_workspace(uuid, text[]) to service_role;
COMMIT;
