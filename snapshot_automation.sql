-- Daily snapshots run inside Supabase, independently of Streamlit visitors.
-- Apply as the database owner. No new API key or public write endpoint is needed.
create extension if not exists http with schema extensions;
create extension if not exists pg_cron with schema pg_catalog;

create schema if not exists portfolio_internal;
revoke all on schema portfolio_internal from public, anon, authenticated;

-- Only the owner-operated job needs outbound HTTP access.
do $$
declare f record;
begin
  for f in
    select p.oid::regprocedure as signature from pg_proc p
    join pg_depend d on d.objid=p.oid and d.classid='pg_proc'::regclass and d.deptype='e'
    join pg_extension e on e.oid=d.refobjid and d.refclassid='pg_extension'::regclass
    where e.extname='http'
  loop
    execute format('revoke execute on function %s from public, anon, authenticated',f.signature);
  end loop;
end $$;

alter table public.portfolio_snapshots
  add column usd_jpy_rate numeric check (usd_jpy_rate > 0 and usd_jpy_rate < 'Infinity'::numeric),
  add column usd_jpy_rate_date date,
  add column usd_jpy_rate_source text,
  add column capture_source text check (capture_source in ('manual','scheduled')),
  add constraint snapshot_historical_fx_metadata check (
    usd_jpy_rate is null or
    (usd_jpy_rate_date is not null and usd_jpy_rate_date <= date
     and date-usd_jpy_rate_date <= 10 and usd_jpy_rate_source is not null));

grant select (usd_jpy_rate,usd_jpy_rate_date,usd_jpy_rate_source,capture_source)
  on public.portfolio_snapshots to portfolio_public_view_owner;
create or replace view public.public_portfolio_history with (security_barrier=true) as
  select date,total_value_jpy,total_value_usd,prices_updated_at,
         usd_jpy_rate,usd_jpy_rate_date,usd_jpy_rate_source,capture_source
  from public.portfolio_snapshots;
-- CREATE OR REPLACE preserves the existing restricted NOLOGIN view owner.

create or replace function portfolio_internal.value_snapshot(holdings jsonb, prices jsonb)
returns jsonb language plpgsql security invoker set search_path=pg_catalog as $$
declare item jsonb; quote jsonb; held numeric; jpy numeric; usd numeric;
        total_jpy numeric:=0; total_usd numeric:=0; asset_count integer:=0;
begin
  if jsonb_typeof(holdings) is distinct from 'array' or jsonb_array_length(holdings)=0 then
    raise exception 'No active holdings';
  end if;
  for item in select value from jsonb_array_elements(holdings) loop
    held:=(item->>'holdings')::numeric;
    if held is null or not (held>0 and held<'Infinity'::numeric) then
      raise exception 'Invalid holding quantity';
    end if;
    quote:=prices->(item->>'api_id');
    if jsonb_typeof(quote->'jpy') is distinct from 'number'
       or jsonb_typeof(quote->'usd') is distinct from 'number' then
      raise exception 'Missing JPY/USD price for %', item->>'symbol';
    end if;
    jpy:=(quote->>'jpy')::numeric; usd:=(quote->>'usd')::numeric;
    if not (jpy>0 and jpy<'Infinity'::numeric and usd>0 and usd<'Infinity'::numeric) then
      raise exception 'Invalid JPY/USD price for %', item->>'symbol';
    end if;
    total_jpy:=total_jpy+held*jpy; total_usd:=total_usd+held*usd;
    asset_count:=asset_count+1;
  end loop;
  if round(total_jpy)<=0 or round(total_usd,8)<=0 then
    raise exception 'Invalid portfolio total';
  end if;
  return jsonb_build_object('total_value_jpy',round(total_jpy),
                           'total_value_usd',round(total_usd,8),'asset_count',asset_count);
end $$;

create or replace function portfolio_internal.fetch_snapshot_valuation()
returns jsonb language plpgsql security invoker set search_path=pg_catalog,extensions as $$
declare holdings jsonb; ids text; response extensions.http_response; valuation jsonb;
begin
  perform extensions.http_set_curlopt('CURLOPT_TIMEOUT_MS','15000');
  perform extensions.http_set_curlopt('CURLOPT_CONNECTTIMEOUT_MS','5000');
  select jsonb_agg(jsonb_build_object('symbol',h.symbol,'api_id',h.api_id,'holdings',h.holdings) order by h.asset_id),
         string_agg(distinct h.api_id,',' order by h.api_id)
    into holdings,ids from public.public_portfolio_holdings h where h.holdings>0;
  if holdings is null or exists (
    select 1 from jsonb_array_elements(holdings) h where nullif(trim(h->>'api_id'),'') is null
  ) then raise exception 'Active holdings or price IDs are missing'; end if;
  -- Only public coin IDs are sent, never quantities or account information.
  response:=extensions.http_get('https://api.coingecko.com/api/v3/simple/price',
    jsonb_build_object('ids',ids,'vs_currencies','jpy,usd'));
  if response.status<>200 then
    raise exception 'CoinGecko returned HTTP %',response.status;
  end if;
  valuation:=portfolio_internal.value_snapshot(holdings,response.content::jsonb);
  return valuation || jsonb_build_object('prices_updated_at',clock_timestamp());
end $$;

create or replace function portfolio_internal.capture_daily_snapshot()
returns jsonb language plpgsql security invoker set search_path=pg_catalog as $$
declare snapshot_day date:=(clock_timestamp() at time zone 'Asia/Tokyo')::date;
        valuation jsonb; saved integer;
begin
  -- One worker per day; never overwrite an existing manual or automatic record.
  perform pg_advisory_xact_lock(hashtextextended('cryptofolio-daily-snapshot',0));
  if exists(select 1 from public.portfolio_snapshots where date=snapshot_day) then
    return jsonb_build_object('status','already_recorded','date',snapshot_day);
  end if;
  valuation:=portfolio_internal.fetch_snapshot_valuation();
  if snapshot_day<>(clock_timestamp() at time zone 'Asia/Tokyo')::date then
    raise exception 'Date changed during price retrieval';
  end if;
  insert into public.portfolio_snapshots
    (date,total_value_jpy,total_value_usd,prices_updated_at,created_at,capture_source)
  values(snapshot_day,(valuation->>'total_value_jpy')::numeric,(valuation->>'total_value_usd')::numeric,
         (valuation->>'prices_updated_at')::timestamptz,clock_timestamp(),'scheduled')
  on conflict(date) do nothing;
  get diagnostics saved=row_count;
  return jsonb_build_object('status',case when saved=1 then 'saved' else 'already_recorded' end,
                           'date',snapshot_day,'asset_count',valuation->'asset_count');
end $$;

create or replace function portfolio_internal.backfill_snapshot_exchange_rates()
returns integer language plpgsql security invoker set search_path=pg_catalog,extensions as $$
declare first_day date; last_day date; response extensions.http_response; rates jsonb; changed integer;
begin
  select min(date),max(date) into first_day,last_day from public.portfolio_snapshots
    where total_value_usd is null and usd_jpy_rate is null;
  if first_day is null then return 0; end if;
  perform extensions.http_set_curlopt('CURLOPT_TIMEOUT_MS','15000');
  perform extensions.http_set_curlopt('CURLOPT_CONNECTTIMEOUT_MS','5000');
  response:=extensions.http_get('https://api.frankfurter.dev/v2/rates',
    jsonb_build_object('base','USD','quotes','JPY','providers','ECB',
                      'from',(first_day-10)::text,'to',last_day::text));
  if response.status<>200 then raise exception 'Historical FX returned HTTP %',response.status; end if;
  rates:=response.content::jsonb;
  if jsonb_typeof(rates) is distinct from 'array' then raise exception 'Invalid historical FX response'; end if;
  -- Keep original monetary amounts unchanged. Only attach dated conversion data.
  with matched as (
    select s.date,r.date as rate_date,r.rate
    from public.portfolio_snapshots s
    cross join lateral (
      select f.date,f.rate from jsonb_to_recordset(rates) f(date date,base text,quote text,rate numeric)
      where f.base='USD' and f.quote='JPY' and f.rate>0 and f.rate<'Infinity'::numeric
        and f.date<=s.date and f.date>=s.date-10
      order by f.date desc limit 1
    ) r
    where s.total_value_usd is null and s.usd_jpy_rate is null
  )
  update public.portfolio_snapshots s set usd_jpy_rate=m.rate,usd_jpy_rate_date=m.rate_date,
         usd_jpy_rate_source='ECB / Frankfurter'
  from matched m where s.date=m.date and s.total_value_usd is null and s.usd_jpy_rate is null;
  get diagnostics changed=row_count;
  if exists(select 1 from public.portfolio_snapshots where total_value_usd is null and usd_jpy_rate is null) then
    raise exception 'Historical FX coverage incomplete; no backfill committed';
  end if;
  return changed;
end $$;

revoke all on all functions in schema portfolio_internal from public,anon,authenticated;

-- Cron uses GMT/UTC on this project: 00:05 UTC = 09:05 Asia/Tokyo.
-- Subsequent attempts return immediately once any snapshot exists for the day.
select cron.schedule('cryptofolio-daily-snapshot','5,20,35 0 * * *',
                     'select portfolio_internal.capture_daily_snapshot();');
notify pgrst,'reload schema';
