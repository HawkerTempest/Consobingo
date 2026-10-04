-- ConsoBingo 1.0. Exécuter dans le MEME projet Supabase que SWOTmania.
-- Le bloc ci-dessous lie l'annuaire existant, sans recopier ni modifier ses lignes.
-- Si votre annuaire de référence est uniquement celui de STP-by-Step, remplacer
-- UNE FOIS source_prefix := 'swot' par source_prefix := 'stp' avant l'installation.
begin;
create table if not exists public.conso_config (id boolean primary key default true check(id), roster_source text not null check(roster_source in ('swot','stp')));
do $$
declare source_prefix text := 'swot'; previous_source text;
begin
 if to_regclass('public.'||source_prefix||'_students') is null or to_regclass('public.'||source_prefix||'_teachers') is null then
  raise exception 'CONSO_ROSTER_MISSING: installer le schema dans le projet de SWOTmania, ou choisir le prefixe stp dans ce bloc';
 end if;
 select roster_source into previous_source from public.conso_config where id;
 if previous_source is not null and previous_source<>source_prefix then raise exception 'CONSO_ROSTER_ALREADY_BOUND'; end if;
 insert into public.conso_config(id,roster_source) values(true,source_prefix) on conflict(id) do nothing;
 execute format('create or replace view public.conso_students as select student_id,email,first_name,last_name,campus,group_name,promotion,active from public.%I',source_prefix||'_students');
 execute format('create or replace view public.conso_teachers as select email,first_name,last_name,is_admin,active from public.%I',source_prefix||'_teachers');
end $$;
create table if not exists public.conso_sessions (
 id uuid primary key default gen_random_uuid(),student_id text not null,
 started_at timestamptz not null default now(),last_seen_at timestamptz not null default now(),ended_at timestamptz
);
create table if not exists public.conso_runs (
 student_id text primary key,state jsonb not null,revision bigint not null default 0,cycle integer not null default 1,
 lease_session uuid references public.conso_sessions(id),last_event_id uuid,
 started_at timestamptz not null default now(),updated_at timestamptz not null default now(),completed_at timestamptz,
 summary jsonb not null default '[]'::jsonb
);
create table if not exists public.conso_archives (
 student_id text not null,cycle integer not null,state jsonb not null,summary jsonb not null,
 started_at timestamptz not null,completed_at timestamptz,archived_at timestamptz not null default now(),
 primary key(student_id,cycle)
);
create table if not exists public.conso_mail_jobs (
 id uuid primary key default gen_random_uuid(),student_id text not null,kind text not null,
 campaign text not null,recipient text not null,status text not null check(status in ('sending','sent','failed','unknown')),
 token uuid not null default gen_random_uuid(),actor text not null,created_at timestamptz not null default now(),
 updated_at timestamptz not null default now(),error text not null default '',unique(student_id,kind,campaign)
);
create index if not exists conso_sessions_sid_idx on public.conso_sessions(student_id,last_seen_at);
alter table public.conso_config enable row level security;
alter table public.conso_sessions enable row level security;
alter table public.conso_runs enable row level security;
alter table public.conso_archives enable row level security;
alter table public.conso_mail_jobs enable row level security;
revoke all on public.conso_config,public.conso_students,public.conso_teachers,public.conso_sessions,public.conso_runs,public.conso_archives,public.conso_mail_jobs from public,anon,authenticated;

create or replace function public.conso_email() returns text
language sql stable security invoker set search_path='' as $$
 select case when auth.uid() is not null then lower(auth.jwt()->>'email') end
$$;
create or replace function public.conso_is_teacher() returns boolean
language sql stable security definer set search_path='' as $$
 select exists(select 1 from public.conso_teachers where active and email=public.conso_email())
$$;
create or replace function public.conso_student_id() returns text
language sql stable security definer set search_path='' as $$
 select student_id from public.conso_students where active and email=public.conso_email()
$$;
create or replace function public.conso_can_login(p_email text,p_role text) returns boolean
language sql stable security definer set search_path='' as $$
 select case when p_role='student' then exists(select 1 from public.conso_students where active and email=lower(trim(p_email)))
 when p_role='teacher' then exists(select 1 from public.conso_teachers where active and email=lower(trim(p_email))) else false end
$$;
create or replace function public.conso_identity(p_role text default null) returns jsonb
language plpgsql security definer set search_path='' as $$
declare result jsonb;
begin
 if p_role is null or p_role='teacher' then
  select to_jsonb(t)||'{"role":"teacher"}'::jsonb into result from public.conso_teachers t where active and email=public.conso_email();
  if result is not null then return result; end if;
 end if;
 if p_role is null or p_role='student' then
  select to_jsonb(s)||'{"role":"student"}'::jsonb into result from public.conso_students s where active and email=public.conso_email();
 end if;
 if result is null then raise exception 'CONSO_DENIED'; end if;
 return result;
end $$;
create or replace function public.conso_valid_state(p jsonb) returns boolean
language plpgsql immutable set search_path='' as $$
declare k text;
begin
 if not coalesce(jsonb_typeof(p)='object' and p->>'app'='ConsoBingo' and p->>'schema_version'='1' and p->>'case_id'='lea-pulse-v1'
 and pg_column_size(p)<500000 and (p->>'seed')~'^[0-9]+$' and (p->>'seed')::numeric between 0 and 4294967295
 and length(p->>'run_id')=36,false) then return false;end if;
 perform (p->>'run_id')::uuid;
 foreach k in array array['answers','history','feedback','aids','ui'] loop
  if jsonb_typeof(p->k) is distinct from 'object' then return false;end if;
 end loop;
 if jsonb_typeof(p->'unlocked') is distinct from 'array' or jsonb_array_length(p->'unlocked')>3 then return false;end if;
 return true;
exception when others then return false;
end $$;
create or replace function public.conso_open_session() returns uuid
language plpgsql security definer set search_path='' as $$
declare sid text:=public.conso_student_id(); result uuid;
begin
 if sid is null then raise exception 'CONSO_DENIED'; end if;
 insert into public.conso_sessions(student_id) values(sid) returning id into result;
 return result;
end $$;
create or replace function public.conso_get_run(p_student_id text default null) returns jsonb
language plpgsql security definer set search_path='' as $$
declare sid text:=coalesce(p_student_id,public.conso_student_id()); result jsonb;
begin
 if sid is null or (sid is distinct from public.conso_student_id() and not public.conso_is_teacher()) then raise exception 'CONSO_DENIED';end if;
 select to_jsonb(r) into result from public.conso_runs r where student_id=sid;
 return result;
end $$;
create or replace function public.conso_claim_run(p_session_id uuid,p_initial_state jsonb default null) returns jsonb
language plpgsql security definer set search_path='' as $$
declare sid text:=public.conso_student_id(); r public.conso_runs;
begin
 if sid is null or not exists(select 1 from public.conso_sessions where id=p_session_id and student_id=sid and ended_at is null) then raise exception 'CONSO_DENIED';end if;
 perform pg_advisory_xact_lock(hashtextextended('conso:'||sid,0));
 select * into r from public.conso_runs where student_id=sid for update;
 if not found then
  if not public.conso_valid_state(p_initial_state) then raise exception 'CONSO_INVALID';end if;
  insert into public.conso_runs(student_id,state,lease_session) values(sid,p_initial_state,p_session_id) returning * into r;
 else
  update public.conso_runs set lease_session=p_session_id where student_id=sid returning * into r;
 end if;
 return to_jsonb(r);
end $$;
create or replace function public.conso_save_run(p_session_id uuid,p_revision bigint,p_state jsonb,p_summary jsonb,p_event_id uuid,p_finish boolean default false) returns jsonb
language plpgsql security definer set search_path='' as $$
declare sid text:=public.conso_student_id();r public.conso_runs;
begin
 if sid is null or not exists(select 1 from public.conso_sessions where id=p_session_id and student_id=sid and ended_at is null) then raise exception 'CONSO_DENIED';end if;
 if not public.conso_valid_state(p_state) or jsonb_typeof(p_summary) is distinct from 'array' or pg_column_size(p_summary)>30000 or jsonb_array_length(p_summary)>12 or p_event_id is null then raise exception 'CONSO_INVALID';end if;
 select * into r from public.conso_runs where student_id=sid for update;
 if not found then raise exception 'CONSO_DENIED';end if;
 if r.lease_session is distinct from p_session_id then raise exception 'CONSO_LEASE';end if;
 if r.last_event_id=p_event_id then return to_jsonb(r);end if;
 if r.revision<>p_revision then raise exception 'CONSO_CONFLICT';end if;
 if p_state->'seed' is distinct from r.state->'seed' or p_state->'run_id' is distinct from r.state->'run_id' then raise exception 'CONSO_INVALID';end if;
 -- Activité formative : l'enregistrement final ne verrouille pas les réponses.
 update public.conso_runs set state=p_state,summary=p_summary,revision=revision+1,last_event_id=p_event_id,
 updated_at=now(),completed_at=case when p_finish then now() else completed_at end
 where student_id=sid returning * into r;
 update public.conso_sessions set last_seen_at=now() where id=p_session_id;
 return to_jsonb(r);
end $$;
create or replace function public.conso_restart(p_session_id uuid,p_revision bigint,p_initial_state jsonb) returns jsonb
language plpgsql security definer set search_path='' as $$
declare sid text:=public.conso_student_id();r public.conso_runs;
begin
 if sid is null or not exists(select 1 from public.conso_sessions where id=p_session_id and student_id=sid and ended_at is null) then raise exception 'CONSO_DENIED';end if;
 if not public.conso_valid_state(p_initial_state) then raise exception 'CONSO_INVALID';end if;
 select * into r from public.conso_runs where student_id=sid for update;
 if not found then raise exception 'CONSO_DENIED';end if;
 if r.lease_session is distinct from p_session_id then raise exception 'CONSO_LEASE';end if;
 if r.state->'run_id'=p_initial_state->'run_id' then return to_jsonb(r);end if;
 if r.revision<>p_revision then raise exception 'CONSO_CONFLICT';end if;
 insert into public.conso_archives(student_id,cycle,state,summary,started_at,completed_at) values(sid,r.cycle,r.state,r.summary,r.started_at,r.completed_at);
 update public.conso_runs set state=p_initial_state,summary='[]',cycle=cycle+1,revision=revision+1,
 last_event_id=null,completed_at=null,started_at=now(),updated_at=now() where student_id=sid returning * into r;
 return to_jsonb(r);
end $$;
create or replace function public.conso_touch(p_session_id uuid) returns boolean
language plpgsql security definer set search_path='' as $$
begin
 update public.conso_sessions set last_seen_at=now() where id=p_session_id and student_id=public.conso_student_id() and ended_at is null;
 return found;
end $$;
create or replace function public.conso_close_session(p_session_id uuid) returns boolean
language plpgsql security definer set search_path='' as $$
begin
 update public.conso_sessions set ended_at=now() where id=p_session_id and student_id=public.conso_student_id() and ended_at is null;
 return found;
end $$;
create or replace function public.conso_dashboard(p_offset integer default 0,p_limit integer default 200) returns jsonb
language plpgsql security definer set search_path='' as $$
declare result jsonb;
begin
 if not public.conso_is_teacher() then raise exception 'CONSO_DENIED';end if;
 select coalesce(jsonb_agg(to_jsonb(t)),'[]') into result from (
  select s.*,r.revision,r.cycle,r.started_at,r.updated_at,r.completed_at,coalesce(r.summary,'[]') as summary,
   (select max(last_seen_at) from public.conso_sessions cs where cs.student_id=s.student_id) as last_seen_at
  from public.conso_students s left join public.conso_runs r using(student_id)
  where s.active order by s.promotion,s.campus,s.group_name,s.last_name,s.student_id
  offset greatest(0,p_offset) limit least(200,greatest(1,p_limit)))t;
 return result;
end $$;
create or replace function public.conso_archived_runs(p_student_id text default null) returns jsonb
language plpgsql security definer set search_path='' as $$
declare sid text:=coalesce(p_student_id,public.conso_student_id());result jsonb;
begin
 if sid is null or (sid is distinct from public.conso_student_id() and not public.conso_is_teacher()) then raise exception 'CONSO_DENIED';end if;
 select coalesce(jsonb_agg(to_jsonb(r) order by cycle desc),'[]') into result from public.conso_archives r where student_id=sid;
 return result;
end $$;
create or replace function public.conso_reserve_mail(p_student_id text,p_kind text,p_campaign text) returns jsonb
language plpgsql security definer set search_path='' as $$
declare s public.conso_students;r public.conso_runs;m public.conso_mail_jobs;campaign_key text;
begin
 if p_kind='completion' then
  if public.conso_student_id() is distinct from p_student_id and not public.conso_is_teacher() then raise exception 'CONSO_DENIED';end if;
 elsif p_kind in ('invitation','reminder','result') then
  if not public.conso_is_teacher() then raise exception 'CONSO_DENIED';end if;
 else raise exception 'CONSO_DENIED';end if;
 select * into s from public.conso_students where student_id=p_student_id and active;
 if not found then raise exception 'CONSO_DENIED';end if;
 select * into r from public.conso_runs where student_id=p_student_id;
 if p_kind in ('completion','result') and r.completed_at is null then raise exception 'CONSO_NOT_FINISHED';end if;
 campaign_key:=case when p_kind='completion' then r.cycle::text else p_campaign end;
 if campaign_key is null or length(campaign_key) not between 1 and 80 then raise exception 'CONSO_INVALID';end if;
 insert into public.conso_mail_jobs(student_id,kind,campaign,recipient,status,actor)
 values(p_student_id,p_kind,campaign_key,s.email,'sending',public.conso_email())
 on conflict(student_id,kind,campaign) do nothing returning * into m;
 if not found then
  select * into m from public.conso_mail_jobs where student_id=p_student_id and kind=p_kind and campaign=campaign_key;
  return jsonb_build_object('allowed',false,'status',m.status,'job_id',m.id);
 end if;
 return jsonb_build_object('allowed',true,'status','sending','recipient',s.email,'job_id',m.id,'token',m.token,'first_name',s.first_name,'last_name',s.last_name);
end $$;
create or replace function public.conso_mark_mail(p_job_id uuid,p_token uuid,p_status text,p_error text default '') returns boolean
language plpgsql security definer set search_path='' as $$
begin
 if p_status not in ('sent','failed','unknown') then raise exception 'CONSO_INVALID';end if;
 update public.conso_mail_jobs set status=p_status,error=left(p_error,500),updated_at=now()
 where id=p_job_id and token=p_token and status='sending' and actor=public.conso_email();
 if not found then raise exception 'CONSO_DENIED';end if;
 return true;
end $$;
create or replace function public.conso_mails() returns jsonb
language plpgsql security definer set search_path='' as $$
declare result jsonb;
begin
 if public.conso_email() is null then raise exception 'CONSO_DENIED';end if;
 select coalesce(jsonb_agg(to_jsonb(t)-'token' order by t.created_at desc),'[]') into result from
 (select * from public.conso_mail_jobs where public.conso_is_teacher() or student_id=public.conso_student_id() order by created_at desc limit 1000)t;
 return result;
end $$;
-- Permissions strictement limitées aux RPC publiques ConsoBingo.
do $$ declare f record; begin
 for f in select p.oid::regprocedure as signature,p.proname from pg_proc p join pg_namespace n on n.oid=p.pronamespace where n.nspname='public' and p.proname like 'conso\_%' escape '\' loop
  execute format('revoke all on function %s from public,anon,authenticated',f.signature);
  if f.proname=any(array['conso_identity','conso_open_session','conso_get_run','conso_claim_run','conso_save_run','conso_restart','conso_touch','conso_close_session','conso_dashboard','conso_archived_runs','conso_reserve_mail','conso_mark_mail','conso_mails']) then
   execute format('grant execute on function %s to authenticated',f.signature);
  end if;
 end loop;
end $$;
grant execute on function public.conso_can_login(text,text) to anon,authenticated;
notify pgrst,'reload schema';
commit;
