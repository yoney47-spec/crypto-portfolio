-- Run as the database owner. Synthetic inputs only; no network or record writes.
do $$
declare result jsonb; bad jsonb; rejected boolean;
begin
  result:=portfolio_internal.value_snapshot(
    '[{"api_id":"btc","symbol":"BTC","holdings":0.1},{"api_id":"kas","symbol":"KAS","holdings":1000}]',
    '{"btc":{"jpy":10000000,"usd":100000},"kas":{"jpy":10,"usd":0.1}}');
  if (result->>'total_value_jpy')::numeric<>1010000
     or (result->>'total_value_usd')::numeric<>10100 then
    raise exception 'Paired valuation assertion failed';
  end if;
  for bad in select value from jsonb_array_elements(
    '[{}, {"btc":{"jpy":10000000}}, {"btc":{"jpy":10000000,"usd":0}}, {"btc":{"jpy":10000000,"usd":null}}]') loop
    rejected:=false;
    begin
      perform portfolio_internal.value_snapshot('[{"api_id":"btc","symbol":"BTC","holdings":0.1}]',bad);
    exception when raise_exception then rejected:=true;
    end;
    if not rejected then raise exception 'Incomplete prices were accepted'; end if;
  end loop;
  if has_function_privilege('anon','portfolio_internal.capture_daily_snapshot()','EXECUTE')
     or has_function_privilege('authenticated','portfolio_internal.capture_daily_snapshot()','EXECUTE') then
    raise exception 'Scheduled writer is exposed to app roles';
  end if;
end $$;
select 'valuation and access checks passed' as result;
