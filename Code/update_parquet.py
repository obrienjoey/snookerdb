import sqlite3
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

conn = sqlite3.connect("Database\snookerdb.db")

def sql_to_pq(table, conn):
    """
    reads the tables from the SQLite database and writes
    them to an equivalent parquet file
    """
    df = pd.read_sql_query(f"SELECT * from {table}", conn)
    pq_table = pa.Table.from_pandas(df)
    pq.write_table(pq_table, f'Parquet/{table}.parquet')

tables = ['players', 'tournament', 'matches']
for table in tables:
    sql_to_pq(table, conn)
    print(f"Table {table} written to Parquet")