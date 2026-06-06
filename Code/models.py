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
