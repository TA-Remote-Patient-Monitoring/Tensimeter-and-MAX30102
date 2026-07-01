from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "sqlite:///./omron.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    pool_size=40,
    max_overflow=60,
    pool_timeout=30,
    pool_recycle=3600,
    pool_pre_ping=True,
)


@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """
    Optimasi SQLite PRAGMA untuk performa tinggi di bawah beban concurrent.
    Dijalankan sekali setiap kali koneksi baru dibuat dari pool.
    """
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")        # concurrent read/write
    cursor.execute("PRAGMA synchronous=NORMAL")      # balance safety vs speed
    cursor.execute("PRAGMA cache_size=-64000")       # 64MB cache (default 2MB)
    cursor.execute("PRAGMA busy_timeout=10000")      # retry 10s saat lock
    cursor.execute("PRAGMA temp_store=MEMORY")       # temp tables di RAM
    cursor.execute("PRAGMA mmap_size=268435456")     # memory-mapped I/O 256MB
    cursor.execute("PRAGMA read_uncommitted=1")      # kurangi lock contention reads
    cursor.execute("PRAGMA wal_autocheckpoint=1000") # checkpoint setiap 1000 pages
    cursor.close()


SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()