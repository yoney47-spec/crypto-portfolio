-- Additive workspace upgrade. Existing transactions and JPY history are preserved.
alter table public.transactions
  add column input_currency text,
  add column input_price numeric,
  add column input_total numeric,
  add column exchange_rate numeric,
  add column exchange_rate_source text,
  add column exchange_rate_date date,
  add constraint transactions_input_currency_check check (input_currency in ('JPY','USD')),
  add constraint transactions_input_price_check check (input_price >= 0 and input_price < 'Infinity'::numeric),
  add constraint transactions_input_total_check check (input_total >= 0 and input_total < 'Infinity'::numeric),
  add constraint transactions_exchange_rate_check check (exchange_rate > 0 and exchange_rate < 'Infinity'::numeric),
  add constraint transactions_jpy_metadata_check check (
    input_currency is distinct from 'JPY' or
    (input_price is not null and input_total is not null and exchange_rate is not null
     and exchange_rate_date is not null and length(trim(exchange_rate_source)) > 0
     and exchange_rate_source is not null));

alter table public.portfolio_snapshots
  add column total_value_usd numeric check (total_value_usd >= 0 and total_value_usd < 'Infinity'::numeric),
  add column prices_updated_at timestamptz;
alter table public.price_cache add column jpy_24h_change numeric;

grant select (total_value_usd, prices_updated_at) on public.portfolio_snapshots to portfolio_public_view_owner;
grant select (jpy_24h_change) on public.price_cache to portfolio_public_view_owner;
grant select (exchange_rate) on public.transactions to portfolio_public_view_owner;

create or replace view public.public_portfolio_history with (security_barrier=true) as
 select date, total_value_jpy, total_value_usd, prices_updated_at from public.portfolio_snapshots;
create or replace view public.public_price_cache with (security_barrier=true) as
 select api_id,price_usd,price_jpy,usd_24h_change,updated_at,jpy_24h_change from public.price_cache;

-- Only year aggregates are public; individual dates, notes and original inputs stay private.
create or replace view public.public_portfolio_stats with (security_barrier=true) as
 with flows as (
 select extract(year from now() at time zone 'Asia/Tokyo')::int as year,
 coalesce(sum(case when type in ('Buy','Gift') then total_amount else -total_amount end),0) as net_flow_usd,
 coalesce(sum((case when type in ('Buy','Gift') then total_amount else -total_amount end) * exchange_rate),0) as net_flow_jpy,
 coalesce(bool_or(total_amount <= 0),false) as unknown_usd,
 coalesce(bool_or(exchange_rate is null or total_amount <= 0),false) as unknown_jpy
 from public.transactions
 where type in ('Buy','Sell','Gift','Transfer')
 and date >= (date_trunc('year', now() at time zone 'Asia/Tokyo') at time zone 'Asia/Tokyo')
 and date <= now())
 select (select count(id) from public.assets) as asset_count,
 (select count(asset_id) from public.transactions) as transaction_count,
 (select coalesce(sum(total_amount),0) from public.transactions where type='Buy'
  and (date at time zone 'Asia/Tokyo') >= date_trunc('year',now() at time zone 'Asia/Tokyo')) as total_investment_this_year,
 (select coalesce(sum(total_amount),0) from public.transactions where type='Sell'
  and (date at time zone 'Asia/Tokyo') >= date_trunc('year',now() at time zone 'Asia/Tokyo')) as total_sales_this_year,
 flows.year, flows.net_flow_usd, flows.net_flow_jpy, flows.unknown_usd, flows.unknown_jpy from flows;

create table public.portfolio_goals (
 user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
 asset_id bigint not null references public.assets(id) on delete cascade,
 target_quantity numeric check (target_quantity > 0 and target_quantity < 'Infinity'::numeric),
 target_weight numeric check (target_weight >= 0 and target_weight <= 100),
 updated_at timestamptz not null default now(),
 primary key (user_id,asset_id),
 constraint portfolio_goals_target_required check (target_quantity is not null or target_weight is not null)
);
create index portfolio_goals_asset_idx on public.portfolio_goals(asset_id);
alter table public.portfolio_goals enable row level security;
revoke all on public.portfolio_goals from anon, public;
grant select,insert,update,delete on public.portfolio_goals to authenticated;
create policy goals_admin_owner on public.portfolio_goals for all to authenticated
 using (user_id=(select auth.uid()) and exists (select 1 from public.portfolio_admins where user_id=(select auth.uid())))
 with check (user_id=(select auth.uid()) and exists (select 1 from public.portfolio_admins where user_id=(select auth.uid())));

-- Curated views intentionally use a restricted NOLOGIN owner, which already has
-- column-only grants and RLS SELECT policies. Do not switch these to invoker views.
notify pgrst, 'reload schema';
