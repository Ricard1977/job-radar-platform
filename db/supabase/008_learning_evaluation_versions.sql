-- Track which learning profile version has already evaluated each job.
-- Prevents repeated LLM decisions when no new learning exists.
create table if not exists public.learning_job_evaluations (
  job_id bigint not null references public.jobs(id) on delete cascade,
  profile_version bigint not null,
  action text not null check (action in ('MANTENER','ELIMINAR')),
  confidence numeric,
  pattern text,
  reason text,
  evaluated_at timestamptz not null default now(),
  primary key (job_id, profile_version)
);

alter table public.learning_job_evaluations enable row level security;
revoke all on public.learning_job_evaluations from public, anon, authenticated;
grant all on public.learning_job_evaluations to service_role;

create index if not exists learning_job_evaluations_profile_version_idx
  on public.learning_job_evaluations(profile_version);
