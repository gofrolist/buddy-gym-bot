alter table if exists users add column if not exists handle varchar(64);
alter table if exists users add column if not exists tz varchar(32) default 'UTC';
alter table if exists users add column if not exists units varchar(8) default 'kg';
alter table if exists users add column if not exists last_lang varchar(8) default 'en';
