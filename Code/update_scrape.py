import snooker_utils as snooker
import sqlite3
import pandas as pd
import string

conn = sqlite3.connect("Database\snookerdb.db")

season_urls = snooker.season_urls()
check_season = season_urls[0]
tourn_df = pd.DataFrame(snooker.tournament_urls(check_season))

match_data = snooker.matches_scrape(tourn_df['url'])
match_df = pd.DataFrame(match_data, columns = ['tourn_id', 'match_id', 'date', 'stage', 'best_of', 
                                               'player_1_score', 'player_2_score','player_1', 'player_1_url', 
                                               'player_2', 'player_2_url', 'scores', 'walkover'])

surname_initials = list(string.ascii_lowercase)
player_df = pd.DataFrame(snooker.player_details(surname_initials, error_log = False))

### now compare with what we already have

local_match_df = pd.read_sql_query("SELECT * from matches", conn)
local_tourn_df = pd.read_sql_query("SELECT * from tournament", conn)
local_player_df = pd.read_sql_query("SELECT * from players", conn)

new_tourn_count = sum(tourn_df.tourn_id.isin(local_tourn_df.tourn_id) == False)
new_match_count = sum(match_df.match_id.isin(local_match_df.match_id) == False)
new_player_count = sum(player_df.url.isin(local_player_df.url) == False)

if new_player_count != 0:
    print(f'number of new players: {new_player_count}')
    new_df = pd.concat([local_player_df, player_df[player_df.url.isin(local_player_df.url) == False]])
    new_df = new_df.reset_index(drop = True)
    new_df['player_id'] = pd.to_numeric(new_df['player_id'])
    new_df = new_df.sort_values(by = ['player_id'])
    new_df.applymap(str).to_sql("players", conn, if_exists="replace", index=False)
    print('successfully updated players df')

if new_tourn_count != 0:
    print(f'number of new tournaments: {new_tourn_count}')
    new_df = pd.concat([local_tourn_df, tourn_df[tourn_df.tourn_id.isin(local_tourn_df.tourn_id) == False]])
    new_df = new_df.reset_index(drop = True)
    new_df['tourn_id'] = pd.to_numeric(new_df['tourn_id'])
    new_df = new_df.sort_values(by = ['tourn_id'])
    new_df.applymap(str).to_sql("tournament", conn, if_exists="replace", index=False)
    print('successfully updated tournament df')

if new_match_count != 0:
    print(f'number of new matches: {new_match_count}')
    new_df = pd.concat([local_match_df, match_df[match_df.match_id.isin(local_match_df.match_id) == False]])
    new_df = new_df.reset_index(drop = True)
    new_df['match_id'] = pd.to_numeric(new_df['match_id'])
    new_df = new_df.sort_values(by = ['match_id'])
    new_df.applymap(str).to_sql("matches", conn, if_exists="replace", index=False)
    print('successfully updated match df')    
else:
    print('\n no new matches to add')                                           