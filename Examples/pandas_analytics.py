#!/usr/bin/env python3
"""
pandas_analytics.py

An example script showing how to load SnookerDB tables (either from SQLite or
Parquet) into Pandas DataFrames and run interesting statistical/analytical queries.
"""

import os
import sqlite3
import pandas as pd


def get_db_path():
    # Resolve the path to Database/snookerdb.db relative to this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(script_dir, "..", "Database", "snookerdb.db")


def load_data_via_sqlite():
    db_path = get_db_path()
    if not os.path.exists(db_path):
        raise FileNotFoundError(
            f"Database not found at {os.path.abspath(db_path)}.\n"
            "Please run 'python Code/initialize_db.py' to generate it."
        )
        
    print(f"Loading tables from SQLite database: {db_path}")
    conn = sqlite3.connect(db_path)
    
    # Load all tables into DataFrames
    players = pd.read_sql_query("SELECT * FROM players", conn)
    tournaments = pd.read_sql_query("SELECT * FROM tournament", conn)
    matches = pd.read_sql_query("SELECT * FROM matches", conn)
    frames = pd.read_sql_query("SELECT * FROM frames", conn)
    breaks = pd.read_sql_query("SELECT * FROM breaks", conn)
    rankings = pd.read_sql_query("SELECT * FROM rankings", conn)
    
    conn.close()
    return players, tournaments, matches, frames, breaks, rankings


def load_data_via_parquet():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    parquet_dir = os.path.join(script_dir, "..", "Parquet")
    
    print(f"Loading datasets from Parquet files in: {parquet_dir}")
    players = pd.read_parquet(os.path.join(parquet_dir, "players.parquet"))
    tournaments = pd.read_parquet(os.path.join(parquet_dir, "tournament.parquet"))
    matches = pd.read_parquet(os.path.join(parquet_dir, "matches.parquet"))
    
    # Optional tables (load if they exist as parquet)
    frames_path = os.path.join(parquet_dir, "frames.parquet")
    breaks_path = os.path.join(parquet_dir, "breaks.parquet")
    rankings_path = os.path.join(parquet_dir, "rankings.parquet")
    
    frames = pd.read_parquet(frames_path) if os.path.exists(frames_path) else pd.DataFrame()
    breaks = pd.read_parquet(breaks_path) if os.path.exists(breaks_path) else pd.DataFrame()
    rankings = pd.read_parquet(rankings_path) if os.path.exists(rankings_path) else pd.DataFrame()
    
    return players, tournaments, matches, frames, breaks, rankings


def run_analytics(players, tournaments, matches, frames, breaks, rankings):
    print("\n=============================================")
    print("           SNOOKERDB ANALYTICS DEMO          ")
    print("=============================================\n")
    
    # Ensure match_id columns are consistently cast to int64 to avoid merge type conflicts
    if not matches.empty:
        matches["match_id"] = matches["match_id"].astype("int64")
    if not breaks.empty:
        breaks["match_id"] = breaks["match_id"].astype("int64")

    # Normalize URL columns to lowercase to prevent casing mismatches on merges
    for df in [players, matches, breaks, rankings]:
        if df is not None and not df.empty:
            for col in ["url", "player_1_url", "player_2_url", "winner_url", "player_url"]:
                if col in df.columns:
                    df[col] = df[col].astype(str).str.lower().str.strip()

    # 1. Top 10 players with most match wins
    print("--- Top 10 Match Winners ---")
    if not matches.empty:
        # Filter out walkovers (walkover can be 1, True, 'True', etc. due to historical/type variations)
        normal_matches = matches[~matches["walkover"].astype(str).str.lower().isin(["1", "true"])]
        
        # Count wins per winner URL
        wins = normal_matches["winner_url"].value_counts().reset_index()
        wins.columns = ["player_url", "match_wins"]
        
        # Merge with player names
        top_winners = wins.merge(players, left_on="player_url", right_on="url")
        top_winners["full_name"] = top_winners["first_name"] + " " + top_winners["surname"]
        
        for idx, row in top_winners.head(10).iterrows():
            print(f"{idx+1}. {row['full_name']} ({row['nationality']}) - {row['match_wins']} wins")
    else:
        print("Matches table is empty.")
    print("-" * 50 + "\n")

    # 2. Most Century Breaks (points >= 100)
    print("--- Top 10 Century Break Builders ---")
    if not breaks.empty and not players.empty:
        centuries = breaks[breaks["points"] >= 100]
        
        # To identify which player built the break:
        # We need to map player_number (1 or 2) to player_1_url or player_2_url in matches
        match_player_map = matches[["match_id", "player_1_url", "player_2_url"]]
        centuries_with_players = centuries.merge(match_player_map, on="match_id")
        
        # Get the URL of the player who made the break
        centuries_with_players["player_url"] = centuries_with_players.apply(
            lambda r: r["player_1_url"] if r["player_number"] == 1 else r["player_2_url"], axis=1
        )
        
        century_counts = centuries_with_players["player_url"].value_counts().reset_index()
        century_counts.columns = ["player_url", "century_count"]
        
        top_centuries = century_counts.merge(players, left_on="player_url", right_on="url")
        top_centuries["full_name"] = top_centuries["first_name"] + " " + top_centuries["surname"]
        
        for idx, row in top_centuries.head(10).iterrows():
            print(f"{idx+1}. {row['full_name']} - {row['century_count']} centuries")
    else:
        print("Breaks or Players table is empty.")
    print("-" * 50 + "\n")

    # 3. Country performance by total match wins
    print("--- Top 5 Nationalities by Match Wins ---")
    if not matches.empty and not players.empty:
        normal_matches = matches[~matches["walkover"].astype(str).str.lower().isin(["1", "true"])]
        match_winners = normal_matches.merge(players, left_on="winner_url", right_on="url")
        country_wins = match_winners["nationality"].value_counts()
        print(country_wins.head(5))
    else:
        print("Matches or Players table is empty.")
    print("-" * 50 + "\n")

    # 4. Historical world ranking progress (e.g. Judd Trump or Ronnie O'Sullivan)
    target_player_url = "https://cuetracker.net/players/judd-trump"
    print(f"--- Season Ranking History for player '{target_player_url}' ---")
    if not rankings.empty:
        player_ranks = rankings[rankings["player_url"] == target_player_url].sort_values(by="season")
        if not player_ranks.empty:
            for _, row in player_ranks.iterrows():
                print(
                    f"Season: {row['season']} | "
                    f"Start Rank: {row['start_position'] if row['start_position'] else 'N/A'} | "
                    f"Finish Rank: {row['finish_position'] if row['finish_position'] else 'N/A'}"
                )
        else:
            print(f"No ranking data found for {target_player_url}")
    else:
        print("Rankings table is empty.")
    print("=" * 45)


def main():
    try:
        # Prefer SQLite since it contains all tables (frames, breaks, rankings)
        players, tournaments, matches, frames, breaks, rankings = load_data_via_sqlite()
        
        # Alternatively, to run with Parquet files:
        # players, tournaments, matches, frames, breaks, rankings = load_data_via_parquet()
        
        run_analytics(players, tournaments, matches, frames, breaks, rankings)
    except Exception as e:
        print(f"Error loading or analyzing data: {e}")


if __name__ == "__main__":
    main()
