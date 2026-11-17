-- Ejecutar mediante create_qr_user.sh con un administrador PostgreSQL.
-- No cambia contraseñas de usuarios existentes ni elimina datos.
\getenv qr_password QR_DB_PASSWORD
SELECT format('CREATE ROLE qr_user LOGIN PASSWORD %L', :'qr_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'qr_user')
\gexec
SELECT 'CREATE DATABASE qr_produccion OWNER qr_user'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'qr_produccion')
\gexec
