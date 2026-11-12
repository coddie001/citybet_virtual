"""Database models, engine, and session setup for CityBet Virtuals."""

import os
from datetime import datetime
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Time,
    create_engine,
    text,
)
from sqlalchemy.dialects.postgresql import BYTEA, JSONB, UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://citybet_app:CityBet_Virtuals_2026!@localhost:5432/citybet_virtuals",
)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Season(Base):
    __tablename__ = "seasons"
    __table_args__ = {"schema": "public"}

    season_id = Column(UUID(as_uuid=True), primary_key=True)
    tournament_id = Column(UUID(as_uuid=True), nullable=False)
    tournament_name = Column(String(255), nullable=False)
    season_status = Column(String(50), default="upcoming")
    cum_teams = Column(Integer, default=0)
    cum_gwk = Column(Integer, default=38)
    current_gwk = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)


class Team(Base):
    __tablename__ = "teams"
    __table_args__ = {"schema": "public"}

    team_id = Column(UUID(as_uuid=True), primary_key=True)
    season_id = Column(UUID(as_uuid=True), nullable=True)
    league_name = Column(String(255), nullable=True)
    team_name = Column(String(255), nullable=False)
    league_rank = Column(Integer, nullable=True)
    team_rating = Column(Integer, nullable=True)
    team_data = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Player(Base):
    __tablename__ = "players"
    __table_args__ = {"schema": "public"}

    player_id = Column(UUID(as_uuid=True), primary_key=True)
    team_id = Column(UUID(as_uuid=True), nullable=True)
    player_name = Column(String(255), nullable=False)
    role = Column(String(10), nullable=True)
    player_position = Column(Integer, nullable=True)
    player_rating = Column(Integer, nullable=True)
    age = Column(Integer, nullable=True)
    tired_factor = Column(Numeric(4, 3), default=0.0)
    velocity = Column(Numeric(5, 2), nullable=True)
    gfr_attributes = Column(JSONB, nullable=True)
    rewards = Column(JSONB, default=dict)
    player_face_url = Column(String(500), nullable=True)
    goals = Column(Integer, default=0)
    assists = Column(Integer, default=0)
    appearances = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class Fixture(Base):
    __tablename__ = "fixtures"
    __table_args__ = {"schema": "public"}

    match_id = Column(UUID(as_uuid=True), primary_key=True)
    season_id = Column(UUID(as_uuid=True), nullable=True)
    gameweek = Column(Integer, nullable=False)
    game_date = Column(Date, nullable=False)
    game_time = Column(Time, nullable=False)
    show_at_ms = Column(BigInteger, nullable=False, default=0)
    fixture_image_url = Column(String(500), nullable=True)
    home_team_id = Column(UUID(as_uuid=True), nullable=True)
    away_team_id = Column(UUID(as_uuid=True), nullable=True)
    score = Column(String(10), default="0-0")
    predictions = Column(JSONB, nullable=True)
    outcome = Column(JSONB, nullable=True)
    settled = Column(Boolean, default=False)
    status = Column(String(50), default="upcoming")
    stats_recorded = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class EventMarket(Base):
    __tablename__ = "event_markets"
    __table_args__ = {"schema": "public"}

    market_id = Column(UUID(as_uuid=True), primary_key=True)
    match_id = Column(UUID(as_uuid=True), nullable=True)
    market_category = Column(UUID(as_uuid=True), nullable=True)
    market_name = Column(String(255), nullable=False)
    selection_name = Column(String(255), nullable=False)
    odds = Column(Numeric(5, 2), nullable=False)
    prize = Column(Numeric(10, 2), nullable=True)
    number_of_winners = Column(Integer, default=0)
    twin_market_id = Column(UUID(as_uuid=True), nullable=True)
    twin_market_name = Column(String(255), nullable=True)
    twin_odds = Column(Numeric(5, 2), nullable=True)
    status = Column(String(50), default="open")
    winning_selection = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class GfrDump(Base):
    __tablename__ = "gfr_dumps"
    __table_args__ = {"schema": "public"}

    dump_id = Column(UUID(as_uuid=True), primary_key=True)
    match_id = Column(UUID(as_uuid=True), nullable=True)
    season_id = Column(UUID(as_uuid=True), nullable=True)
    gameweek = Column(Integer, nullable=True)
    home_team_id = Column(UUID(as_uuid=True), nullable=True)
    away_team_id = Column(UUID(as_uuid=True), nullable=True)
    gfr_game_dump_file = Column(String(500), nullable=True)
    video_url = Column(String(500), nullable=True)
    gfr_stats = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    match_video = Column(BYTEA, nullable=True)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
