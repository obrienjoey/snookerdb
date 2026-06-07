# SnookerDB Examples

This directory contains example Python scripts to help you get started querying and analyzing the SnookerDB database.

## Contents

1. **[`basic_queries.py`](file:///c:/Users/joeyobrien/Github/Projects/snookerdb/Examples/basic_queries.py)**
   - Shows how to connect to the SQLite database (`Database/snookerdb.db`) using the Python standard library `sqlite3` module.
   - Demonstrates typical queries: retrieving a player profile, pulling head-to-head records, and finding tournament winners.

2. **[`pandas_analytics.py`](file:///c:/Users/joeyobrien/Github/Projects/snookerdb/Examples/pandas_analytics.py)**
   - Demonstrates loading the Parquet files (`Parquet/*.parquet`) or SQLite tables into Pandas DataFrames for analytics.
   - Calculates career metrics: total wins, win percentages, highest break builders, century break statistics, and rankings progression.

## Setup & Running the Examples

### Prerequisites

Ensure you have installed the project requirements:
```bash
pip install -r requirements.txt
```

If you haven't initialized or downloaded the database, run:
```bash
python Code/initialize_db.py
```
*(Alternatively, check the `Database/` directory to ensure `snookerdb.db` is present.)*

### Run from Command Line

To run the basic SQLite queries:
```bash
python Examples/basic_queries.py
```

To run the Pandas analytics script:
```bash
python Examples/pandas_analytics.py
```

### Using with Jupyter Notebooks

If you prefer to work interactively in Jupyter, you can launch a Jupyter server and import the code snippets or use the same connections:

```python
import sqlite3
import pandas as pd

# Connect to database
conn = sqlite3.connect("Database/snookerdb.db")

# Load any table into a DataFrame
df_players = pd.read_sql_query("SELECT * FROM players", conn)
print(df_players.head())
```
