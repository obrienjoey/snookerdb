import snooker_utils as snooker

surname_initials = list(string.ascii_lowercase)
player_df = pd.DataFrame(snooker.player_details(surname_initials))

season_urls = snooker.season_urls()
tourn_df = pd.DataFrame(snooker.tournament_urls(season_urls))

match_data = snooker.matches_scrape(tourn_df['url'])
match_df = pd.DataFrame(match_data, columns = ['tourn_id', 'match_id', 'date', 'stage', 'best_of', 
                                               'player_1_score', 'player_2_score','player_1', 'player_1_url', 
                                               'player_2', 'player_2_url', 'scores', 'walkover'])

conn = sqlite3.connect("Database\snookerdb.db")
player_df.applymap(str).to_sql("players", conn, if_exists="replace", index=False)
tourn_df.applymap(str).to_sql("tournament", conn, if_exists="replace", index=False)
match_df.applymap(str).to_sql("matches", conn, if_exists="replace", index=False)

