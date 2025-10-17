"""
QA: Smoke de conectividad a la base de datos.
Uso dentro del contenedor:
    python backend/scripts/check_db_connectivity.py
"""

import sqlalchemy as sa

from backend.utils.config import Config


def main():
    engine = sa.create_engine(Config.DATABASE_URL, pool_pre_ping=True)
    with engine.connect() as c:
        val = c.execute(sa.text("select 1")).scalar()
        print("db_ok", val)


if __name__ == "__main__":
    main()
