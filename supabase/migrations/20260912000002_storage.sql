-- Storage buckets + object-level access.
-- 'uploads'  : user uploads (dirty CSVs)
-- 'outputs'  : harmonized CSV / JSON report artifacts produced by jobs

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values
  ('uploads', 'uploads', false, 10485760, array['text/csv', 'application/vnd.ms-excel', 'application/json']),
  ('outputs', 'outputs', false, 10485760, array['text/csv', 'application/json', 'image/png'])
on conflict (id) do nothing;

create policy "users can read own uploads"
  on storage.objects for select to authenticated
  using (bucket_id = 'uploads' and owner = auth.uid());

create policy "users can upload to uploads"
  on storage.objects for insert to authenticated
  with check (bucket_id = 'uploads' and owner = auth.uid());

create policy "users can update own uploads"
  on storage.objects for update to authenticated
  using (bucket_id = 'uploads' and owner = auth.uid());

create policy "users can delete own uploads"
  on storage.objects for delete to authenticated
  using (bucket_id = 'uploads' and owner = auth.uid());

create policy "users can read own outputs"
  on storage.objects for select to authenticated
  using (bucket_id = 'outputs' and owner = auth.uid());

create policy "users can write own outputs"
  on storage.objects for insert to authenticated
  with check (bucket_id = 'outputs' and owner = auth.uid());

create policy "users can update own outputs"
  on storage.objects for update to authenticated
  using (bucket_id = 'outputs' and owner = auth.uid());

create policy "users can delete own outputs"
  on storage.objects for delete to authenticated
  using (bucket_id = 'outputs' and owner = auth.uid());