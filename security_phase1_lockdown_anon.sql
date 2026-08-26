-- Phase 1C: run only after the read-only app has been deployed and verified.
-- Removes all direct anonymous/authenticated access to private base tables.

begin;

alter table public.assets enable row level security;
alter table public.transactions enable row level security;
alter table public.balances enable row level security;
alter table public.portfolio_snapshots enable row level security;
alter table public.price_cache enable row level security;
alter table public.ai_comments enable row level security;

drop policy if exists "Enable all for anon" on public.assets;
drop policy if exists "Enable all for anon" on public.transactions;
drop policy if exists "Enable all for anon" on public.balances;
drop policy if exists "Enable all for anon" on public.portfolio_snapshots;
drop policy if exists "Enable all for anon" on public.price_cache;
drop policy if exists "Enable all for anon" on public.ai_comments;

revoke all privileges on table
    public.assets,
    public.transactions,
    public.balances,
    public.portfolio_snapshots,
    public.price_cache,
    public.ai_comments
from public, anon, authenticated;

-- Keep only the curated views readable without login.
grant usage on schema public to anon;
grant select on table
    public.public_portfolio_holdings,
    public.public_portfolio_stats,
    public.public_portfolio_history,
    public.public_price_cache,
    public.public_ai_comments
to anon;

-- Fail the transaction if an anonymous role still has direct DML privileges.
do $$
declare
    private_table text;
begin
    foreach private_table in array array[
        'public.assets',
        'public.transactions',
        'public.balances',
        'public.portfolio_snapshots',
        'public.price_cache',
        'public.ai_comments'
    ]
    loop
        if has_table_privilege('anon', private_table, 'INSERT')
           or has_table_privilege('anon', private_table, 'UPDATE')
           or has_table_privilege('anon', private_table, 'DELETE')
           or has_table_privilege('anon', private_table, 'SELECT') then
            raise exception 'anon still has direct privileges on %', private_table;
        end if;
    end loop;
end
$$;

-- Confirm the public role can still read every curated endpoint before commit.
set local role anon;
select count(*) from public.public_portfolio_holdings;
select count(*) from public.public_portfolio_stats;
select count(*) from public.public_portfolio_history;
select count(*) from public.public_price_cache;
select count(*) from public.public_ai_comments;
reset role;

notify pgrst, 'reload schema';

commit;
