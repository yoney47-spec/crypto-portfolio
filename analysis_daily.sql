-- Bounded daily generation coordinated by the trusted Streamlit backend.
-- No Gemini credential is copied into the database or sent to the browser.
alter table public.ai_comments
  add column sections jsonb,
  add column model text,
  add column prices_updated_at timestamptz;

create table portfolio_internal.analysis_runs (
  date date primary key,
  status text not null check(status in ('processing','failed','ready')),
  attempts integer not null check(attempts between 1 and 3),
  token uuid not null,
  model text not null,
  started_at timestamptz not null,
  retry_at timestamptz not null,
  error_code text
);
alter table portfolio_internal.analysis_runs enable row level security;
create policy "Backend manages daily analysis" on portfolio_internal.analysis_runs
  for all to service_role using(true) with check(true);
revoke all on portfolio_internal.analysis_runs from public,anon,authenticated;
grant usage on schema portfolio_internal to service_role;
grant select,insert,update on portfolio_internal.analysis_runs to service_role;
grant select,insert,update on public.ai_comments to service_role;
do $$ begin
  execute format('grant usage on sequence %s to service_role',pg_get_serial_sequence('public.ai_comments','id'));
end $$;

grant select(sections,model,prices_updated_at) on public.ai_comments to portfolio_public_view_owner;
create or replace view public.public_ai_comments with (security_barrier=true) as
  select date,comment,created_at,sections,model,prices_updated_at from public.ai_comments;
-- Preserve the existing restricted NOLOGIN view owner and its SELECT-only RLS.

create function public.claim_daily_analysis(p_model text)
returns jsonb language plpgsql security invoker set search_path=pg_catalog as $$
declare day date:=(clock_timestamp() at time zone 'Asia/Tokyo')::date;
        current_run portfolio_internal.analysis_runs%rowtype;
        lease uuid:=gen_random_uuid(); stamp timestamptz:=clock_timestamp();
begin
  if p_model is null or p_model !~ '^gemini-[a-zA-Z0-9.-]+$' or length(p_model)>100 then
    raise exception 'Invalid model';
  end if;
  perform pg_advisory_xact_lock(hashtextextended('cryptofolio-daily-analysis',0));
  if exists(select 1 from public.ai_comments where date=day) then
    return jsonb_build_object('claimed',false,'status','ready');
  end if;
  select * into current_run from portfolio_internal.analysis_runs where date=day for update;
  if found then
    if current_run.status='processing' and stamp<current_run.retry_at then
      return jsonb_build_object('claimed',false,'status','processing','retry_at',current_run.retry_at);
    end if;
    if current_run.attempts>=3 then
      return jsonb_build_object('claimed',false,'status','daily_limit','error_code',current_run.error_code);
    end if;
    if stamp<current_run.retry_at then
      return jsonb_build_object('claimed',false,'status','waiting','error_code',current_run.error_code,
                                'retry_at',current_run.retry_at);
    end if;
  end if;
  insert into portfolio_internal.analysis_runs(date,status,attempts,token,model,started_at,retry_at)
    values(day,'processing',1,lease,p_model,stamp,stamp+interval '10 minutes')
  on conflict(date) do update set status='processing',attempts=analysis_runs.attempts+1,
    token=lease,model=p_model,started_at=stamp,retry_at=stamp+interval '10 minutes',error_code=null;
  return jsonb_build_object('claimed',true,'token',lease,'date',day);
end $$;

create function public.finish_daily_analysis(p_token uuid,p_sections jsonb,p_context jsonb,p_error text)
returns jsonb language plpgsql security invoker set search_path=pg_catalog as $$
declare current_run portfolio_internal.analysis_runs%rowtype;
        day date:=(clock_timestamp() at time zone 'Asia/Tokyo')::date;
        stamp timestamptz:=clock_timestamp(); observed timestamptz; body text; saved integer;
begin
  select * into current_run from portfolio_internal.analysis_runs where token=p_token for update;
  if not found or current_run.status<>'processing' then
    return jsonb_build_object('saved',false);
  end if;
  if p_error is not null then
    update portfolio_internal.analysis_runs set status='failed',retry_at=stamp+interval '15 minutes',
      error_code=case when p_error in ('missing_key','invalid_key','model_unavailable','request_rejected',
        'rate_limited','network_error','provider_error','invalid_response','storage_error','date_changed')
        then p_error else 'provider_error' end where token=p_token;
    return jsonb_build_object('saved',false,'retry_at',stamp+interval '15 minutes');
  end if;
  if current_run.date<>day or p_context->>'date' is distinct from day::text then
    update portfolio_internal.analysis_runs set status='failed',error_code='date_changed' where token=p_token;
    return jsonb_build_object('saved',false);
  end if;
  if jsonb_typeof(p_sections) is distinct from 'object' then raise exception 'Invalid sections'; end if;
  if (select count(*) from jsonb_object_keys(p_sections))<>3
    or exists(select 1 from unnest(array['overview','drivers','watch']) k
      where jsonb_typeof(p_sections->k) is distinct from 'string'
         or length(trim(p_sections->>k)) not between 10 and 600) then
    raise exception 'Invalid sections';
  end if;
  observed:=(p_context->>'prices_updated_at')::timestamptz;
  if observed is null or observed>stamp or stamp-observed>interval '20 minutes'
    or (observed at time zone 'Asia/Tokyo')::date<>day then
    raise exception 'Invalid observation time';
  end if;
  body:=(p_sections->>'overview')||E'\n\n'||(p_sections->>'drivers')||E'\n\n'||(p_sections->>'watch');
  insert into public.ai_comments(date,comment,portfolio_summary,created_at,sections,model,prices_updated_at)
    values(day,body,p_context,stamp,p_sections,current_run.model,observed)
    on conflict(date) do nothing;
  get diagnostics saved=row_count;
  update portfolio_internal.analysis_runs set status='ready',error_code=null where token=p_token;
  return jsonb_build_object('saved',saved=1);
end $$;

revoke all on function public.claim_daily_analysis(text) from public,anon,authenticated;
revoke all on function public.finish_daily_analysis(uuid,jsonb,jsonb,text) from public,anon,authenticated;
grant execute on function public.claim_daily_analysis(text) to service_role;
grant execute on function public.finish_daily_analysis(uuid,jsonb,jsonb,text) to service_role;
notify pgrst,'reload schema';
