import pytest
import responses
import pandas as pd
import sqlite3
import scraper as snooker

@responses.activate
def test_scraping_and_db_e2e(temp_db, load_fixture):
    """
    Mock the CueTracker endpoints and test the full scraper pipeline.
    """
    # Mock HTTP requests
    responses.add(
        responses.GET,
        'https://cuetracker.net/seasons',
        body=load_fixture("seasons_page.html"),
        status=200
    )
    responses.add(
        responses.GET,
        'https://cuetracker.net/seasons/2026-2027',
        body=load_fixture("tournament_page.html"),
        status=200
    )
    responses.add(
        responses.GET,
        'https://cuetracker.net/tournaments/world-championship/2026/1234',
        body=load_fixture("match_page.html"),
        status=200
    )
    responses.add(
        responses.GET,
        'https://cuetracker.net/players/t',
        body=load_fixture("players_page.html"),
        status=200
    )
    responses.add(
        responses.GET,
        'https://cuetracker.net/players/s',
        body='<table></table>',
        status=200
    )
    
    # 1. Seasons
    seasons = snooker.season_urls()
    assert len(seasons) == 2
    
    # 2. Tournaments
    tourn_list = snooker.tournament_urls(seasons[0])
    assert len(tourn_list) == 1
    
    # 3. Matches
    match_list = snooker.matches_scrape(tourn_list[0]['url'])
    assert len(match_list) == 2
    
    # 4. Save to in-memory DB
    tourn_df = pd.DataFrame(tourn_list)
    match_df = pd.DataFrame(match_list, columns = ['tourn_id', 'match_id', 'date', 'stage', 'best_of', 
                                                   'player_1_score', 'player_2_score','player_1', 'player_1_url', 
                                                   'player_2', 'player_2_url', 'scores', 'walkover'])
    
    # Mock player details list
    player_list = snooker.player_details(['t'])
    player_df = pd.DataFrame(player_list)
    
    with sqlite3.connect(temp_db) as conn:
        tourn_df.to_sql("tournament", conn, if_exists="append", index=False)
        match_df.to_sql("matches", conn, if_exists="append", index=False)
        player_df.to_sql("players", conn, if_exists="append", index=False)
        
        # Verify db counts
        tourn_res = pd.read_sql_query("SELECT * FROM tournament", conn)
        assert len(tourn_res) == 1
        
        match_res = pd.read_sql_query("SELECT * FROM matches", conn)
        assert len(match_res) == 2
        
        player_res = pd.read_sql_query("SELECT * FROM players", conn)
        assert len(player_res) == 2
