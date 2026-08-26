-- Initial read-only audit before public views exist.
-- Returns grants, RLS policies, and effective anon privileges in one result set.

select
    'GRANT'::text as category,
    table_name::text as object_name,
    grantee::text as subject,
    privilege_type::text as detail
from information_schema.role_table_grants
where table_schema = 'public'
  and table_name in (
      'assets',
      'transactions',
      'balances',
      'portfolio_snapshots',
      'price_cache',
      'ai_comments'
  )
  and grantee in ('anon', 'authenticated')

union all

select
    'POLICY'::text as category,
    tablename::text as object_name,
    policyname::text as subject,
    concat(
        'roles=', roles::text,
        '; cmd=', cmd,
        '; using=', coalesce(qual, 'NULL'),
        '; check=', coalesce(with_check, 'NULL')
    ) as detail
from pg_policies
where schemaname = 'public'
  and tablename in (
      'assets',
      'transactions',
      'balances',
      'portfolio_snapshots',
      'price_cache',
      'ai_comments'
  )

union all

select
    'CHECK'::text as category,
    'transactions'::text as object_name,
    'anon effective privileges'::text as subject,
    jsonb_build_object(
        'select', has_table_privilege('anon', 'public.transactions', 'SELECT'),
        'insert', has_table_privilege('anon', 'public.transactions', 'INSERT'),
        'update', has_table_privilege('anon', 'public.transactions', 'UPDATE'),
        'delete', has_table_privilege('anon', 'public.transactions', 'DELETE')
    )::text as detail

order by category, object_name, subject, detail;
