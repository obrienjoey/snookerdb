import sqlite3

import pandas as pd
import responses
import scraper as snooker


@responses.activate
def test_scraping_and_db_e2e(temp_db, load_fixture):
    """
    Mock the CueTracker endpoints and test the full scraper pipeline.
    """
    # Mock HTTP requests
    responses.add(responses.GET, "https://cuetracker.net/seasons", body=load_fixture("seasons_page.html"), status=200)
    responses.add(
        responses.GET, "https://cuetracker.net/seasons/2026-2027", body=load_fixture("tournament_page.html"), status=200
    )
    responses.add(
        responses.GET,
        "https://cuetracker.net/tournaments/world-championship/2026/1234",
        body=load_fixture("match_page.html"),
        status=200,
    )
    responses.add(responses.GET, "https://cuetracker.net/players/t", body=load_fixture("players_page.html"), status=200)
    responses.add(responses.GET, "https://cuetracker.net/players/s", body="<table></table>", status=200)
    responses.add(
        responses.GET,
        "https://cuetracker.net/Rankings/2026-2027",
        body=load_fixture("rankings_page.html"),
        status=200,
    )
    responses.add(
        responses.GET,
        "https://cuetracker.net/Rankings/2025-2026",
        body=load_fixture("rankings_page.html"),
        status=200,
    )

    # 1. Seasons
    seasons = snooker.season_urls()
    assert len(seasons) == 2

    # 2. Tournaments
    tourn_list = snooker.tournament_urls(seasons[0])
    assert len(tourn_list) == 1

    # 3. Matches
    match_list = snooker.matches_scrape(tourn_list[0]["url"])
    assert len(match_list) == 2

    # 4. Rankings
    ranking_seasons = [u.rsplit("/", 1)[-1] for u in seasons]
    ranking_list = snooker.scrape_rankings(ranking_seasons)
    assert len(ranking_list) == 6

    # 5. Save to in-memory DB
    tourn_df = pd.DataFrame(tourn_list)
    match_df = pd.DataFrame(
        match_list,
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
    ranking_df = pd.DataFrame(ranking_list)

    # Mock player details list
    player_list = snooker.player_details(["t"])
    player_df = pd.DataFrame(player_list)

    with sqlite3.connect(temp_db) as conn:
        tourn_df.to_sql("tournament", conn, if_exists="append", index=False)
        match_df.to_sql("matches", conn, if_exists="append", index=False)
        player_df.to_sql("players", conn, if_exists="append", index=False)
        ranking_df.to_sql("rankings", conn, if_exists="append", index=False)

        # Verify db counts
        tourn_res = pd.read_sql_query("SELECT * FROM tournament", conn)
        assert len(tourn_res) == 1

        match_res = pd.read_sql_query("SELECT * FROM matches", conn)
        assert len(match_res) == 2

        player_res = pd.read_sql_query("SELECT * FROM players", conn)
        assert len(player_res) == 2

        ranking_res = pd.read_sql_query("SELECT * FROM rankings", conn)
        assert len(ranking_res) == 6

