import os
import re
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./nutriperu.db")

# Render usa "postgres://" pero SQLAlchemy requiere "postgresql://"
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Log de diagnóstico (password enmascarada) — visible en Render logs
_masked = re.sub(r"://([^:]+):([^@]+)@", r"://\1:***@", DATABASE_URL)
if DATABASE_URL.startswith("sqlite"):
    print(f"[db] WARNING: usando SQLite efímero ({_masked}). DATABASE_URL no está configurada.", flush=True)
else:
    print(f"[db] Conectando a Postgres externa: {_masked}", flush=True)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
# pool_pre_ping para Neon: detecta conexiones muertas tras auto-suspend
engine_kwargs = {"connect_args": connect_args}
if not DATABASE_URL.startswith("sqlite"):
    engine_kwargs["pool_pre_ping"] = True
engine = create_engine(DATABASE_URL, **engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
