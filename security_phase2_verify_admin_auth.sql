-- Read-only verification for Phase 2 administrator access.

select 'anonymous base-table privileges' as check_name,
       case when count(*) = 0 then 'PASS' else 'FAIL' end as status,
       count(*)::text as detail
from information_schema.role_table_grants
where grantee = 'anon'
  and table_schema = 'public'
  and table_name in (
      'assets', 'transactions', 'balances', 'portfolio_snapshots',
      'price_cache', 'ai_comments', 'portfolio_admins'
  )

union all

select 'administrator allow-list RLS',
       case when c.relrowsecurity then 'PASS' else 'FAIL' end,
       'RLS=' || c.relrowsecurity::text
from pg_class c
join pg_namespace n on n.oid = c.relnamespace
where n.nspname = 'public' and c.relname = 'portfolio_admins'

union all

select 'transaction validation constraints',
       case when count(*) = 5 then 'PASS' else 'FAIL' end,
       count(*)::text || ' / 5'
from pg_constraint
where conrelid = 'public.transactions'::regclass
  and conname in (
      'transactions_quantity_positive',
      'transactions_price_nonnegative',
      'transactions_total_nonnegative',
      'transactions_fee_nonnegative',
      'transactions_fee_currency_not_blank'
  )

union all

select 'administrator transaction policies',
       case when count(*) = 4 then 'PASS' else 'FAIL' end,
       count(*)::text || ' / 4'
from pg_policies
where schemaname = 'public'
  and tablename = 'transactions'
  and policyname like 'Administrator can % transactions'

union all

select 'public views readable by anon',
       case when count(*) = 5 then 'PASS' else 'FAIL' end,
       count(*)::text || ' / 5'
from information_schema.role_table_grants
where grantee = 'anon'
  and table_schema = 'public'
  and table_name in (
      'public_portfolio_holdings', 'public_portfolio_stats',
      'public_portfolio_history', 'public_price_cache', 'public_ai_comments'
  )
  and privilege_type = 'SELECT'

order by check_name;
