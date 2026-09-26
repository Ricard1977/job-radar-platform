-- Learning V1: current human signals, without changing AI scoring.

create unique index if not exists learning_signals_current_unique
on public.learning_signals(user_id, job_id, signal_type)
where job_id is not null;

create or replace function public.record_learning_signal(
  p_job_id bigint,
  p_signal_type text,
  p_reason text default null
) returns void
language plpgsql
security definer
set search_path=public
as $$
declare
  v_user uuid := auth.uid();
  v_title text;
  v_company text;
  v_location text;
  v_workplace text;
  v_salary text;
  v_description text;
  v_source text;
  v_ai_decision text;
  v_ai_score numeric;
  v_ai_id bigint;
  v_weight numeric(4,2);
begin
  if v_user is null then raise exception 'Authentication required'; end if;
  if p_signal_type not in ('INTERESTED','APPLIED','REJECTED') then raise exception 'Invalid signal type'; end if;

  select j.title,c.name,j.location,j.workplace_type,j.salary_text,j.description
  into v_title,v_company,v_location,v_workplace,v_salary,v_description
  from public.jobs j left join public.companies c on c.id=j.company_id
  where j.id=p_job_id;
  if not found then raise exception 'Job not found'; end if;

  select s.name into v_source
  from public.job_sources js join public.sources s on s.id=js.source_id
  where js.job_id=p_job_id order by js.id limit 1;

  select id,decision,score into v_ai_id,v_ai_decision,v_ai_score
  from public.ai_evaluations where job_id=p_job_id
  order by evaluated_at desc limit 1;

  v_weight := case p_signal_type when 'INTERESTED' then 1 when 'APPLIED' then 2 else -1 end;

  insert into public.learning_signals(
    user_id,job_id,signal_type,signal_weight,reason,ai_decision,ai_score,ai_evaluation_id,
    job_title,company_name,location,workplace_type,salary_text,source_name,job_features,ai_snapshot
  ) values (
    v_user,p_job_id,p_signal_type,v_weight,nullif(trim(p_reason),''),v_ai_decision,v_ai_score,v_ai_id,
    v_title,v_company,v_location,v_workplace,v_salary,v_source,
    jsonb_build_object('description',v_description),
    jsonb_build_object('decision',v_ai_decision,'score',v_ai_score,'evaluation_id',v_ai_id)
  )
  on conflict (user_id,job_id,signal_type) where job_id is not null
  do update set
    signal_weight=excluded.signal_weight,reason=excluded.reason,ai_decision=excluded.ai_decision,
    ai_score=excluded.ai_score,ai_evaluation_id=excluded.ai_evaluation_id,job_title=excluded.job_title,
    company_name=excluded.company_name,location=excluded.location,workplace_type=excluded.workplace_type,
    salary_text=excluded.salary_text,source_name=excluded.source_name,job_features=excluded.job_features,
    ai_snapshot=excluded.ai_snapshot,created_at=now();
end;
$$;

revoke all on function public.record_learning_signal(bigint,text,text) from public;
grant execute on function public.record_learning_signal(bigint,text,text) to authenticated;
