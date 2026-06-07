CREATE TABLE IF NOT EXISTS players (
    url TEXT PRIMARY KEY,
    first_name TEXT,
    surname TEXT,
    nationality TEXT
);

CREATE TABLE IF NOT EXISTS tournament (
    tourn_id INTEGER PRIMARY KEY,
    url TEXT,
    dates TEXT,
    name TEXT,
    season TEXT,
    category TEXT,
    venue TEXT,
    city TEXT,
    country TEXT,
    sponsor TEXT,
    prize_fund TEXT,
    start_date TEXT,
    end_date TEXT
);

CREATE TABLE IF NOT EXISTS matches (
    match_id INTEGER PRIMARY KEY,
    tourn_id INTEGER,
    date TEXT,
    stage TEXT,
    best_of INTEGER,
    player_1_score INTEGER,
    player_2_score INTEGER,
    player_1 TEXT,
    player_1_url TEXT,
    player_2 TEXT,
    player_2_url TEXT,
    scores TEXT,
    walkover INTEGER,
    winner TEXT,
    winner_url TEXT,
    FOREIGN KEY(tourn_id) REFERENCES tournament(tourn_id)
);

CREATE TABLE IF NOT EXISTS frames (
    match_id INTEGER,
    frame_num INTEGER,
    player_1_score INTEGER,
    player_2_score INTEGER,
    PRIMARY KEY (match_id, frame_num),
    FOREIGN KEY(match_id) REFERENCES matches(match_id)
);

CREATE TABLE IF NOT EXISTS breaks (
    match_id INTEGER,
    frame_num INTEGER,
    player_number INTEGER,
    points INTEGER,
    FOREIGN KEY(match_id) REFERENCES matches(match_id)
);
