"""Initial Database Ingestion and Schema Initialization.

This script initializes the SnookerDB SQLite database from scratch by applying
the SQL schema, scraping all historical players (A-Z listing), seasons,
tournaments, and match records from CueTracker, and inserting them with correct
datatypes and keys.
"""

import logging
import sqlite3
import string
from pathlib import Path

import pandas as pd
import scraper

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
schema_path = base_dir / "Database" / "schema.sql"

# Ensure target directories exist
db_path.parent.mkdir(parents=True, exist_ok=True)

logger.info(f"Initializing database at: {db_path}")

# Initialize schema within a connection context
with sqlite3.connect(db_path) as conn:
    with open(schema_path, "r") as f:
        schema_sql = f.read()

    cursor = conn.cursor()
    # Dropping existing tables for a clean initial scrape
    cursor.execute("DROP TABLE IF EXISTS matches;")
    cursor.execute("DROP TABLE IF EXISTS tournament;")
    cursor.execute("DROP TABLE IF EXISTS players;")
    cursor.execute("DROP TABLE IF EXISTS rankings;")
    conn.commit()

    # Run the schema creation sql
    conn.executescript(schema_sql)
    conn.commit()

logger.info("Database schema applied successfully. Scraping player details...")
surname_initials = list(string.ascii_lowercase)
player_df = pd.DataFrame(scraper.player_details(surname_initials))

logger.info("Scraping season and tournament details...")
season_urls = scraper.season_urls()
tourn_df = pd.DataFrame(scraper.tournament_urls(season_urls))

logger.info("Scraping match details...")
match_data = scraper.matches_scrape(tourn_df["url"])
match_df = pd.DataFrame(
    match_data,
    columns=[
        "tourn_id",
        "match_id",
        "date",
        "stage",
        "best_of",
        "player_1_score",
        "player_2_score",
        "player_1",
        "player_1_url",
        "player_2",
        "player_2_url",
        "scores",
        "walkover",
    ],
)

logger.info("Scraping ranking details...")
ranking_seasons = [u.rsplit("/", 1)[-1] for u in season_urls]
ranking_data = scraper.scrape_rankings(ranking_seasons)
ranking_df = pd.DataFrame(ranking_data)

logger.info("Writing scraped data to database...")
with sqlite3.connect(db_path) as conn:
    # Use if_exists="append" to insert into pre-created tables matching schema
    player_df.to_sql("players", conn, if_exists="append", index=False)
    tourn_df.to_sql("tournament", conn, if_exists="append", index=False)
    match_df.to_sql("matches", conn, if_exists="append", index=False)
    ranking_df.to_sql("rankings", conn, if_exists="append", index=False)

logger.info("Initial scrape completed successfully and database initialized.")

