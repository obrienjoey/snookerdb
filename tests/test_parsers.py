from scraper import (
    parse_date_to_iso,
    parse_matches,
    parse_player_details,
    parse_rankings,
    parse_season_urls,
    parse_tournament_dates,
    parse_tournament_urls,
)


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
    assert tournaments[0]["start_date"] == "2026-06-01"
    assert tournaments[0]["end_date"] == "2026-06-05"


def test_parse_date_to_iso():
    assert parse_date_to_iso("05 Jun 2026") == "2026-06-05"
    assert parse_date_to_iso("28 Dec 2023") == "2023-12-28"
    assert parse_date_to_iso("") is None


def test_parse_tournament_dates():
    assert parse_tournament_dates("01 Jun to 05 Jun 2026") == ("2026-06-01", "2026-06-05")
    assert parse_tournament_dates("01 to 05 Jun 2026") == ("2026-06-01", "2026-06-05")
    assert parse_tournament_dates("28 Dec 2023 to 03 Jan 2024") == ("2023-12-28", "2024-01-03")
    assert parse_tournament_dates("05 Jun 2026") == ("2026-06-05", "2026-06-05")
    assert parse_tournament_dates("") == (None, None)


def test_parse_matches(load_fixture):
    html = load_fixture("match_page.html")
    matches = parse_matches(html, 1234)

    assert len(matches) == 2

    # Final match (standard)
    # columns: tourn_id, match_id, date, stage, best_of, player_1_score, player_2_score,
    #          player_1, player_1_url, player_2, player_2_url, scores, walkover, winner, winner_url
    m1 = matches[0]
    assert m1[0] == 1234
    assert m1[1] == 9999
    assert m1[2] == "2026-06-05"
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
    assert m1[13] == "Judd Trump"
    assert m1[14] == "https://cuetracker.net/players/judd-trump"

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
    assert m2[13] == "Mark Selby"
    assert m2[14] == "https://cuetracker.net/players/mark-selby"


def test_parse_frames_and_breaks():
    from scraper import parse_frames_and_breaks

    # Normal scores with breaks
    frames, breaks = parse_frames_and_breaks(1, "104(104)-0; 21-101(88); 1-117(54,54)")
    assert len(frames) == 3
    assert frames[0]["player_1_score"] == 104
    assert frames[0]["player_2_score"] == 0
    assert frames[1]["player_1_score"] == 21
    assert frames[1]["player_2_score"] == 101
    assert frames[2]["player_1_score"] == 1
    assert frames[2]["player_2_score"] == 117

    # Breaks for frame 1
    f1_breaks = [b for b in breaks if b["frame_num"] == 1]
    assert len(f1_breaks) == 1
    assert f1_breaks[0]["points"] == 104
    assert f1_breaks[0]["player_number"] == 1

    # Breaks for frame 2
    f2_breaks = [b for b in breaks if b["frame_num"] == 2]
    assert len(f2_breaks) == 1
    assert f2_breaks[0]["points"] == 88
    assert f2_breaks[0]["player_number"] == 2

    # Breaks for frame 3
    f3_breaks = [b for b in breaks if b["frame_num"] == 3]
    assert len(f3_breaks) == 2
    assert f3_breaks[0]["points"] == 54
    assert f3_breaks[1]["points"] == 54
    assert f3_breaks[0]["player_number"] == 2

    # Walkover
    f, b = parse_frames_and_breaks(2, "Walkover")
    assert len(f) == 0
    assert len(b) == 0

    # Float/NaN and None
    import math
    f, b = parse_frames_and_breaks(3, float("nan"))
    assert len(f) == 0
    assert len(b) == 0

    f, b = parse_frames_and_breaks(4, None)
    assert len(f) == 0
    assert len(b) == 0


def test_parse_rankings(load_fixture):
    html = load_fixture("rankings_page.html")
    rankings = parse_rankings(html, "2024-2025")

    assert len(rankings) == 3

    # First ranking
    assert rankings[0]["season"] == "2024-2025"
    assert rankings[0]["player_name"] == "Judd Trump"
    assert rankings[0]["player_url"] == "https://cuetracker.net/players/judd-trump"
    assert rankings[0]["start_position"] == 4
    assert rankings[0]["start_points"] == 556000
    assert rankings[0]["difference"] == 3
    assert rankings[0]["finish_position"] == 1
    assert rankings[0]["finish_points"] == 1984200

    # Second ranking (negative difference)
    assert rankings[1]["player_name"] == "Ronnie O'Sullivan"
    assert rankings[1]["difference"] == -2

    # Third ranking (missing points and difference)
    assert rankings[2]["player_name"] == "No Points Player"
    assert rankings[2]["start_points"] is None
    assert rankings[2]["difference"] is None
    assert rankings[2]["finish_points"] is None

