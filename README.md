# snookerdb

The snookerdb repository contains a collection of `python` scripts which are used to collect a large collection of data describing the history (1907-) of the sport of snooker stored at [Cuetracker](https://cuetracker.net/). 

## Datasets

The scripts collect three separate datasets

- players - list of all players to have had their snooker matches recorded on the website

- tournaments - describes all tournaments that were played since 1907.

- matches - describes the matches which were played, namely the competitors and the score.

## Data storage

The data is stored  in a SQL database found in `Database\snookerdb.db`.


## Automation

Each night the website is also automatically checked to see if any new matches have been played that day. If so, the database is updated.

