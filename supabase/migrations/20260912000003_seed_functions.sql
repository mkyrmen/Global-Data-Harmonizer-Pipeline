-- Seed helper: scaffolds a demo workspace for a user.
-- Designed to be called by the backend once the two demo CSV files have been
-- uploaded to Storage under `uploads/<uid>/...`.

create or replace function public.seed_demo_workspace(p_owner uuid, p_names text[])
returns uuid
language plpgsql
security definer set search_path = public
as $$
declare
  v_workspace uuid;
  v_source    uuid;
  v_name      text;
begin
  insert into public.workspaces (owner_id, name, description)
  values (p_owner, 'Demo Workspace', 'Harmonizes the two bundled demo sources.')
  returning id into v_workspace;

  foreach v_name in array p_names loop
    insert into public.raw_sources (owner_id, workspace_id, name, storage_path)
    values (p_owner, v_workspace, v_name, format('uploads/%s/%s', p_owner, v_name))
    returning id into v_source;

    insert into public.workspace_sources (workspace_id, source_id, include, sort_order)
    select v_workspace, id, true, row_number() over (order by created_at) - 1
    from public.raw_sources
    where workspace_id = v_workspace;
  end loop;

  return v_workspace;
end;
$$;

revoke all on function public.seed_demo_workspace(uuid, text[]) from public;
grant execute on function public.seed_demo_workspace(uuid, text[]) to service_role;