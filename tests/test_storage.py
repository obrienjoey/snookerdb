import sqlite3

import pandas as pd


def test_sqlite_insert_and_queries(temp_db):
    """
    Test that we can insert records into pre-created tables and query them back.
    """
    players_data = [
        {
            "url": "https://cuetracker.net/players/judd-trump",
            "first_name": "Judd",
            "surname": "Trump",
            "nationality": "England",
        },
        {
            "url": "https://cuetracker.net/players/mark-selby",
            "first_name": "Mark",
            "surname": "Selby",
            "nationality": "England",
        },
    ]
    player_df = pd.DataFrame(players_data)

    tournaments_data = [
        {
            "tourn_id": 1234,
            "url": "https://cuetracker.net/tournaments/world-championship/2026/1234",
            "dates": "01 Jun to 05 Jun 2026",
            "name": "World Championship",
            "season": "2026-2027",
            "category": "Professional",
        }
    ]
    tourn_df = pd.DataFrame(tournaments_data)

    matches_data = [
        [
            1234,
            9999,
            "05 Jun 2026",
            "Final",
            19,
            10,
            8,
            "Judd Trump",
            "https://cuetracker.net/players/judd-trump",
            "Mark Selby",
            "https://cuetracker.net/players/mark-selby",
            "100-0, 50-80",
            0,
            "Judd Trump",
            "https://cuetracker.net/players/judd-trump",
        ]
    ]
    match_df = pd.DataFrame(
        matches_data,
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

    with sqlite3.connect(temp_db) as conn:
        # Insert
        player_df.to_sql("players", conn, if_exists="append", index=False)
        tourn_df.to_sql("tournament", conn, if_exists="append", index=False)
        match_df.to_sql("matches", conn, if_exists="append", index=False)

        # Verify players
        res_players = pd.read_sql_query("SELECT * FROM players ORDER BY surname", conn)
        assert len(res_players) == 2
        assert res_players.iloc[0]["surname"] == "Selby"
        assert res_players.iloc[1]["surname"] == "Trump"

        # Verify tournaments types
        res_tourn = pd.read_sql_query("SELECT * FROM tournament", conn)
        assert len(res_tourn) == 1
        assert res_tourn.iloc[0]["tourn_id"] == 1234  # Should be parsed as int, not text

        # Verify matches types and relations
        res_matches = pd.read_sql_query("SELECT * FROM matches", conn)
        assert len(res_matches) == 1
        assert res_matches.iloc[0]["match_id"] == 9999
        assert res_matches.iloc[0]["walkover"] == 0
        assert res_matches.iloc[0]["date"] == "05 Jun 2026"

        # Rankings insertion and verification
        rankings_data = [
            {
                "season": "2026-2027",
                "player_name": "Judd Trump",
                "player_url": "https://cuetracker.net/players/judd-trump",
                "start_position": 4,
                "start_points": 556000,
                "difference": 3,
                "finish_position": 1,
                "finish_points": 1984200,
            }
        ]
        rankings_df = pd.DataFrame(rankings_data)
        rankings_df.to_sql("rankings", conn, if_exists="append", index=False)

        res_rankings = pd.read_sql_query("SELECT * FROM rankings", conn)
        assert len(res_rankings) == 1
        assert res_rankings.iloc[0]["season"] == "2026-2027"
        assert res_rankings.iloc[0]["player_name"] == "Judd Trump"
        assert res_rankings.iloc[0]["start_position"] == 4
        assert res_rankings.iloc[0]["finish_points"] == 1984200

