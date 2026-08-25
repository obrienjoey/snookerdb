import logging
import re
import time
from typing import Any, Dict, List, Optional, Union

import requests
from bs4 import BeautifulSoup

# Import models for validation
from models import BreakModel, FrameModel, MatchModel, PlayerModel, RankingModel, TournamentModel
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

# Configure module-level logging
logger = logging.getLogger("snookerdb")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

_session = None


def parse_date_to_iso(date_str: str) -> Union[str, None]:
    if not date_str:
        return None
    import re
    from datetime import datetime

    s = date_str.strip()
    if not s:
        return None

    # 1. ISO format at the start: YYYY-MM-DD
    # Handles "2025-12-21", "2026-05-03 - 05-04", "2026-05-03 - 2026-05-04", "2026-05-03 to ..."
    iso_match = re.match(r"^(\d{4}-\d{2}-\d{2})", s)
    if iso_match:
        iso_candidate = iso_match.group(1)
        try:
            datetime.strptime(iso_candidate, "%Y-%m-%d")
            return iso_candidate
        except ValueError:
            pass

    # 2. Textual date: "%d %b %Y" (e.g. "05 Jun 2026", "5 Jun 2026")
    try:
        return datetime.strptime(s, "%d %b %Y").strftime("%Y-%m-%d")
    except ValueError:
        pass

    # 3. Check for range separators (" to ", " - ", " – ", " — ")
    for sep in [" to ", " - ", " – ", " — "]:
        if sep in s:
            start_str, end_str = [p.strip() for p in s.split(sep, 1)]

            # Single ISO in start_str
            start_iso = re.match(r"^(\d{4}-\d{2}-\d{2})$", start_str)
            if start_iso:
                try:
                    datetime.strptime(start_iso.group(1), "%Y-%m-%d")
                    return start_iso.group(1)
                except ValueError:
                    pass

            # Full textual in start_str: e.g. "01 Jun 2026"
            try:
                return datetime.strptime(start_str, "%d %b %Y").strftime("%Y-%m-%d")
            except ValueError:
                pass

            # Textual format with month/year borrowed from end_str
            end_match = re.search(r"([a-zA-Z]{3})\s+(\d{4})$", end_str)
            if end_match:
                end_month, end_year = end_match.group(1), end_match.group(2)
                if re.match(r"^\d{1,2}\s+[a-zA-Z]{3}$", start_str):
                    try:
                        return datetime.strptime(f"{start_str} {end_year}", "%d %b %Y").strftime("%Y-%m-%d")
                    except ValueError:
                        pass
                elif re.match(r"^\d{1,2}$", start_str):
                    try:
                        return datetime.strptime(f"{start_str} {end_month} {end_year}", "%d %b %Y").strftime("%Y-%m-%d")
                    except ValueError:
                        pass

    return None


def parse_tournament_dates(
    dates_str: str, season: Optional[str] = None
) -> tuple[Union[str, None], Union[str, None]]:
    if not dates_str:
        return None, None
    import re
    from datetime import datetime

    s = dates_str.strip()
    if not s:
        return None, None

    # Extract season years if available (e.g. "2025-2026" -> year1=2025, year2=2026)
    year1: Optional[int] = None
    year2: Optional[int] = None
    if season:
        m = re.search(r"(\d{4})[-/](\d{4})", season)
        if m:
            year1, year2 = int(m.group(1)), int(m.group(2))
        else:
            m_single = re.search(r"(\d{4})", season)
            if m_single:
                year1 = year2 = int(m_single.group(1))

    def resolve_year_for_month(month: int) -> Optional[int]:
        if year1 is not None and year2 is not None:
            # Snooker season: May-Dec (months 5-12) is year1, Jan-Apr (months 1-4) is year2
            return year1 if month >= 5 else year2
        elif year1 is not None:
            return year1
        return None

    # 1. Check for range separators: " to ", " - ", " – ", " — "
    separator = None
    for sep in [" to ", " - ", " – ", " — "]:
        if sep in s:
            separator = sep
            break

    if separator:
        start_str, end_str = [p.strip() for p in s.split(separator, 1)]

        # 1a. Check ISO range: YYYY-MM-DD - YYYY-MM-DD or YYYY-MM-DD - MM-DD
        m_iso_full = re.match(r"^(\d{4}-\d{2}-\d{2})\s*(?:to|-|–|—)\s*(\d{4}-\d{2}-\d{2})$", s)
        if m_iso_full:
            d1_s, d2_s = m_iso_full.group(1), m_iso_full.group(2)
            try:
                datetime.strptime(d1_s, "%Y-%m-%d")
                datetime.strptime(d2_s, "%Y-%m-%d")
                return d1_s, d2_s
            except ValueError:
                pass

        m_iso_partial = re.match(r"^(\d{4})-(\d{2})-(\d{2})\s*(?:to|-|–|—)\s*(\d{2})-(\d{2})$", s)
        if m_iso_partial:
            y1_s, m1_s, d1_s, m2_s, d2_s = m_iso_partial.groups()
            y1 = int(y1_s)
            m1, m2 = int(m1_s), int(m2_s)
            y2 = y1 if m2 >= m1 else y1 + 1
            res1 = f"{y1:04d}-{m1_s}-{d1_s}"
            res2 = f"{y2:04d}-{m2_s}-{d2_s}"
            try:
                datetime.strptime(res1, "%Y-%m-%d")
                datetime.strptime(res2, "%Y-%m-%d")
                return res1, res2
            except ValueError:
                pass

        # 1b. Check numeric DD-MM-YYYY - DD-MM-YYYY
        m_dmy_full = re.match(r"^(\d{1,2})-(\d{1,2})-(\d{4})\s*(?:to|-|–|—)\s*(\d{1,2})-(\d{1,2})-(\d{4})$", s)
        if m_dmy_full:
            d1_i, m1_i, y1_i, d2_i, m2_i, y2_i = [int(x) for x in m_dmy_full.groups()]
            res1 = f"{y1_i:04d}-{m1_i:02d}-{d1_i:02d}"
            res2 = f"{y2_i:04d}-{m2_i:02d}-{d2_i:02d}"
            try:
                datetime.strptime(res1, "%Y-%m-%d")
                datetime.strptime(res2, "%Y-%m-%d")
                return res1, res2
            except ValueError:
                pass

        # 1c. Check numeric DD-MM - DD-MM (e.g. "18-04 - 04-05")
        m_dm_short = re.match(r"^(\d{1,2})-(\d{1,2})\s*(?:to|-|–|—)\s*(\d{1,2})-(\d{1,2})$", s)
        if m_dm_short:
            d1_i, m1_i, d2_i, m2_i = [int(x) for x in m_dm_short.groups()]
            y1_calc = resolve_year_for_month(m1_i)
            if y1_calc is not None:
                y2_calc = y1_calc if m2_i >= m1_i else y1_calc + 1
                res1 = f"{y1_calc:04d}-{m1_i:02d}-{d1_i:02d}"
                res2 = f"{y2_calc:04d}-{m2_i:02d}-{d2_i:02d}"
                try:
                    datetime.strptime(res1, "%Y-%m-%d")
                    datetime.strptime(res2, "%Y-%m-%d")
                    return res1, res2
                except ValueError:
                    pass

        # 1d. Textual ranges (e.g. "01 Jun to 05 Jun 2026", "01 to 05 Jun 2026", "28 Dec 2023 to 03 Jan 2024")
        end_date = None
        try:
            end_date_obj = datetime.strptime(end_str, "%d %b %Y")
            end_date = end_date_obj.strftime("%Y-%m-%d")
        except ValueError:
            pass

        start_date = None
        if re.match(r"^\d{1,2} [a-zA-Z]{3} \d{4}$", start_str):
            try:
                start_date = datetime.strptime(start_str, "%d %b %Y").strftime("%Y-%m-%d")
            except Exception:
                pass
        elif re.match(r"^\d{1,2} [a-zA-Z]{3}$", start_str) and end_date:
            try:
                start_date = datetime.strptime(start_str + " " + end_date[:4], "%d %b %Y").strftime("%Y-%m-%d")
            except Exception:
                pass
        elif re.match(r"^\d{1,2}$", start_str) and end_date:
            try:
                start_date = f"{end_date[:8]}{int(start_str):02d}"
                datetime.strptime(start_date, "%Y-%m-%d")
            except Exception:
                start_date = None

        if start_date or end_date:
            return start_date, end_date

    # 2. Single dates
    # 2a. Single ISO YYYY-MM-DD
    m_single_iso = re.match(r"^(\d{4}-\d{2}-\d{2})$", s)
    if m_single_iso:
        try:
            datetime.strptime(m_single_iso.group(1), "%Y-%m-%d")
            return m_single_iso.group(1), m_single_iso.group(1)
        except ValueError:
            pass

    # 2b. Single numeric DD-MM-YYYY
    m_single_dmy = re.match(r"^(\d{1,2})-(\d{1,2})-(\d{4})$", s)
    if m_single_dmy:
        d_i, m_i, y_i = [int(x) for x in m_single_dmy.groups()]
        res = f"{y_i:04d}-{m_i:02d}-{d_i:02d}"
        try:
            datetime.strptime(res, "%Y-%m-%d")
            return res, res
        except ValueError:
            pass

    # 2c. Single textual "%d %b %Y"
    try:
        dt = datetime.strptime(s, "%d %b %Y").strftime("%Y-%m-%d")
        return dt, dt
    except Exception:
        pass

    return None, None


def parse_tournament_details(html: str) -> Dict[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(separator=" ", strip=True)
    details = {"venue": "", "city": "", "country": "", "sponsor": "", "prize_fund": ""}

    loc_match = re.search(r"Location:\s*(.*?)(?=\s*(?:Players:|Matches:|Status:|Dates:|Prize fund:|$))", text)
    if loc_match:
        loc_str = loc_match.group(1).strip()
        sponsor_match = re.search(r"(.*?)\s+Sponsor:\s*(.*?)(?=\s*Broadcaster:|$)", loc_str)
        if sponsor_match:
            loc_str = sponsor_match.group(1).strip()
            details["sponsor"] = sponsor_match.group(2).strip()

        parts = [x.strip() for x in loc_str.split(",")]
        if len(parts) >= 3:
            details["venue"] = parts[0]
            details["city"] = parts[1]
            details["country"] = parts[2]
        elif len(parts) == 2:
            details["city"] = parts[0]
            details["country"] = parts[1]
        elif len(parts) == 1:
            details["country"] = parts[0]

    prize_match = re.search(r"Prize fund:\s*(.*?)(?=\s*(?:Points scored:|Status:|Location:|$))", text)
    if prize_match:
        details["prize_fund"] = prize_match.group(1).strip()

    return details


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
        _session.headers.update({"User-Agent": "SnookerDB/1.0 (+https://github.com/obrienjoey/snookerdb)"})
        # Retry on status codes 429, 500, 502, 503, 504 with an exponential backoff
        retries = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504], raise_on_status=False)
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
    tables = soup.find_all("table")
    if not tables:
        logger.warning("No table found in player details HTML")
        return []

    rows = tables[0].find_all("tr")
    data = []
    for row in rows:
        entries = row.find_all("a")
        if len(entries) < 2:
            continue

        # Safely convert to str to satisfy mypy
        url_attr = entries[0].get("href")
        url = str(url_attr) if url_attr else ""

        first_name = entries[0].get_text().strip()
        surname = entries[1].get_text().strip()
        nationality = "NA"
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
        full_url = f"https://cuetracker.net/players/{surname_initial}"
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
    href_tags = soup.find_all("a", href=True)
    for href_tag in href_tags:
        href_val = href_tag.get("href")
        if not href_val:
            continue
        href_str = str(href_val)
        match = re.search(r"/(\d{4}-\d{4})\Z", href_str)
        if match:
            season_urls.append(href_str)
    return season_urls


def season_urls() -> List[str]:
    """Fetches and parses the complete index of season URLs.

    Returns:
        List[str]: A list of full season paths.
    """
    try:
        html = fetch_html("https://cuetracker.net/seasons")
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
    tables = soup.find_all("table")
    if len(tables) < 3:
        logger.warning(f"Expected at least 3 tables for season {season}, found {len(tables)}")
        return []

    rows = tables[2].find_all("tr")
    data = []
    for row in rows:
        tds = row.find_all("td")
        if len(tds) < 3:
            continue
        dates = tds[0].get_text().strip()
        name = tds[1].get_text().strip()
        links = tds[1].find_all("a")
        if not links:
            continue
        url_attr = links[0].get("href")
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

        start_date, end_date = parse_tournament_dates(dates, season=season)

        try:
            tourn_model = TournamentModel(
                tourn_id=tourn_id,
                url=url,
                dates=dates,
                name=name,
                season=season,
                category=category,
                start_date=start_date,
                end_date=end_date,
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
        season = season_url.rstrip("/").rsplit("/", 1)[-1]
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
    regex = re.compile(".*match row.*")
    matches = soup.find_all("div", {"class": regex})
    data = []
    for match in matches:
        match_id_attr = match.get("data-match-id")
        if not match_id_attr:
            continue

        match_id_str = str(match_id_attr[0]) if isinstance(match_id_attr, list) else str(match_id_attr)
        try:
            match_id = int(match_id_str)
        except ValueError:
            logger.error(f"Could not parse match ID '{match_id_str}' as int under tournament {tourn_id}")
            continue

        h5_tag = match.find("h5")
        stage = h5_tag.get_text().strip() if h5_tag else "Unknown Stage"

        best_of_tag = match.find("span", {"class": "best_of text-nowrap"})
        best_of_str = best_of_tag.get_text().strip().strip("()") if best_of_tag else ""
        try:
            best_of = int(best_of_str)
        except ValueError:
            best_of = None

        p1_score_tag = match.find("span", {"class": "matchResultText text-nowrap float-left player_1_score"})
        player_1_score_str = p1_score_tag.get_text().strip() if p1_score_tag else ""
        try:
            player_1_score = int(player_1_score_str)
        except ValueError:
            player_1_score = None

        p2_score_tag = match.find("span", {"class": "matchResultText text-nowrap float-right player_2_score"})
        player_2_score_str = p2_score_tag.get_text().strip() if p2_score_tag else ""
        try:
            player_2_score = int(player_2_score_str)
        except ValueError:
            player_2_score = None

        p1_div = match.find("div", {"class": "player_1_name matchResultText mx-auto"})
        if p1_div:
            player_1 = p1_div.get_text().strip().replace(" (Walkover)", "")
            p1_a = p1_div.find("a")
            if p1_a:
                p1_href = p1_a.get("href")
                p1_href_str = str(p1_href[0]) if isinstance(p1_href, list) else str(p1_href) if p1_href else ""
                player_1_url = p1_href_str.rsplit("/", 2)[0] if p1_href_str else ""
            else:
                player_1_url = ""
        else:
            player_1, player_1_url = "Unknown", ""

        p2_div = match.find("div", {"class": "player_2_name matchResultText mx-auto"})
        if p2_div:
            player_2 = p2_div.get_text().strip().replace(" (Walkover)", "")
            p2_a = p2_div.find("a")
            if p2_a:
                p2_href = p2_a.get("href")
                p2_href_str = str(p2_href[0]) if isinstance(p2_href, list) else str(p2_href) if p2_href else ""
                player_2_url = p2_href_str.rsplit("/", 2)[0] if p2_href_str else ""
            else:
                player_2_url = ""
        else:
            player_2, player_2_url = "Unknown", ""

        if " (Walkover)" in match.get_text():
            date = None
            scores = None
            walkover = 1
        else:
            date = None
            played_on_div = match.find("div", {"class": "col-12 played_on"})
            if played_on_div:
                date = parse_date_to_iso(played_on_div.get_text().strip())

            scores = None
            frame_scores_div = match.find("div", {"class": "col-12 frame_scores"})
            if frame_scores_div:
                scores = frame_scores_div.get_text().strip()

            walkover = 0

        winner = None
        winner_url = None
        if walkover:
            # Look at match text to see who won walkover
            # Typically CueTracker uses ' (Walkover)' next to the winning player's name
            p1_div_text = p1_div.get_text() if p1_div else ""
            p2_div_text = p2_div.get_text() if p2_div else ""
            if "Walkover" in p1_div_text:
                winner, winner_url = player_1, player_1_url
            elif "Walkover" in p2_div_text:
                winner, winner_url = player_2, player_2_url
        else:
            if player_1_score is not None and player_2_score is not None:
                if player_1_score > player_2_score:
                    winner, winner_url = player_1, player_1_url
                elif player_2_score > player_1_score:
                    winner, winner_url = player_2, player_2_url

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
                walkover=walkover,
                winner=winner,
                winner_url=winner_url,
            )
            data.append(
                [
                    match_model.tourn_id,
                    match_model.match_id,
                    match_model.date,
                    match_model.stage,
                    match_model.best_of,
                    match_model.player_1_score,
                    match_model.player_2_score,
                    match_model.player_1,
                    match_model.player_1_url,
                    match_model.player_2,
                    match_model.player_2_url,
                    match_model.scores,
                    match_model.walkover,
                    match_model.winner,
                    match_model.winner_url,
                ]
            )
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
        tourn_id_str = tourn_url.rsplit("/", 1)[1]
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


def parse_frames_and_breaks(match_id: int, scores_str: str) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Parses a frame scores string into structured frame and break data.

    Args:
        match_id: The ID of the match.
        scores_str: The raw scores string (e.g. '104(104)-0; 21-101(88)').

    Returns:
        A tuple containing two lists: (frames_data, breaks_data)
    """
    frames = []
    breaks = []
    if not isinstance(scores_str, str) or not scores_str or "Walkover" in scores_str:
        return frames, breaks

    frame_strs = [f.strip() for f in scores_str.split(";")]
    frame_num = 1
    for frame_str in frame_strs:
        if not frame_str:
            continue

        parts = frame_str.split("-")
        if len(parts) != 2:
            continue

        p1_part, p2_part = parts[0].strip(), parts[1].strip()

        m1 = re.match(r"^(\d+)(?:\(([\d,]+)\))?$", p1_part)
        m2 = re.match(r"^(\d+)(?:\(([\d,]+)\))?$", p2_part)

        if not m1 or not m2:
            continue

        p1_score = int(m1.group(1))
        p1_breaks_str = m1.group(2)
        p1_breaks = [int(b) for b in p1_breaks_str.split(",")] if p1_breaks_str else []

        p2_score = int(m2.group(1))
        p2_breaks_str = m2.group(2)
        p2_breaks = [int(b) for b in p2_breaks_str.split(",")] if p2_breaks_str else []

        try:
            frame_model = FrameModel(
                match_id=match_id, frame_num=frame_num, player_1_score=p1_score, player_2_score=p2_score
            )
            frames.append(frame_model.model_dump())

            for brk in p1_breaks:
                break_model = BreakModel(match_id=match_id, frame_num=frame_num, player_number=1, points=brk)
                breaks.append(break_model.model_dump())

            for brk in p2_breaks:
                break_model = BreakModel(match_id=match_id, frame_num=frame_num, player_number=2, points=brk)
                breaks.append(break_model.model_dump())

        except Exception as e:
            logger.error(f"Validation failed for frame/break in match {match_id}: {e}")

        frame_num += 1

    return frames, breaks


def parse_rankings(html: str, season: str) -> List[Dict[str, Any]]:
    """Parses a seasonal rankings page and returns a list of validated ranking dictionaries.

    Args:
        html: Raw HTML content from a season rankings page.
        season: The season name (e.g. '2024-2025').

    Returns:
        List[Dict[str, Any]]: A list of dictionaries representing validated player rankings.
    """
    soup = BeautifulSoup(html, features="html.parser")
    t = soup.find("table", id="main_table")
    if not t:
        logger.warning(f"No main_table found in rankings HTML for season {season}")
        return []

    tbody = t.find("tbody")
    if not tbody:
        logger.warning(f"No tbody found in rankings HTML for season {season}")
        return []

    rows = tbody.find_all("tr")
    data = []
    for row in rows:
        tds = row.find_all("td")
        if len(tds) < 6:
            continue

        p_a = tds[0].find("a")
        if not p_a:
            continue
        player_name = p_a.get_text().strip()
        player_url = str(p_a.get("href"))

        def parse_int(text: str) -> Optional[int]:
            clean_text = text.strip().replace(",", "")
            if not clean_text or clean_text == "":
                return None
            try:
                return int(clean_text)
            except ValueError:
                return None

        start_position = parse_int(tds[1].get_text())
        start_points = parse_int(tds[2].get_text())

        diff_text = tds[3].get_text().strip().replace("+", "")
        difference = parse_int(diff_text)

        finish_position = parse_int(tds[4].get_text())
        finish_points = parse_int(tds[5].get_text())

        try:
            ranking_model = RankingModel(
                season=season,
                player_name=player_name,
                player_url=player_url,
                start_position=start_position,
                start_points=start_points,
                difference=difference,
                finish_position=finish_position,
                finish_points=finish_points,
            )
            data.append(ranking_model.model_dump())
        except Exception as e:
            logger.error(f"Validation failed for ranking row: {e}")

    return data


def scrape_rankings(seasons: List[str]) -> List[Dict[str, Any]]:
    """Scrapes rankings for a list of season names.

    Args:
        seasons: List of season strings (e.g. ['2023-2024', '2024-2025']).

    Returns:
        List[Dict[str, Any]]: Aggregated ranking records parsed and validated.
    """
    data = []
    for season in seasons:
        url = f"https://cuetracker.net/Rankings/{season}"
        try:
            html = fetch_html(url)
            parsed_data = parse_rankings(html, season)
            data.extend(parsed_data)
        except Exception as e:
            logger.error(f"Error scraping rankings for season {season}: {e}")
        time.sleep(0.5)
    return data

