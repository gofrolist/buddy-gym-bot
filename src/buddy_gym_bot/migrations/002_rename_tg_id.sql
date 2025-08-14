alter table if exists users rename column tg_user_id to tg_id;
alter table if exists workouts rename column tg_user_id to tg_id;
alter table if exists logs rename column tg_user_id to tg_id;
