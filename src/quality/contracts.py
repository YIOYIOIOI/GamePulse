"""Source contracts: no missing value is silently converted to a business fact."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, field_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


class Product(BaseModel):
    """A monitored game, as recorded in each snapshot so replays never depend on later edits."""

    key: str
    name: str
    app_id: int
    repo: str = ""


class ReviewAuthor(BaseModel):
    model_config = ConfigDict(extra="ignore")
    steamid: str = Field(pattern=r"^\d+$", max_length=25)
    playtime_forever: StrictInt | None = Field(default=None, ge=0)
    playtime_at_review: StrictInt | None = Field(default=None, ge=0)


class SteamReview(BaseModel):
    model_config = ConfigDict(extra="ignore")
    recommendationid: str = Field(pattern=r"^\d+$", max_length=25)
    review: str
    language: str = Field(min_length=1, max_length=50)
    voted_up: StrictBool
    timestamp_created: StrictInt = Field(gt=0)
    timestamp_updated: StrictInt = Field(gt=0)
    votes_up: StrictInt = Field(ge=0)
    author: ReviewAuthor
    steam_purchase: StrictBool | None = None
    received_for_free: StrictBool | None = None


class GithubIssue(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: StrictInt = Field(gt=0)
    number: StrictInt = Field(gt=0)
    title: str
    body: str | None
    html_url: str
    state: Literal["open", "closed"]
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None = None
    labels: list[dict] = Field(default_factory=list)
    pull_request: dict | None = None

    @field_validator("created_at", "updated_at", "closed_at")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("source timestamp must include timezone")
        return value


class GithubRelease(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: StrictInt = Field(gt=0)
    tag_name: str
    name: str | None
    body: str | None
    html_url: str
    published_at: datetime | None
    draft: StrictBool
    prerelease: StrictBool


class SyncRequest(BaseModel):
    # Keys of added games; empty means every added game.
    products: list[str] = Field(default_factory=list, max_length=50)
    days: int = Field(default=180, ge=30, le=730)
    max_reviews: int = Field(default=6000, ge=100, le=20000)
    max_issue_pages: int = Field(default=4, ge=1, le=10)

    @field_validator("products")
    @classmethod
    def distinct(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("每款游戏只能选一次")
        return value


class TriageCreate(BaseModel):
    run_id: str | None = None
    product: str
    title: str = Field(min_length=3, max_length=180)
    evidence_ids: list[str] = Field(min_length=1, max_length=30)
    owner: str = Field(default="", max_length=80)
    note: str = Field(default="", max_length=3000)


class TriageUpdate(BaseModel):
    revision: int = Field(ge=1)
    status: Literal["pending", "investigating", "confirmed", "closed"]
    owner: str = Field(default="", max_length=80)
    note: str = Field(min_length=1, max_length=3000)


class MemberCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    role: Literal["owner", "reviewer", "analyst", "viewer"]


class GameCreate(BaseModel):
    app_id: int = Field(gt=0, lt=10**9)
    repo: str = Field(default="", max_length=200)


class GameUpdate(BaseModel):
    repo: str = Field(default="", max_length=200)
