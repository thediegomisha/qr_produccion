DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'qr_user') THEN
    CREATE ROLE qr_user LOGIN PASSWORD 'Nomeacuerd0';
  ELSE
    ALTER ROLE qr_user WITH LOGIN PASSWORD 'Nomeacuerd0';
  END IF;
END
$$;

SELECT 'CREATE DATABASE qr_produccion OWNER qr_user'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = 'qr_produccion')
\gexec

GRANT ALL PRIVILEGES ON DATABASE qr_produccion TO qr_user;
