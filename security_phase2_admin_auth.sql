-- Phase 2: Supabase Auth administrator access for private portfolio CRUD.
-- Safe to run before an administrator account exists: nobody can write until
-- an auth.users row is explicitly added to public.portfolio_admins.

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

grant usage on schema public to anon, authenticated;
grant select on table
    public.public_portfolio_holdings,
    public.public_portfolio_stats,
    public.public_portfolio_history,
    public.public_price_cache,
    public.public_ai_comments
to anon, authenticated;

create table if not exists public.portfolio_admins (
    user_id uuid primary key references auth.users(id) on delete cascade,
    created_at timestamptz not null default now()
);

alter table public.portfolio_admins enable row level security;
revoke all privileges on table public.portfolio_admins from public, anon, authenticated;
grant select on table public.portfolio_admins to authenticated;

drop policy if exists "Administrator can verify own membership" on public.portfolio_admins;
create policy "Administrator can verify own membership"
on public.portfolio_admins
for select
to authenticated
using (user_id = (select auth.uid()));

alter table public.transactions
    add column if not exists fee_amount numeric not null default 0,
    add column if not exists fee_currency text not null default 'USD',
    add column if not exists source text,
    add column if not exists updated_at timestamptz not null default now();

do $$
begin
    if not exists (
        select 1 from pg_constraint
        where conrelid = 'public.transactions'::regclass
          and conname = 'transactions_quantity_positive'
    ) then
        alter table public.transactions
            add constraint transactions_quantity_positive check (quantity > 0);
    end if;

    if not exists (
        select 1 from pg_constraint
        where conrelid = 'public.transactions'::regclass
          and conname = 'transactions_price_nonnegative'
    ) then
        alter table public.transactions
            add constraint transactions_price_nonnegative check (price_per_unit >= 0);
    end if;

    if not exists (
        select 1 from pg_constraint
        where conrelid = 'public.transactions'::regclass
          and conname = 'transactions_total_nonnegative'
    ) then
        alter table public.transactions
            add constraint transactions_total_nonnegative check (total_amount >= 0);
    end if;

    if not exists (
        select 1 from pg_constraint
        where conrelid = 'public.transactions'::regclass
          and conname = 'transactions_fee_nonnegative'
    ) then
        alter table public.transactions
            add constraint transactions_fee_nonnegative check (fee_amount >= 0);
    end if;

    if not exists (
        select 1 from pg_constraint
        where conrelid = 'public.transactions'::regclass
          and conname = 'transactions_fee_currency_not_blank'
    ) then
        alter table public.transactions
            add constraint transactions_fee_currency_not_blank
            check (length(btrim(fee_currency)) between 1 and 12);
    end if;
end
$$;

create index if not exists transactions_asset_id_idx
    on public.transactions (asset_id);
create index if not exists transactions_date_idx
    on public.transactions (date desc);
create index if not exists transactions_type_date_idx
    on public.transactions (type, date desc);

create or replace function public.set_transaction_updated_at()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists set_transaction_updated_at on public.transactions;
create trigger set_transaction_updated_at
before update on public.transactions
for each row execute function public.set_transaction_updated_at();

create or replace function public.update_balance_on_transaction()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
begin
    if tg_op = 'INSERT' then
        insert into public.balances (asset_id, amount)
        values (
            new.asset_id,
            case
                when new.type in ('Buy', 'Airdrop', 'Staking Reward', 'Interest', 'Gift') then new.quantity
                when new.type in ('Sell', 'Transfer') then -new.quantity
                else 0
            end
        )
        on conflict (asset_id) do update set
            amount = public.balances.amount + excluded.amount,
            updated_at = now();
        return new;
    elsif tg_op = 'DELETE' then
        update public.balances
        set amount = amount - case
                when old.type in ('Buy', 'Airdrop', 'Staking Reward', 'Interest', 'Gift') then old.quantity
                when old.type in ('Sell', 'Transfer') then -old.quantity
                else 0
            end,
            updated_at = now()
        where asset_id = old.asset_id;
        return old;
    elsif tg_op = 'UPDATE' then
        update public.balances
        set amount = amount - case
                when old.type in ('Buy', 'Airdrop', 'Staking Reward', 'Interest', 'Gift') then old.quantity
                when old.type in ('Sell', 'Transfer') then -old.quantity
                else 0
            end,
            updated_at = now()
        where asset_id = old.asset_id;

        insert into public.balances (asset_id, amount)
        values (
            new.asset_id,
            case
                when new.type in ('Buy', 'Airdrop', 'Staking Reward', 'Interest', 'Gift') then new.quantity
                when new.type in ('Sell', 'Transfer') then -new.quantity
                else 0
            end
        )
        on conflict (asset_id) do update set
            amount = public.balances.amount + excluded.amount,
            updated_at = now();
        return new;
    end if;
    return null;
end;
$$;

drop trigger if exists on_transaction_change on public.transactions;
create trigger on_transaction_change
after insert or update or delete on public.transactions
for each row execute function public.update_balance_on_transaction();

revoke all on function public.set_transaction_updated_at() from public, anon;
revoke all on function public.update_balance_on_transaction() from public, anon;
grant execute on function public.set_transaction_updated_at() to authenticated;
grant execute on function public.update_balance_on_transaction() to authenticated;

grant select, insert, update, delete on table public.assets to authenticated;
grant select, insert, update, delete on table public.transactions to authenticated;
grant select, insert, update on table public.balances to authenticated;
grant usage, select on sequence
    public.assets_id_seq,
    public.transactions_id_seq,
    public.balances_id_seq
to authenticated;

drop policy if exists "Administrator can read assets" on public.assets;
drop policy if exists "Administrator can add assets" on public.assets;
drop policy if exists "Administrator can update assets" on public.assets;
drop policy if exists "Administrator can delete assets" on public.assets;
create policy "Administrator can read assets" on public.assets
for select to authenticated
using (exists (
    select 1 from public.portfolio_admins pa
    where pa.user_id = (select auth.uid())
));
create policy "Administrator can add assets" on public.assets
for insert to authenticated
with check (exists (
    select 1 from public.portfolio_admins pa
    where pa.user_id = (select auth.uid())
));
create policy "Administrator can update assets" on public.assets
for update to authenticated
using (exists (
    select 1 from public.portfolio_admins pa
    where pa.user_id = (select auth.uid())
))
with check (exists (
    select 1 from public.portfolio_admins pa
    where pa.user_id = (select auth.uid())
));
create policy "Administrator can delete assets" on public.assets
for delete to authenticated
using (exists (
    select 1 from public.portfolio_admins pa
    where pa.user_id = (select auth.uid())
));

drop policy if exists "Administrator can read transactions" on public.transactions;
drop policy if exists "Administrator can add transactions" on public.transactions;
drop policy if exists "Administrator can update transactions" on public.transactions;
drop policy if exists "Administrator can delete transactions" on public.transactions;
create policy "Administrator can read transactions" on public.transactions
for select to authenticated
using (exists (
    select 1 from public.portfolio_admins pa
    where pa.user_id = (select auth.uid())
));
create policy "Administrator can add transactions" on public.transactions
for insert to authenticated
with check (exists (
    select 1 from public.portfolio_admins pa
    where pa.user_id = (select auth.uid())
));
create policy "Administrator can update transactions" on public.transactions
for update to authenticated
using (exists (
    select 1 from public.portfolio_admins pa
    where pa.user_id = (select auth.uid())
))
with check (exists (
    select 1 from public.portfolio_admins pa
    where pa.user_id = (select auth.uid())
));
create policy "Administrator can delete transactions" on public.transactions
for delete to authenticated
using (exists (
    select 1 from public.portfolio_admins pa
    where pa.user_id = (select auth.uid())
));

drop policy if exists "Administrator can read balances" on public.balances;
drop policy if exists "Administrator can add balances" on public.balances;
drop policy if exists "Administrator can update balances" on public.balances;
create policy "Administrator can read balances" on public.balances
for select to authenticated
using (exists (
    select 1 from public.portfolio_admins pa
    where pa.user_id = (select auth.uid())
));
create policy "Administrator can add balances" on public.balances
for insert to authenticated
with check (exists (
    select 1 from public.portfolio_admins pa
    where pa.user_id = (select auth.uid())
));
create policy "Administrator can update balances" on public.balances
for update to authenticated
using (exists (
    select 1 from public.portfolio_admins pa
    where pa.user_id = (select auth.uid())
))
with check (exists (
    select 1 from public.portfolio_admins pa
    where pa.user_id = (select auth.uid())
));

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
        'public.ai_comments',
        'public.portfolio_admins'
    ]
    loop
        if has_table_privilege('anon', private_table, 'SELECT')
           or has_table_privilege('anon', private_table, 'INSERT')
           or has_table_privilege('anon', private_table, 'UPDATE')
           or has_table_privilege('anon', private_table, 'DELETE') then
            raise exception 'anon still has direct privileges on %', private_table;
        end if;
    end loop;
end
$$;

set local role anon;
select count(*) from public.public_portfolio_holdings;
select count(*) from public.public_portfolio_stats;
select count(*) from public.public_portfolio_history;
select count(*) from public.public_price_cache;
select count(*) from public.public_ai_comments;
reset role;

notify pgrst, 'reload schema';

commit;
