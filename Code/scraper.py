import logging
import re
import time
from typing import Any, Dict, List, Union
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

# Import models for validation
from models import MatchModel, PlayerModel, TournamentModel

# Configure module-level logging
logger = logging.getLogger("snookerdb")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

_session = None

def get_session() -> requests.Session:
    """Retrieves or initializes a requests Session object.

    The session is preconfigured with standard HTTP headers (including a custom User-Agent)
    and an HTTP connection adapter that automatically retries failed requests on connection
    failures and specific server response status codes (e.g. rate limits or server errors)
    using exponential backoff.

    Returns:
        requests.Session: A thread-safe, pre-configured HTTP session.
    """
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update({
            "User-Agent": "SnookerDB/1.0 (+https://github.com/obrienjoey/snookerdb)"
        })
        # Retry on status codes 429, 500, 502, 503, 504 with an exponential backoff
        retries = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            raise_on_status=False
        )
        adapter = HTTPAdapter(max_retries=retries)
        _session.mount("http://", adapter)
        _session.mount("https://", adapter)
    return _session

def fetch_html(url: str) -> str:
    """Fetches the raw HTML content from a given URL.

    Args:
        url: The web address to fetch.

    Raises:
        requests.RequestException: If the HTTP request fails or returns an error status.

    Returns:
        str: The raw HTML response string.
    """
    logger.info(f"Fetching URL: {url}")
    try:
        response = get_session().get(url, timeout=30)
        response.raise_for_status()
        return response.text
    except requests.RequestException as e:
        logger.error(f"HTTP request failed for {url}: {e}")
        raise

def parse_player_details(html: str) -> List[Dict[str, str]]:
    """Parses player profile list data from a listing page.

    Extracts details such as URL, names, and nationality, then validates
    them against the PlayerModel schema.

    Args:
        html: Raw HTML content from a CueTracker player directory initial listing page.

    Returns:
        List[Dict[str, str]]: A list of dictionaries representing validated player profiles.
    """
    soup = BeautifulSoup(html, features="html.parser")
    tables = soup.find_all('table')
    if not tables:
        logger.warning("No table found in player details HTML")
        return []
    
    rows = tables[0].find_all('tr')
    data = []
    for row in rows:
        entries = row.find_all('a')
        if len(entries) < 2:
            continue
        
        # Safely convert to str to satisfy mypy
        url_attr = entries[0].get('href')
        url = str(url_attr) if url_attr else ''
        
        first_name = entries[0].get_text().strip()
        surname = entries[1].get_text().strip()
        nationality = 'NA'
        if len(entries) >= 3:
            try:
                nationality = entries[2].get_text().lstrip()
            except IndexError as e:
                logger.warning(f"IndexError parsing nationality for player '{first_name} {surname}': {e}")
        
        try:
            player_model = PlayerModel(url=url, first_name=first_name, surname=surname, nationality=nationality)
            data.append(player_model.model_dump())
        except Exception as e:
            logger.error(f"Validation failed for player '{first_name} {surname}': {e}")
            
    return data

def player_details(surname_initials: List[str], error_log: bool = True) -> List[Dict[str, str]]:
    """Scrapes player information for a list of surname starting initials.

    Args:
        surname_initials: List of lowercase characters (e.g. ['a', 'b']).
        error_log: Flag indicating whether errors should print warnings.

    Returns:
        List[Dict[str, str]]: Aggregated list of all scraped and validated player dictionaries.
    """
    data = []
    for surname_initial in surname_initials:
        full_url = f'https://cuetracker.net/players/{surname_initial}'
        try:
            html = fetch_html(full_url)
            parsed_data = parse_player_details(html)
            data.extend(parsed_data)
        except Exception as e:
            logger.error(f"Error scraping players starting with '{surname_initial}': {e}")
        logger.info(f"Finished with initials beginning with {surname_initial}")
    return data

def parse_season_urls(html: str) -> List[str]:
    """Parses season links from the main seasons overview page.

    Filters URLs to match those of the format '/YYYY-YYYY'.

    Args:
        html: Raw HTML content from the seasons listing page.

    Returns:
        List[str]: List of season URL path extensions.
    """
    soup = BeautifulSoup(html, features="html.parser")
    season_urls = []
    href_tags = soup.find_all('a', href=True)
    for href_tag in href_tags:
        href_val = href_tag.get('href')
        if not href_val:
            continue
        href_str = str(href_val)
        match = re.search(r'/(\d{4}-\d{4})\Z', href_str)
        if match:
            season_urls.append(href_str)
    return season_urls

def season_urls() -> List[str]:
    """Fetches and parses the complete index of season URLs.

    Returns:
        List[str]: A list of full season paths.
    """
    try:
        html = fetch_html('https://cuetracker.net/seasons')
        return parse_season_urls(html)
    except Exception as e:
        logger.error(f"Error fetching season URLs: {e}")
        raise

def parse_tournament_urls(html: str, season: str) -> List[Dict[str, Any]]:
    """Parses tournament listing tables for a single season page.

    Args:
        html: Raw HTML content of a season page listing all tournaments.
        season: The season string (e.g. '2023-2024').

    Returns:
        List[Dict[str, Any]]: List of validated tournament dictionaries.
    """
    soup = BeautifulSoup(html, features="html.parser")
    tables = soup.find_all('table')
    if len(tables) < 3:
        logger.warning(f"Expected at least 3 tables for season {season}, found {len(tables)}")
        return []
    
    rows = tables[2].find_all('tr')
    data = []
    for row in rows:
        tds = row.find_all('td')
        if len(tds) < 3:
            continue
        dates = tds[0].get_text().strip()
        name = tds[1].get_text().strip()
        links = tds[1].find_all('a')
        if not links:
            continue
        url_attr = links[0].get('href')
        if not url_attr:
            continue
        url = str(url_attr)
        tourn_id_str = url.rsplit("/", 1)[-1]
        
        try:
            tourn_id = int(tourn_id_str)
        except ValueError:
            logger.error(f"Could not parse tournament ID '{tourn_id_str}' as int for season {season}")
            continue
            
        category = tds[2].get_text().strip()
        
        try:
            tourn_model = TournamentModel(
                tourn_id=tourn_id,
                url=url,
                dates=dates,
                name=name,
                season=season,
                category=category
            )
            data.append(tourn_model.model_dump())
        except Exception as e:
            logger.error(f"Validation failed for tournament with ID {tourn_id} under season {season}: {e}")
            
    return data

def tournament_urls(season_urls: Union[List[str], str]) -> List[Dict[str, Any]]:
    """Scrapes all tournament listings for the given season URLs.

    Args:
        season_urls: A list of season URLs or a single season URL string.

    Returns:
        List[Dict[str, Any]]: Aggregated validated tournament data dictionaries.
    """
    data = []
    if isinstance(season_urls, str):
        season_urls = [season_urls]
    for season_url in season_urls:
        season = season_url[-9:]
        try:
            html = fetch_html(season_url)
            parsed_data = parse_tournament_urls(html, season)
            data.extend(parsed_data)
        except Exception as e:
            logger.error(f"Error scraping tournaments for season {season}: {e}")
        time.sleep(0.5)
        logger.info(f"Finished scraping tournament info for season: {season}")
    return data

def parse_matches(html: str, tourn_id: int) -> List[List[Any]]:
    """Parses individual match lines from a tournament page.

    Handles walkovers, score extractions, player URLs, stage names,
    and frame scores.

    Args:
        html: Raw HTML content of a tournament match listing page.
        tourn_id: Unique tournament identifier.

    Returns:
        List[List[Any]]: List of matches, where each match is a flat list
            ordered matching database schemas.
    """
    soup = BeautifulSoup(html, features="html.parser")
    regex = re.compile('.*match row.*')
    matches = soup.find_all("div", {"class": regex})
    data = []
    for match in matches:
        match_id_attr = match.get('data-match-id')
        if not match_id_attr:
            continue
        
        match_id_str = str(match_id_attr[0]) if isinstance(match_id_attr, list) else str(match_id_attr)
        try:
            match_id = int(match_id_str)
        except ValueError:
            logger.error(f"Could not parse match ID '{match_id_str}' as int under tournament {tourn_id}")
            continue
            
        h5_tag = match.find('h5')
        stage = h5_tag.get_text().strip() if h5_tag else 'Unknown Stage'
        
        best_of_tag = match.find('span', {'class': 'best_of text-nowrap'})
        best_of_str = best_of_tag.get_text().strip().strip('()') if best_of_tag else ''
        try:
            best_of = int(best_of_str)
        except ValueError:
            best_of = None
            
        p1_score_tag = match.find('span', {'class': 'matchResultText text-nowrap float-left player_1_score'})
        player_1_score_str = p1_score_tag.get_text().strip() if p1_score_tag else ''
        try:
            player_1_score = int(player_1_score_str)
        except ValueError:
            player_1_score = None
            
        p2_score_tag = match.find('span', {'class': 'matchResultText text-nowrap float-right player_2_score'})
        player_2_score_str = p2_score_tag.get_text().strip() if p2_score_tag else ''
        try:
            player_2_score = int(player_2_score_str)
        except ValueError:
            player_2_score = None
            
        p1_div = match.find('div', {'class': 'player_1_name matchResultText mx-auto'})
        if p1_div:
            player_1 = p1_div.get_text().strip().replace(' (Walkover)', '')
            p1_a = p1_div.find('a')
            if p1_a:
                p1_href = p1_a.get('href')
                p1_href_str = str(p1_href[0]) if isinstance(p1_href, list) else str(p1_href) if p1_href else ''
                player_1_url = p1_href_str.rsplit('/', 2)[0] if p1_href_str else ''
            else:
                player_1_url = ''
        else:
            player_1, player_1_url = 'Unknown', ''
            
        p2_div = match.find('div', {'class': 'player_2_name matchResultText mx-auto'})
        if p2_div:
            player_2 = p2_div.get_text().strip().replace(' (Walkover)', '')
            p2_a = p2_div.find('a')
            if p2_a:
                p2_href = p2_a.get('href')
                p2_href_str = str(p2_href[0]) if isinstance(p2_href, list) else str(p2_href) if p2_href else ''
                player_2_url = p2_href_str.rsplit('/', 2)[0] if p2_href_str else ''
            else:
                player_2_url = ''
        else:
            player_2, player_2_url = 'Unknown', ''
            
        if ' (Walkover)' in match.get_text():
            date = None
            scores = None
            walkover = 1
        else:
            date = None
            played_on_div = match.find('div', {'class': 'col-12 played_on'})
            if played_on_div:
                date = played_on_div.get_text().strip()
                
            scores = None
            frame_scores_div = match.find('div', {'class': 'col-12 frame_scores'})
            if frame_scores_div:
                scores = frame_scores_div.get_text().strip()
                
            walkover = 0
            
        try:
            match_model = MatchModel(
                tourn_id=tourn_id,
                match_id=match_id,
                date=date,
                stage=stage,
                best_of=best_of,
                player_1_score=player_1_score,
                player_2_score=player_2_score,
                player_1=player_1,
                player_1_url=player_1_url,
                player_2=player_2,
                player_2_url=player_2_url,
                scores=scores,
                walkover=walkover
            )
            data.append([
                match_model.tourn_id, match_model.match_id, match_model.date, match_model.stage, match_model.best_of,
                match_model.player_1_score, match_model.player_2_score, match_model.player_1, match_model.player_1_url,
                match_model.player_2, match_model.player_2_url, match_model.scores, match_model.walkover
            ])
        except Exception as e:
            logger.error(f"Validation failed for match with ID {match_id} under tournament {tourn_id}: {e}")
            
    return data

def matches_scrape(tournament_urls: Union[List[str], str]) -> List[List[Any]]:
    """Scrapes and compiles match data for the given tournament URLs.

    Args:
        tournament_urls: A list of tournament URL strings or a single URL string.

    Returns:
        List[List[Any]]: Flattend match records parsed and validated.
    """
    if isinstance(tournament_urls, str):
        tournament_urls = [tournament_urls]
    data = []
    counter = 0
    for tourn_url in tournament_urls:
        tourn_id_str = tourn_url.rsplit('/', 1)[1]
        try:
            tourn_id = int(tourn_id_str)
        except ValueError:
            logger.error(f"Could not parse tournament ID '{tourn_id_str}' as int from URL: {tourn_url}")
            continue
            
        try:
            html = fetch_html(tourn_url)
            parsed_data = parse_matches(html, tourn_id)
            data.extend(parsed_data)
        except Exception as e:
            logger.error(f"Error scraping matches for tournament {tourn_id}: {e}")
        time.sleep(0.5)
        counter += 1
        pct = 100 * counter / len(tournament_urls)
        logger.info(f"Tournament {counter} / {len(tournament_urls)} ({pct:.2f} %) scraped")
    return data
