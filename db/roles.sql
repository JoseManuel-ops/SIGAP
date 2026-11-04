-- Roles de SIGAP en app_metadata (solo el servidor puede modificarlo; user_metadata lo edita el usuario).
-- Los usuarios se crean en Supabase Auth. El rol entra en el token en el siguiente inicio de sesión.
update auth.users
set raw_app_meta_data = coalesce(raw_app_meta_data, '{}'::jsonb) || jsonb_build_object(
  'role',
  case email when 'admin@sigap.demo' then 'admin' when 'operario@sigap.demo' then 'operario' end
)
where email in ('admin@sigap.demo', 'operario@sigap.demo');
