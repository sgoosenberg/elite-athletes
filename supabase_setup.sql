-- Run once in the SQL Editor of your FREE Supabase project.
create table if not exists public.athlete_submissions (
  id text primary key,
  name text not null check (char_length(name) between 1 and 80),
  phone text not null check (char_length(phone) between 1 and 30),
  history text not null default '' check (char_length(history) <= 2000),
  status text not null default 'pending' check (status in ('pending', 'approved', 'denied')),
  highlights_url text not null default '',
  highlights_video text not null default '',
  created_at timestamptz not null default now()
);
alter table public.athlete_submissions enable row level security;
revoke all on public.athlete_submissions from anon, authenticated;
grant select, insert, update on public.athlete_submissions to service_role;

-- Private bucket: only the server can upload or issue short-lived viewing URLs.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('highlights', 'highlights', false, 52428800,
        array['video/mp4', 'video/quicktime', 'video/webm'])
on conflict (id) do update set public = false,
  file_size_limit = excluded.file_size_limit,
  allowed_mime_types = excluded.allowed_mime_types;
