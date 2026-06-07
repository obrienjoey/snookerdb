"""Nightly Incremental Update Ingestion Script.

This script executes incremental updates for the SnookerDB data pipeline. It:
1. Resolves seasonal tournament lists (falling back to the previous season if needed).
2. Scrapes match details for the latest tournament list.
3. Performs optimized player scraping by checking new matches for unregistered player profiles.
4. Conducts database updates transactionally using incremental appends (`if_exists="append"`).
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

# Ensure directories exist
db_path.parent.mkdir(parents=True, exist_ok=True)

# 1. Open database connection and apply schema if tables don't exist
logger.info(f"Connecting to database at: {db_path}")
with sqlite3.connect(db_path) as conn:
    with open(schema_path, "r") as f:
        schema_sql = f.read()
    conn.executescript(schema_sql)
    conn.commit()

    # Apply missing columns for migration
    try:
        conn.execute("ALTER TABLE matches ADD COLUMN winner TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE matches ADD COLUMN winner_url TEXT")
    except sqlite3.OperationalError:
        pass

    for col in ["venue", "city", "country", "sponsor", "prize_fund", "start_date", "end_date"]:
        try:
            conn.execute(f"ALTER TABLE tournament ADD COLUMN {col} TEXT")
        except sqlite3.OperationalError:
            pass
    conn.commit()

# 2. Fetch tournament urls and scrape
logger.info("Scraping season and tournament list...")
season_urls = scraper.season_urls()
if not season_urls:
    raise RuntimeError("No season URLs retrieved. Scraping aborted.")

check_season = season_urls[0]
tourn_df = pd.DataFrame(scraper.tournament_urls(check_season))

# If no tournaments in current season, fallback to previous season
if len(tourn_df) == 0:
    logger.info("No tournaments found for current season. Checking previous season...")
    tourn_df = pd.DataFrame(scraper.tournament_urls(season_urls[1]))

if len(tourn_df) == 0:
    raise RuntimeError("No tournaments found for current or previous season. Scraping aborted.")

# 3. Read existing data to compare and only fetch/insert new records
with sqlite3.connect(db_path) as conn:
    local_match_df = pd.read_sql_query("SELECT * from matches", conn)
    local_tourn_df = pd.read_sql_query("SELECT * from tournament", conn)
    local_player_df = pd.read_sql_query("SELECT * from players", conn)

# Normalize/cast existing IDs to ensure proper comparison
local_match_ids = set(local_match_df["match_id"].astype(str))
local_tourn_ids = set(local_tourn_df["tourn_id"].astype(str))
local_player_urls = set(local_player_df["url"].str.lower())

# Identify completed tournaments (those with a Final match that has a result)
completed_tourn_ids = set(
    local_match_df[
        (local_match_df["stage"] == "Final") & (local_match_df["scores"].notna() | (local_match_df["walkover"] == 1))
    ]["tourn_id"].astype(str)
)

# Filter tournaments: only scrape if they are new or not completed
active_tourn_df = tourn_df[~tourn_df["tourn_id"].astype(str).isin(completed_tourn_ids)]

if len(active_tourn_df) > 0:
    logger.info(f"Scraping matches for {len(active_tourn_df)} active tournaments...")
    match_data = scraper.matches_scrape(active_tourn_df["url"])
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
            "winner",
            "winner_url",
        ],
    )
else:
    logger.info("No active tournaments to scrape matches for.")
    match_df = pd.DataFrame(
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
            "winner",
            "winner_url",
        ]
    )

# Identify new tournaments and matches
new_tourn_df = tourn_df[~tourn_df["tourn_id"].astype(str).isin(local_tourn_ids)]
new_match_df = match_df[~match_df["match_id"].astype(str).isin(local_match_ids)]

logger.info(f"Scraped matches contain {len(new_match_df)} new matches and {len(new_tourn_df)} new tournaments.")

# 4. Optimize player scraping: only scrape listing pages for new players
# We ONLY check for missing players in newly scraped matches to avoid infinite loops on unlisted amateurs
new_player_candidates = []
for idx, row in new_match_df.iterrows():
    if row["player_1_url"]:
        new_player_candidates.append((row["player_1"], row["player_1_url"]))
    if row["player_2_url"]:
        new_player_candidates.append((row["player_2"], row["player_2_url"]))

new_player_candidates = list(set(new_player_candidates))
missing_players = [(name, url) for name, url in new_player_candidates if url.lower() not in local_player_urls]

player_df = pd.DataFrame(columns=["url", "first_name", "surname", "nationality"])
if missing_players:
    logger.info(f"Found {len(missing_players)} players in new matches not present in database.")
    # Determine the initials to scrape
    initials_to_scrape = set()
    for name, url in missing_players:
        name_parts = name.strip().split()
        if name_parts:
            # Match by last word in name (surname)
            initial = name_parts[-1][0].lower()
            if initial in string.ascii_lowercase:
                initials_to_scrape.add(initial)
            else:
                initial = name_parts[0][0].lower()
                if initial in string.ascii_lowercase:
                    initials_to_scrape.add(initial)

    if initials_to_scrape:
        logger.info(f"Scraping player listing pages for initials: {list(initials_to_scrape)}")
        scraped_players = scraper.player_details(list(initials_to_scrape), error_log=False)
        player_df = pd.DataFrame(scraped_players)

# Normalize scraped players to filter out any that might have been added concurrently
new_player_df = player_df[~player_df["url"].str.lower().isin(local_player_urls)]

# 5. Insert new records incrementally within a transaction context manager
with sqlite3.connect(db_path) as conn:
    if len(new_player_df) > 0:
        logger.info(f"Inserting {len(new_player_df)} new players...")
        new_player_df.to_sql("players", conn, if_exists="append", index=False)

    if len(new_tourn_df) > 0:
        logger.info(f"Inserting {len(new_tourn_df)} new tournaments...")
        # Make sure tourn_id is numeric
        new_tourn_df = new_tourn_df.copy()
        new_tourn_df["tourn_id"] = pd.to_numeric(new_tourn_df["tourn_id"])
        new_tourn_df.to_sql("tournament", conn, if_exists="append", index=False)

    if len(new_match_df) > 0:
        logger.info(f"Inserting {len(new_match_df)} new matches...")
        new_match_df = new_match_df.copy()
        new_match_df["match_id"] = pd.to_numeric(new_match_df["match_id"])
        new_match_df.to_sql("matches", conn, if_exists="append", index=False)
        logger.info("Database update successful.")

        logger.info(f"Parsing frames and breaks for {len(new_match_df)} new matches...")
        new_frames = []
        new_breaks = []
        for idx, row in new_match_df.iterrows():
            f, b = scraper.parse_frames_and_breaks(row["match_id"], row["scores"])
            new_frames.extend(f)
            new_breaks.extend(b)

        if new_frames:
            logger.info(f"Inserting {len(new_frames)} new frames...")
            pd.DataFrame(new_frames).to_sql("frames", conn, if_exists="append", index=False)
        if new_breaks:
            logger.info(f"Inserting {len(new_breaks)} new breaks...")
            pd.DataFrame(new_breaks).to_sql("breaks", conn, if_exists="append", index=False)
    else:
        logger.info("No new matches to add.")

    # Backfill frames and breaks for existing matches missing from the frames table
    try:
        local_frames_df = pd.read_sql_query("SELECT DISTINCT match_id FROM frames", conn)
        local_frames_match_ids = set(local_frames_df["match_id"].astype(str))
    except sqlite3.OperationalError:
        # If frames table is completely empty or just created, it might cause an issue.
        local_frames_match_ids = set()

    missing_frames_matches = local_match_df[~local_match_df["match_id"].astype(str).isin(local_frames_match_ids)]

    missing_frames_matches = missing_frames_matches[
        missing_frames_matches["scores"].notna()
        & (missing_frames_matches["scores"] != "")
        & (~missing_frames_matches["scores"].str.contains("Walkover", na=False))
    ]

    if len(missing_frames_matches) > 0:
        logger.info(f"Backfilling frames for {len(missing_frames_matches)} historical matches...")
        backfill_frames = []
        backfill_breaks = []

        # To avoid massive memory usage, we could chunk it, but the total number of matches is ~100k,
        # frames list might be up to 1M rows. Let's do it in one go for now, or chunk by 10k matches.
        for idx, row in missing_frames_matches.iterrows():
            f, b = scraper.parse_frames_and_breaks(row["match_id"], row["scores"])
            backfill_frames.extend(f)
            backfill_breaks.extend(b)

        if backfill_frames:
            logger.info(f"Inserting {len(backfill_frames)} backfilled frames...")
            pd.DataFrame(backfill_frames).to_sql("frames", conn, if_exists="append", index=False)
        if backfill_breaks:
            logger.info(f"Inserting {len(backfill_breaks)} backfilled breaks...")
            pd.DataFrame(backfill_breaks).to_sql("breaks", conn, if_exists="append", index=False)
        logger.info("Backfill complete.")
    else:
        logger.info("No historical matches require frame backfilling.")

    # 6. Backfill Winner Data
    matches_needing_winners = pd.read_sql_query(
        "SELECT match_id, player_1_score, player_2_score, player_1, player_1_url, "
        "player_2, player_2_url, walkover FROM matches WHERE winner IS NULL AND "
        "(player_1_score IS NOT NULL OR walkover = 1)",
        conn,
    )
    if len(matches_needing_winners) > 0:
        logger.info(f"Backfilling winners for {len(matches_needing_winners)} matches...")
        updates = []
        for row in matches_needing_winners.to_dict("records"):
            w, w_url = None, None
            try:
                if row["walkover"] == 1:
                    p1 = row["player_1"] or ""
                    p2 = row["player_2"] or ""
                    if "Walkover" in p1:
                        w, w_url = p1.replace(" (Walkover)", ""), row["player_1_url"]
                    elif "Walkover" in p2:
                        w, w_url = p2.replace(" (Walkover)", ""), row["player_2_url"]
                else:
                    p1_s, p2_s = row["player_1_score"], row["player_2_score"]
                    if pd.notna(p1_s) and pd.notna(p2_s):
                        if p1_s > p2_s:
                            w, w_url = row["player_1"], row["player_1_url"]
                        elif p2_s > p1_s:
                            w, w_url = row["player_2"], row["player_2_url"]
                if w is not None:
                    updates.append((w, w_url, row["match_id"]))
            except Exception:
                pass
        if updates:
            conn.executemany("UPDATE matches SET winner = ?, winner_url = ? WHERE match_id = ?", updates)
            conn.commit()

    # 7. Backfill Match Dates to ISO 8601
    matches_needing_dates = pd.read_sql_query("SELECT match_id, date FROM matches WHERE date LIKE '% %'", conn)
    if len(matches_needing_dates) > 0:
        logger.info(f"Backfilling ISO dates for {len(matches_needing_dates)} matches...")
        updates = []
        for row in matches_needing_dates.to_dict("records"):
            d = scraper.parse_date_to_iso(row["date"])
            if d:
                updates.append((d, row["match_id"]))
        if updates:
            conn.executemany("UPDATE matches SET date = ? WHERE match_id = ?", updates)
            conn.commit()

    # 8. Backfill Tournament Start/End Dates
    tournaments_needing_dates = pd.read_sql_query(
        "SELECT tourn_id, dates FROM tournament WHERE start_date IS NULL AND dates IS NOT NULL", conn
    )
    if len(tournaments_needing_dates) > 0:
        logger.info(f"Backfilling start/end dates for {len(tournaments_needing_dates)} tournaments...")
        updates = []
        for row in tournaments_needing_dates.to_dict("records"):
            sd, ed = scraper.parse_tournament_dates(row["dates"])
            if sd or ed:
                updates.append((sd, ed, row["tourn_id"]))
        if updates:
            conn.executemany("UPDATE tournament SET start_date = ?, end_date = ? WHERE tourn_id = ?", updates)
            conn.commit()

    # 9. Backfill Tournament Metadata (Venue, Prize etc.)
    tournaments_needing_metadata = pd.read_sql_query(
        "SELECT tourn_id, url FROM tournament WHERE venue IS NULL AND city IS NULL", conn
    )
    if len(tournaments_needing_metadata) > 0:
        logger.info(
            f"Backfilling metadata for {len(tournaments_needing_metadata)} tournaments. This may take a while..."
        )
        updates = []
        for idx, row in enumerate(tournaments_needing_metadata.to_dict("records")):
            url = row["url"]
            try:
                html = scraper.fetch_html(url)
                details = scraper.parse_tournament_details(html)
                updates.append(
                    (
                        details.get("venue"),
                        details.get("city"),
                        details.get("country"),
                        details.get("sponsor"),
                        details.get("prize_fund"),
                        row["tourn_id"],
                    )
                )
            except Exception:
                pass
            import time

            time.sleep(0.3)
            if idx % 50 == 0 and idx > 0:
                logger.info(f"Backfilled {idx}/{len(tournaments_needing_metadata)} tournaments...")

        if updates:
            conn.executemany(
                "UPDATE tournament SET venue = ?, city = ?, country = ?, "
                "sponsor = ?, prize_fund = ? WHERE tourn_id = ?",
                updates,
            )
            conn.commit()
