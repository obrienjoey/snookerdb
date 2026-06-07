#!/usr/bin/env python3
"""
basic_queries.py

An example script showing how to connect to the SnookerDB SQLite database
and run standard SQL queries to extract players, matches, head-to-head records,
and tournament winners.
"""

import os
import sqlite3


def get_db_connection():
    # Resolve the path to Database/snookerdb.db relative to this script
    script_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(script_dir, "..", "Database", "snookerdb.db")

    if not os.path.exists(db_path):
        raise FileNotFoundError(
            f"Database not found at {os.path.abspath(db_path)}.\n"
            "Please run 'python Code/initialize_db.py' or check the file location."
        )

    return sqlite3.connect(db_path)


def normalize_url(url_or_slug):
    url_or_slug = url_or_slug.strip().lower()
    if not url_or_slug.startswith("http"):
        return f"https://cuetracker.net/players/{url_or_slug}"
    return url_or_slug.replace("/players/", "/players/")


def query_player_profile(conn, surname_query):
    print(f"\n--- Player Search for '{surname_query}' ---")
    cursor = conn.cursor()

    query = """
        SELECT first_name, surname, nationality, url
        FROM players
        WHERE surname LIKE ? OR first_name LIKE ?
    """
    cursor.execute(query, (f"%{surname_query}%", f"%{surname_query}%"))
    players = cursor.fetchall()

    if not players:
        print("No players found.")
        return

    for first_name, surname, nationality, url in players:
        print(f"Name: {first_name} {surname}")
        print(f"  Nationality: {nationality}")
        print(f"  CueTracker URL: {url}")
        print("-" * 30)


def query_head_to_head(conn, player_1_url_or_slug, player_2_url_or_slug):
    p1_url = normalize_url(player_1_url_or_slug)
    p2_url = normalize_url(player_2_url_or_slug)

    print(f"\n--- Head-to-Head: {p1_url} vs {p2_url} ---")
    cursor = conn.cursor()

    # Check total matches played (using case-insensitive comparison or LOWER() since DB might have casing variations)
    query = """
        SELECT
            COUNT(*) as total_played,
            SUM(CASE WHEN LOWER(winner_url) = ? THEN 1 ELSE 0 END) as p1_wins,
            SUM(CASE WHEN LOWER(winner_url) = ? THEN 1 ELSE 0 END) as p2_wins
        FROM matches
        WHERE
            (LOWER(player_1_url) = ? AND LOWER(player_2_url) = ?)
            OR (LOWER(player_1_url) = ? AND LOWER(player_2_url) = ?)
    """
    cursor.execute(query, (
        p1_url, p2_url,
        p1_url, p2_url,
        p2_url, p1_url
    ))

    row = cursor.fetchone()
    if not row or row[0] == 0:
        print("No matches recorded between these two players.")
        return

    total, p1_wins, p2_wins = row
    print(f"Total Matches Played: {total}")
    print(f"  {p1_url} Wins: {p1_wins} ({p1_wins/total*100:.1f}%)")
    print(f"  {p2_url} Wins: {p2_wins} ({p2_wins/total*100:.1f}%)")

    # List the last 5 matches
    print("\nLast 5 Match Details:")
    detail_query = """
        SELECT m.date, t.name, m.stage, m.player_1, m.player_1_score, m.player_2_score, m.player_2, m.winner
        FROM matches m
        JOIN tournament t ON m.tourn_id = t.tourn_id
        WHERE
            (LOWER(m.player_1_url) = ? AND LOWER(m.player_2_url) = ?)
            OR (LOWER(m.player_1_url) = ? AND LOWER(m.player_2_url) = ?)
        ORDER BY m.date DESC, m.match_id DESC
        LIMIT 5
    """
    cursor.execute(detail_query, (
        p1_url, p2_url,
        p2_url, p1_url
    ))

    for row in cursor.fetchall():
        date, tourn_name, stage, p1, p1_score, p2_score, p2, winner = row
        print(f"  [{date}] {tourn_name} ({stage}): {p1} {p1_score} - {p2_score} {p2} (Winner: {winner})")


def query_tournament_history(conn, tournament_name):
    print(f"\n--- Tournament Winners for '{tournament_name}' ---")
    cursor = conn.cursor()

    query = """
        SELECT t.season, t.name, m.winner, m.player_1, m.player_1_score, m.player_2_score, m.player_2
        FROM matches m
        JOIN tournament t ON m.tourn_id = t.tourn_id
        WHERE t.name LIKE ? AND m.stage = 'Final'
        ORDER BY t.season DESC
    """
    cursor.execute(query, (f"%{tournament_name}%",))
    finals = cursor.fetchall()

    if not finals:
        print("No finals found for this tournament.")
        return

    for season, name, winner, p1, p1_score, p2_score, p2 in finals:
        print(f"  Season {season} | {name}:")
        print(f"    Winner: {winner} (Final Score: {p1} {p1_score} - {p2_score} {p2})")


def main():
    try:
        conn = get_db_connection()
        print("Successfully connected to SnookerDB SQLite Database.")

        # 1. Search for a player
        query_player_profile(conn, "O'Sullivan")

        # 2. Query a head-to-head matchup
        # Common slugs: ronnie-osullivan, judd-trump, john-higgins, mark-selby
        query_head_to_head(conn, "ronnie-osullivan", "judd-trump")

        # 3. Query historical finals for a tournament
        query_tournament_history(conn, "Masters")

        conn.close()
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
