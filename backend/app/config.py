DB_USER = "qr_user"
DB_PASS = "Nomeacuerd0"
DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "qr_produccion"

DATABASE_URL = (
    f"postgresql+psycopg2://{DB_USER}:{DB_PASS}"
    f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

SECRET_KEY = b"CAMBIAR_CLAVE_SECRETA"
