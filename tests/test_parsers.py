import pytest
from scraper import parse_player_details, parse_season_urls, parse_tournament_urls, parse_matches

def test_parse_player_details(load_fixture):
    html = load_fixture("players_page.html")
    players = parse_player_details(html)
    
    assert len(players) == 2
    
    # First player has nationality
    assert players[0]["url"] == "https://cuetracker.net/Players/judd-trump"
    assert players[0]["first_name"] == "Judd"
    assert players[0]["surname"] == "Trump"
    assert players[0]["nationality"] == "England"
    
    # Second player has missing nationality, falls back to "NA"
    assert players[1]["url"] == "https://cuetracker.net/Players/missing-nat"
    assert players[1]["first_name"] == "Missing"
    assert players[1]["surname"] == "Nat"
    assert players[1]["nationality"] == "NA"

def test_parse_season_urls(load_fixture):
    html = load_fixture("seasons_page.html")
    seasons = parse_season_urls(html)
    
    assert len(seasons) == 2
    assert "https://cuetracker.net/seasons/2026-2027" in seasons
    assert "https://cuetracker.net/seasons/2025-2026" in seasons
    assert "https://cuetracker.net/about" not in seasons

def test_parse_tournament_urls(load_fixture):
    html = load_fixture("tournament_page.html")
    tournaments = parse_tournament_urls(html, "2026-2027")
    
    assert len(tournaments) == 1
    assert tournaments[0]["tourn_id"] == 1234
    assert tournaments[0]["url"] == "https://cuetracker.net/tournaments/world-championship/2026/1234"
    assert tournaments[0]["dates"] == "01 Jun to 05 Jun 2026"
    assert tournaments[0]["name"] == "World Championship"
    assert tournaments[0]["season"] == "2026-2027"
    assert tournaments[0]["category"] == "Professional"

def test_parse_matches(load_fixture):
    html = load_fixture("match_page.html")
    matches = parse_matches(html, 1234)
    
    assert len(matches) == 2
    
    # Final match (standard)
    # columns: tourn_id, match_id, date, stage, best_of, player_1_score, player_2_score,
    #          player_1, player_1_url, player_2, player_2_url, scores, walkover
    m1 = matches[0]
    assert m1[0] == 1234
    assert m1[1] == 9999
    assert m1[2] == "05 Jun 2026"
    assert m1[3] == "Final"
    assert m1[4] == 19
    assert m1[5] == 10
    assert m1[6] == 8
    assert m1[7] == "Judd Trump"
    assert m1[8] == "https://cuetracker.net/players/judd-trump"
    assert m1[9] == "Mark Selby"
    assert m1[10] == "https://cuetracker.net/players/mark-selby"
    assert m1[11] == "100-0, 50-80"
    assert m1[12] == 0
    
    # Semi Final match (Walkover)
    m2 = matches[1]
    assert m2[0] == 1234
    assert m2[1] == 8888
    assert m2[2] is None
    assert m2[3] == "Semi Final"
    assert m2[4] == 11
    assert m2[5] == 6
    assert m2[6] == 0
    assert m2[7] == "Judd Trump"
    assert m2[8] == "https://cuetracker.net/players/judd-trump"
    assert m2[9] == "Mark Selby"
    assert m2[10] == "https://cuetracker.net/players/mark-selby"
    assert m2[11] is None
    assert m2[12] == 1
