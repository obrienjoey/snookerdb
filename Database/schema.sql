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
    category TEXT
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
    FOREIGN KEY(tourn_id) REFERENCES tournament(tourn_id)
);
