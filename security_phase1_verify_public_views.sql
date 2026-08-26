-- Phase 1B: compact read-only verification after creating the public views.
-- Expected result: eight rows, all with status = PASS.

with
target_views(view_name) as (
    values
        ('public_portfolio_holdings'),
        ('public_portfolio_stats'),
        ('public_portfolio_history'),
        ('public_price_cache'),
        ('public_ai_comments')
),
expected_columns(view_name, column_names) as (
    values
        ('public_portfolio_holdings', array[
            'asset_id', 'name', 'symbol', 'api_id', 'icon_url',
            'holdings', 'avg_cost', 'total_cost'
        ]::text[]),
        ('public_portfolio_stats', array[
            'asset_count', 'transaction_count',
            'total_investment_this_year', 'total_sales_this_year'
        ]::text[]),
        ('public_portfolio_history', array[
            'date', 'total_value_jpy'
        ]::text[]),
        ('public_price_cache', array[
            'api_id', 'price_usd', 'price_jpy',
            'usd_24h_change', 'updated_at'
        ]::text[]),
        ('public_ai_comments', array[
            'date', 'comment', 'created_at'
        ]::text[])
),
actual_columns as (
    select
        table_name as view_name,
        array_agg(column_name::text order by ordinal_position) as column_names
    from information_schema.columns
    where table_schema = 'public'
      and table_name in (select view_name from target_views)
    group by table_name
),
checks(sort_order, check_name, expected, actual, passed) as (
    select
        1,
        'public_views_exist',
        '5',
        count(*)::text,
        count(*) = 5
    from pg_class as c
    join pg_namespace as n on n.oid = c.relnamespace
    where n.nspname = 'public'
      and c.relkind = 'v'
      and c.relname in (select view_name from target_views)

    union all

    select
        2,
        'restricted_view_owner',
        '5/5',
        count(*) filter (
            where c.relowner::regrole::text = 'portfolio_public_view_owner'
        )::text || '/5',
        count(*) = 5
        and bool_and(c.relowner::regrole::text = 'portfolio_public_view_owner')
    from pg_class as c
    join pg_namespace as n on n.oid = c.relnamespace
    where n.nspname = 'public'
      and c.relkind = 'v'
      and c.relname in (select view_name from target_views)

    union all

    select
        3,
        'owner_role_is_safe',
        'nologin/noinherit/nobypassrls',
        concat(
            case when rolcanlogin then 'login' else 'nologin' end, '/',
            case when rolinherit then 'inherit' else 'noinherit' end, '/',
            case when rolbypassrls then 'bypassrls' else 'nobypassrls' end
        ),
        not rolcanlogin and not rolinherit and not rolbypassrls
    from pg_roles
    where rolname = 'portfolio_public_view_owner'

    union all

    select
        4,
        'owner_select_policies',
        '5/5',
        count(distinct tablename)::text || '/5',
        count(distinct tablename) = 5
    from pg_policies
    where schemaname = 'public'
      and policyname = 'Public view owner can read'
      and cmd = 'SELECT'
      and roles::text[] @> array['portfolio_public_view_owner']::text[]
      and tablename in (
          'assets',
          'transactions',
          'portfolio_snapshots',
          'price_cache',
          'ai_comments'
      )

    union all

    select
        5,
        'anon_can_select_views',
        '5/5',
        count(*) filter (
            where has_table_privilege(
                'anon', format('public.%I', view_name), 'SELECT'
            )
        )::text || '/5',
        bool_and(has_table_privilege(
            'anon', format('public.%I', view_name), 'SELECT'
        ))
    from target_views

    union all

    select
        6,
        'anon_cannot_write_views',
        '5/5',
        count(*) filter (
            where not has_table_privilege(
                'anon', format('public.%I', view_name), 'INSERT'
            )
              and not has_table_privilege(
                'anon', format('public.%I', view_name), 'UPDATE'
            )
              and not has_table_privilege(
                'anon', format('public.%I', view_name), 'DELETE'
            )
        )::text || '/5',
        bool_and(
            not has_table_privilege(
                'anon', format('public.%I', view_name), 'INSERT'
            )
            and not has_table_privilege(
                'anon', format('public.%I', view_name), 'UPDATE'
            )
            and not has_table_privilege(
                'anon', format('public.%I', view_name), 'DELETE'
            )
        )
    from target_views

    union all

    select
        7,
        'published_columns_exact',
        '5/5',
        count(*) filter (
            where actual.column_names = expected.column_names
        )::text || '/5',
        count(*) = 5
        and bool_and(actual.column_names = expected.column_names)
    from expected_columns as expected
    join actual_columns as actual using (view_name)

    union all

    select
        8,
        'legacy_access_unchanged',
        'true (temporary)',
        (
            has_table_privilege('anon', 'public.transactions', 'SELECT')
            and has_table_privilege('anon', 'public.transactions', 'INSERT')
            and has_table_privilege('anon', 'public.transactions', 'UPDATE')
            and has_table_privilege('anon', 'public.transactions', 'DELETE')
        )::text,
        has_table_privilege('anon', 'public.transactions', 'SELECT')
        and has_table_privilege('anon', 'public.transactions', 'INSERT')
        and has_table_privilege('anon', 'public.transactions', 'UPDATE')
        and has_table_privilege('anon', 'public.transactions', 'DELETE')
)
select
    check_name,
    expected,
    actual,
    case when passed then 'PASS' else 'FAIL' end as status
from checks
order by sort_order;
