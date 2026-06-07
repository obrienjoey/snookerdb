from typing import Optional

from pydantic import BaseModel, Field


class PlayerModel(BaseModel):
    url: str
    first_name: str
    surname: str
    nationality: str = "NA"


class TournamentModel(BaseModel):
    tourn_id: int
    url: str
    dates: str
    name: str
    season: str
    category: str
    venue: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    sponsor: Optional[str] = None
    prize_fund: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class MatchModel(BaseModel):
    tourn_id: int
    match_id: int
    date: Optional[str] = None
    stage: str
    best_of: Optional[int] = None
    player_1_score: Optional[int] = None
    player_2_score: Optional[int] = None
    player_1: str
    player_1_url: str
    player_2: str
    player_2_url: str
    scores: Optional[str] = None
    walkover: int = Field(default=0, ge=0, le=1)
    winner: Optional[str] = None
    winner_url: Optional[str] = None


class FrameModel(BaseModel):
    match_id: int
    frame_num: int
    player_1_score: int
    player_2_score: int


class BreakModel(BaseModel):
    match_id: int
    frame_num: int
    player_number: int = Field(ge=1, le=2)
    points: int


class RankingModel(BaseModel):
    season: str
    player_name: str
    player_url: str
    start_position: Optional[int] = None
    start_points: Optional[int] = None
    difference: Optional[int] = None
    finish_position: Optional[int] = None
    finish_points: Optional[int] = None

