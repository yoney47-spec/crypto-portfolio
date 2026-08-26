-- VERSION 2: fixes PostgreSQL 16+ SET ROLE requirements during view ownership transfer.
-- Phase 1A: create curated public views before deploying the read-only app.
-- This script does not revoke any existing permission, so the current app keeps working.

begin;

-- Use a no-login, read-only owner for curated views. The role receives only
-- the source columns required by the published aggregates.
do $$
begin
    if not exists (
        select 1 from pg_roles where rolname = 'portfolio_public_view_owner'
    ) then
        execute 'create role portfolio_public_view_owner nologin noinherit nobypassrls';
    end if;
end
$$;

revoke all privileges on all tables in schema public from portfolio_public_view_owner;
grant usage on schema public to portfolio_public_view_owner;
grant select (id, name, symbol, api_id, icon_url)
    on public.assets to portfolio_public_view_owner;
grant select (asset_id, date, type, quantity, total_amount)
    on public.transactions to portfolio_public_view_owner;
grant select (date, total_value_jpy)
    on public.portfolio_snapshots to portfolio_public_view_owner;
grant select (api_id, price_usd, price_jpy, usd_24h_change, updated_at)
    on public.price_cache to portfolio_public_view_owner;
grant select (date, comment, created_at)
    on public.ai_comments to portfolio_public_view_owner;

alter table public.assets enable row level security;
alter table public.transactions enable row level security;
alter table public.portfolio_snapshots enable row level security;
alter table public.price_cache enable row level security;
alter table public.ai_comments enable row level security;

drop policy if exists "Public view owner can read" on public.assets;
drop policy if exists "Public view owner can read" on public.transactions;
drop policy if exists "Public view owner can read" on public.portfolio_snapshots;
drop policy if exists "Public view owner can read" on public.price_cache;
drop policy if exists "Public view owner can read" on public.ai_comments;

create policy "Public view owner can read" on public.assets
    for select to portfolio_public_view_owner using (true);
create policy "Public view owner can read" on public.transactions
    for select to portfolio_public_view_owner using (true);
create policy "Public view owner can read" on public.portfolio_snapshots
    for select to portfolio_public_view_owner using (true);
create policy "Public view owner can read" on public.price_cache
    for select to portfolio_public_view_owner using (true);
create policy "Public view owner can read" on public.ai_comments
    for select to portfolio_public_view_owner using (true);

create or replace view public.public_portfolio_holdings
with (security_barrier = true)
as
with transaction_aggregates as (
    select
        asset_id,
        coalesce(sum(
            case
                when type in ('Buy', 'Airdrop', 'Staking Reward', 'Interest', 'Gift') then quantity
                when type in ('Sell', 'Transfer') then -quantity
                else 0
            end
        ), 0) as holdings,
        coalesce(sum(case when type = 'Buy' then quantity else 0 end), 0) as bought_quantity,
        coalesce(sum(case when type = 'Buy' then total_amount else 0 end), 0) as bought_cost
    from public.transactions
    group by asset_id
)
select
    assets.id as asset_id,
    assets.name,
    assets.symbol,
    assets.api_id,
    assets.icon_url,
    aggregates.holdings,
    case
        when aggregates.bought_quantity > 0
            then aggregates.bought_cost / aggregates.bought_quantity
        else 0
    end as avg_cost,
    case
        when aggregates.bought_quantity > 0
            then (aggregates.bought_cost / aggregates.bought_quantity) * aggregates.holdings
        else 0
    end as total_cost
from public.assets as assets
join transaction_aggregates as aggregates on aggregates.asset_id = assets.id
where aggregates.holdings > 0.00000001;

create or replace view public.public_portfolio_stats
with (security_barrier = true)
as
select
    (select count(id)::bigint from public.assets) as asset_count,
    (select count(asset_id)::bigint from public.transactions) as transaction_count,
    (
        select coalesce(sum(total_amount), 0)
        from public.transactions
        where type = 'Buy'
          and (date at time zone 'Asia/Tokyo') >= date_trunc('year', now() at time zone 'Asia/Tokyo')
    ) as total_investment_this_year,
    (
        select coalesce(sum(total_amount), 0)
        from public.transactions
        where type = 'Sell'
          and (date at time zone 'Asia/Tokyo') >= date_trunc('year', now() at time zone 'Asia/Tokyo')
    ) as total_sales_this_year;

create or replace view public.public_portfolio_history
with (security_barrier = true)
as
select date, total_value_jpy
from public.portfolio_snapshots;

create or replace view public.public_price_cache
with (security_barrier = true)
as
select api_id, price_usd, price_jpy, usd_24h_change, updated_at
from public.price_cache;

create or replace view public.public_ai_comments
with (security_barrier = true)
as
select date, comment, created_at
from public.ai_comments;

revoke all on table
    public.public_portfolio_holdings,
    public.public_portfolio_stats,
    public.public_portfolio_history,
    public.public_price_cache,
    public.public_ai_comments
from public, anon, authenticated;

grant usage on schema public to anon;
grant select on table
    public.public_portfolio_holdings,
    public.public_portfolio_stats,
    public.public_portfolio_history,
    public.public_price_cache,
    public.public_ai_comments
to anon;

comment on view public.public_portfolio_holdings is
    'Public aggregate holdings only. Excludes asset location and individual transactions.';
comment on view public.public_portfolio_stats is
    'Public aggregate counts and current-year cash-flow totals.';
comment on view public.public_portfolio_history is
    'Public daily portfolio totals.';
comment on view public.public_price_cache is
    'Public market-price cache without write access.';
comment on view public.public_ai_comments is
    'Public AI comment text without private portfolio_summary JSON.';

-- PostgreSQL views use the owner's permissions by default. Make that owner the
-- restricted no-login role above, not postgres.
grant create on schema public to portfolio_public_view_owner;

-- PostgreSQL 16+ gives a CREATEROLE user administrative membership in a newly
-- created role with SET disabled. Temporarily enable SET ROLE so ownership can
-- be transferred, then restore the original restricted membership below.
do $$
begin
    if current_setting('server_version_num')::integer >= 160000 then
        execute format(
            'grant portfolio_public_view_owner to %I with set true',
            session_user
        );
    else
        execute format(
            'grant portfolio_public_view_owner to %I',
            session_user
        );
    end if;
end
$$;

alter view public.public_portfolio_holdings owner to portfolio_public_view_owner;
alter view public.public_portfolio_stats owner to portfolio_public_view_owner;
alter view public.public_portfolio_history owner to portfolio_public_view_owner;
alter view public.public_price_cache owner to portfolio_public_view_owner;
alter view public.public_ai_comments owner to portfolio_public_view_owner;

do $$
begin
    if current_setting('server_version_num')::integer >= 160000 then
        execute format(
            'revoke set option for portfolio_public_view_owner from %I',
            session_user
        );
    else
        execute format(
            'revoke portfolio_public_view_owner from %I',
            session_user
        );
    end if;
end
$$;

revoke create on schema public from portfolio_public_view_owner;

notify pgrst, 'reload schema';

commit;
