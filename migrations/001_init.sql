create table if not exists users (
  id bigserial primary key,
  tg_user_id bigint unique not null,
  created_at timestamptz default now(),
  goal text,
  experience text,
  days_per_week int,
  equipment text,
  premium_until timestamptz
);

create table if not exists workouts (
  id bigserial primary key,
  tg_user_id bigint not null,
  day_of_week int not null,
  plan jsonb not null,
  week_start date not null
);

create table if not exists logs (
  id bigserial primary key,
  tg_user_id bigint not null,
  ts timestamptz default now(),
  exercise text not null,
  sets int,
  reps int,
  weight numeric,
  rpe numeric
);

create index if not exists idx_workouts_user_week on workouts(tg_user_id, week_start);
create index if not exists idx_logs_user_ts on logs(tg_user_id, ts);