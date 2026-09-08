-- Run before the first new daily memo is generated. All test writes roll back.
begin;
set local role service_role;
do $$
declare first_lease jsonb; second_lease jsonb; result jsonb;
        day date:=(clock_timestamp() at time zone 'Asia/Tokyo')::date;
        sections jsonb:='{"overview":"確認できるデータに基づいた分析コメントです。","drivers":"確認できるデータに基づいた分析コメントです。","watch":"確認できるデータに基づいた分析コメントです。"}';
begin
  if exists(select 1 from public.ai_comments where date=day) then
    raise exception 'Today already has a real memo; do not run this fixture';
  end if;
  first_lease:=public.claim_daily_analysis('gemini-2.5-flash');
  if not (first_lease->>'claimed')::boolean then raise exception 'Could not claim'; end if;
  result:=public.claim_daily_analysis('gemini-2.5-flash');
  if (result->>'claimed')::boolean or result->>'status'<>'processing' then raise exception 'Duplicate claim accepted'; end if;
  perform public.finish_daily_analysis((first_lease->>'token')::uuid,null,null,'rate_limited');
  result:=public.claim_daily_analysis('gemini-2.5-flash');
  if (result->>'claimed')::boolean or result->>'status'<>'waiting' then raise exception 'Cooldown not enforced'; end if;
  update portfolio_internal.analysis_runs set retry_at=clock_timestamp()-interval '1 second' where date=day;
  second_lease:=public.claim_daily_analysis('gemini-2.5-flash');
  if not (second_lease->>'claimed')::boolean then raise exception 'Retry not available'; end if;
  result:=public.finish_daily_analysis((first_lease->>'token')::uuid,sections,
    jsonb_build_object('date',day,'prices_updated_at',clock_timestamp()),null);
  if (result->>'saved')::boolean then raise exception 'Expired token accepted'; end if;
  result:=public.finish_daily_analysis((second_lease->>'token')::uuid,sections,
    jsonb_build_object('date',day,'prices_updated_at',clock_timestamp()),null);
  if not (result->>'saved')::boolean then raise exception 'Memo was not saved'; end if;
  result:=public.claim_daily_analysis('gemini-2.5-flash');
  if (result->>'claimed')::boolean or result->>'status'<>'ready' then raise exception 'Saved memo regenerated'; end if;
  -- Re-enter a failed state only within this rollback fixture to exercise the cap.
  update portfolio_internal.analysis_runs set attempts=3,status='failed',retry_at=clock_timestamp()-interval '1 second' where date=day;
end $$;
reset role;
-- Remove only this transaction's synthetic memo; rollback restores everything.
delete from public.ai_comments where date=(clock_timestamp() at time zone 'Asia/Tokyo')::date;
set local role service_role;
do $$ declare result jsonb; begin
  result:=public.claim_daily_analysis('gemini-2.5-flash');
  if (result->>'claimed')::boolean or result->>'status'<>'daily_limit' then raise exception 'Daily cap not enforced'; end if;
end $$;
reset role;
do $$ begin
  if has_function_privilege('anon','public.claim_daily_analysis(text)','EXECUTE')
     or has_function_privilege('authenticated','public.finish_daily_analysis(uuid,jsonb,jsonb,text)','EXECUTE')
     or has_schema_privilege('anon','portfolio_internal','USAGE') then
    raise exception 'Backend-only job is exposed';
  end if;
end $$;
set local role anon;
select date,model,sections from public.public_ai_comments order by date desc limit 1;
rollback;
select 'daily leases, persistence, cooldown, cap, and access checks passed' as result;
