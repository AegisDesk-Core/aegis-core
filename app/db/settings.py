import os

from dotenv import load_dotenv

load_dotenv()


DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
	database_host = os.getenv("POSTGRES_HOST") or os.getenv("host", "localhost")
	database_port = os.getenv("POSTGRES_PORT") or os.getenv("port", "5432")
	database_name = os.getenv("POSTGRES_DB") or os.getenv("dbname", "customer_support")
	database_user = os.getenv("POSTGRES_USER") or os.getenv("user", "postgres")
	database_password = os.getenv("POSTGRES_PASSWORD") or os.getenv("password")
	if not database_password:
		raise RuntimeError(
			"Set DATABASE_URL or POSTGRES_PASSWORD in .env before starting the application."
		)
	DATABASE_URL = (
		f"postgresql://{database_user}:{database_password}@"
		f"{database_host}:{database_port}/{database_name}"
	)
DB_MIN_SIZE = int(os.getenv("DB_MIN_SIZE", "1"))
DB_MAX_SIZE = int(os.getenv("DB_MAX_SIZE", "10"))
DB_TIMEOUT = float(os.getenv("DB_TIMEOUT", "10"))
