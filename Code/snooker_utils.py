import requests
from bs4 import BeautifulSoup as bs
import re
import time
import sqlite3
import pandas as pd

### get the player details

def player_details(surname_initials):
    data = []
    for surname_initial in surname_initials:
        full_url = f'https://cuetracker.net/players/{surname_initial}'
        html_raw = requests.get(full_url)
        soup = bs(html_raw.content)
        tables = soup.findChildren('table')[0]
        rows = tables.find_all('tr')
        for row in rows:
            entries = row.findChildren('a')
            url = entries[0]['href']
            first_name = entries[0].get_text()
            surname = entries[1].get_text()
            try:
                nationality = entries[2].get_text().lstrip()
                data.append({'url':url, 'first_name':first_name, 'surname':surname, 'nationality':nationality})
            except:
                # sometimes a player's nationality isn't defined
                data.append({'url':url, 'first_name':first_name, 'surname':surname, 'nationality':'NA'})
                print(f'Problem with nationality of player: {first_name} {surname}')
                pass
        print(f'finished with initials beginning with {surname_initial}')
    return(data)

### get the season urls

def season_urls():
    soup = bs(requests.get('https://cuetracker.net/seasons').content, features="lxml")
    season_urls = []
    href_tags = soup.find_all('a', href = True)
    for href_tag in href_tags:
        match = re.search(r'/(\d{4}-\d{4})\Z', href_tag['href'])
        if match:
            season_urls.append(href_tag['href'])
    return(season_urls)

### get the tournament urls

def tournament_urls(season_urls):
    data = []
    if isinstance(season_urls, str):
        season_urls = [season_urls]
    for season_url in season_urls:
        season = season_url[-9:]
        soup = bs(requests.get(season_url).content, features="lxml")
        tables = soup.findChildren('table')[2]
        rows = tables.find_all('tr')
        for row in rows:
            dates = row.findChildren('td')[0].get_text().strip()
            name = row.findChildren('td')[1].get_text().strip()
            url = row.findChildren('td')[1].findChildren('a')[0]['href']
            tourn_id = url.rsplit("/", 1)[-1]
            category = row.findChildren('td')[2].get_text().strip()
            data.append({'tourn_id':tourn_id, 'url':url, 'dates':dates,
                        'name':name, 'season':season, 'category':category})
        time.sleep(0.5)
        print(f'finished scraping tournament info for season: {season}')
    return(data)

### then do the filter
### after that scrape all the matches

def matches_scrape(tournament_urls):
    if isinstance(tournament_urls, str):
        tournament_urls = [tournament_urls]
    data = []
    counter = 0
    for tourn_url in tournament_urls:
        tourn_id = tourn_url.rsplit('/', 1)[1]
        soup = bs(requests.get(tourn_url).content, features="lxml")
        regex = re.compile('.*match row.*')
        matches = soup.find_all("div",  {"class" : regex})
        for match in matches:
            match_id = match['data-match-id']
            stage = match.find('h5').get_text()
            best_of = match.find('span', {'class':'best_of text-nowrap'}).get_text().strip().strip('()')
            player_1_score = match.find('span', {'class':'matchResultText text-nowrap float-left player_1_score'}).get_text().strip()
            player_2_score = match.find('span', {'class':'matchResultText text-nowrap float-right player_2_score'}).get_text().strip()
            player_1 = match.find('div', {'class':'player_1_name matchResultText mx-auto'}).get_text().strip().replace(' (Walkover)','')
            player_1_url = match.find('div', {'class':'player_1_name matchResultText mx-auto'}).find('a')['href'].rsplit('/',2)[0]
            player_2 = match.find('div', {'class':'player_2_name matchResultText mx-auto'}).get_text().strip().replace(' (Walkover)','')
            player_2_url = match.find('div', {'class':'player_2_name matchResultText mx-auto'}).find('a')['href'].rsplit('/',2)[0]
            if ' (Walkover)' in match.get_text():            
                date = None
                scores = None
                walkover = True
            else:    
                try:
                    date = match.find('div', {'class':'col-12 played_on'}).get_text().strip()
                except:
                    date = None
                try:
                    scores = match.find('div', {'class':'col-12 frame_scores'}).get_text().strip()
                except:
                    scores = None
                walkover = False
            data.append([tourn_id, match_id, date, stage, best_of, player_1_score, player_2_score,
                        player_1, player_1_url, player_2, player_2_url, scores, walkover])
        time.sleep(0.5)
        counter += 1
        print(f'tournament {counter} \ {len(tournament_urls)} ({100 * counter / len(tournament_urls):.2f} %) scraped')
    return(data)

