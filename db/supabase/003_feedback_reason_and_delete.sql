-- MVP: rejection reason + safe archive/delete flow
alter table public.user_job_feedback add column if not exists rejection_reason text;

-- Authenticated frontend operation: archive the vacancy in treated_jobs and remove it from jobs.
-- SECURITY DEFINER is needed because normal authenticated users must not receive generic DELETE rights on jobs.
create or replace function public.archive_and_delete_job(p_job_id bigint, p_reason text default null)
returns void
language plpgsql
security definer
set search_path = public
as $$
declare
  v_job public.jobs%rowtype;
  v_source_code text;
  v_external_job_id text;
  v_source_url text;
  v_company_name text;
  v_ai_score numeric;
  v_ai_decision text;
begin
  if auth.uid() is null then raise exception 'Authentication required'; end if;

  select * into v_job from public.jobs where id = p_job_id;
  if not found then raise exception 'Job not found'; end if;

  select s.code, js.external_job_id, js.source_url
    into v_source_code, v_external_job_id, v_source_url
  from public.job_sources js join public.sources s on s.id=js.source_id
  where js.job_id=p_job_id order by js.id limit 1;

  select name into v_company_name from public.companies where id=v_job.company_id;
  select score, decision into v_ai_score, v_ai_decision
  from public.ai_evaluations where job_id=p_job_id order by evaluated_at desc limit 1;

  if v_source_code is null or v_external_job_id is null then
    raise exception 'Job has no source identity';
  end if;

  insert into public.treated_jobs(original_public_id,source_code,external_job_id,source_url,company_name,job_title,decision,ai_score,ai_decision)
  values(v_job.public_id,v_source_code,v_external_job_id,v_source_url,v_company_name,v_job.title,coalesce(nullif(trim(p_reason),''),'NOT_INTERESTED'),v_ai_score,v_ai_decision)
  on conflict(source_code,external_job_id) do update set
    source_url=excluded.source_url, company_name=excluded.company_name, job_title=excluded.job_title,
    decision=excluded.decision, ai_score=excluded.ai_score, ai_decision=excluded.ai_decision, treated_at=now();

  delete from public.jobs where id=p_job_id;
end;
$$;

revoke all on function public.archive_and_delete_job(bigint,text) from public;
grant execute on function public.archive_and_delete_job(bigint,text) to authenticated;
