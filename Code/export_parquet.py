"""Database to Parquet Export Ingestion Script.

This script exports SQLite database tables (`players`, `tournament`, `matches`)
into stably sorted Parquet format. Sorting by keys prevents noisy git diff changes
on subsequent pipeline runs.
"""

import logging
import sqlite3
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

# Configure logging
logger = logging.getLogger("snookerdb")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

# Set up paths relative to this file
base_dir = Path(__file__).resolve().parent.parent
db_path = base_dir / "Database" / "snookerdb.db"
parquet_dir = base_dir / "Parquet"

# Ensure directories exist
parquet_dir.mkdir(parents=True, exist_ok=True)


def sql_to_pq(table: str, conn: sqlite3.Connection):
    """Reads SQLite database table with stable sorting and writes to Parquet.

    Args:
        table: The SQLite table name (e.g. 'players').
        conn: The active sqlite3 Connection object.
    """
    # Use stable sorting to avoid unnecessary git diffs
    if table == "players":
        query = "SELECT * from players ORDER BY surname, first_name, url"
    elif table == "tournament":
        query = "SELECT * from tournament ORDER BY CAST(tourn_id AS INTEGER)"
    elif table == "matches":
        query = "SELECT * from matches ORDER BY CAST(match_id AS INTEGER)"
    elif table == "frames":
        query = "SELECT * from frames ORDER BY CAST(match_id AS INTEGER), frame_num"
    elif table == "breaks":
        query = "SELECT * from breaks ORDER BY CAST(match_id AS INTEGER), frame_num, player_number, points DESC"
    else:
        query = f"SELECT * from {table}"

    df = pd.read_sql_query(query, conn)
    pq_table = pa.Table.from_pandas(df)

    output_path = parquet_dir / f"{table}.parquet"
    pq.write_table(pq_table, str(output_path))
    logger.info(f"Table {table} written to: {output_path}")


logger.info(f"Connecting to database to export Parquet: {db_path}")
with sqlite3.connect(db_path) as conn:
    tables = ["players", "tournament", "matches", "frames", "breaks"]
    for table in tables:
        sql_to_pq(table, conn)
