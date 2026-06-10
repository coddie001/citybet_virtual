"""Live league table / leaderboard computation from completed fixtures."""
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from utils.db import Team, Fixture


def _parse_score(score: str) -> Optional[tuple]:
    try:
        home_g, away_g = map(int, score.split("-"))
        return home_g, away_g
    except (ValueError, AttributeError, TypeError):
        return None


def _result_for_team(fixture: Fixture, team_id: uuid.UUID) -> str:
    parsed = _parse_score(fixture.score)
    if not parsed:
        return "D"
    home_g, away_g = parsed
    is_home = fixture.home_team_id == team_id
    if is_home:
        if home_g > away_g:
            return "W"
        if home_g < away_g:
            return "L"
        return "D"
    if away_g > home_g:
        return "W"
    if away_g < home_g:
        return "L"
    return "D"


def build_team_form(
    db: Session, season_id: uuid.UUID, team_id: uuid.UUID, limit: int = 5
) -> List[str]:
    """Last N results for a team (oldest → newest, for left-to-right form dots)."""
    fixtures = (
        db.query(Fixture)
        .filter(
            Fixture.season_id == season_id,
            Fixture.status == "completed",
            or_(Fixture.home_team_id == team_id, Fixture.away_team_id == team_id),
        )
        .order_by(
            Fixture.show_at_ms.desc(),
            Fixture.game_date.desc(),
            Fixture.game_time.desc(),
        )
        .limit(limit)
        .all()
    )
    fixtures.reverse()
    return [_result_for_team(f, team_id) for f in fixtures]


def build_league_table(db: Session, season_id: uuid.UUID) -> List[Dict[str, Any]]:
    """Compute current standings from completed fixtures (live leaderboard)."""
    teams = db.query(Team).filter(Team.season_id == season_id).all()
    if not teams:
        return []

    table_stats = {
        t.team_id: {
            "team_id": str(t.team_id),
            "team_name": t.team_name,
            "league_name": t.league_name,
            "team_rating": t.team_rating,
            "points": 0,
            "played": 0,
            "wins": 0,
            "draws": 0,
            "losses": 0,
            "goals_scored": 0,
            "goals_conceded": 0,
            "goal_diff": 0,
            "last_5": [],
        }
        for t in teams
    }

    completed = db.query(Fixture).filter(
        Fixture.season_id == season_id,
        Fixture.status == "completed",
    ).all()

    for f in completed:
        parsed = _parse_score(f.score)
        if not parsed:
            continue
        home_g, away_g = parsed

        if f.home_team_id not in table_stats or f.away_team_id not in table_stats:
            continue

        h = table_stats[f.home_team_id]
        a = table_stats[f.away_team_id]

        h["played"] += 1
        a["played"] += 1
        h["goals_scored"] += home_g
        h["goals_conceded"] += away_g
        a["goals_scored"] += away_g
        a["goals_conceded"] += home_g
        h["goal_diff"] += home_g - away_g
        a["goal_diff"] += away_g - home_g

        if home_g > away_g:
            h["points"] += 3
            h["wins"] += 1
            a["losses"] += 1
        elif away_g > home_g:
            a["points"] += 3
            a["wins"] += 1
            h["losses"] += 1
        else:
            h["points"] += 1
            a["points"] += 1
            h["draws"] += 1
            a["draws"] += 1

    sorted_rows = sorted(
        table_stats.values(),
        key=lambda x: (x["points"], x["goal_diff"], x["goals_scored"]),
        reverse=True,
    )
    for rank, row in enumerate(sorted_rows, 1):
        row["rank"] = rank
        row["last_5"] = build_team_form(
            db, season_id, uuid.UUID(row["team_id"]), limit=5
        )
    return sorted_rows


def build_leaderboard_payload(db: Session, season_id: uuid.UUID) -> Dict[str, Any]:
    """Full leaderboard document for API responses."""
    season = db.query(__import__("utils.db", fromlist=["Season"]).Season).filter(
        __import__("utils.db", fromlist=["Season"]).Season.season_id == season_id
    ).first()
    # Avoid circular import hack - import Season at top level
    from utils.db import Season

    season = db.query(Season).filter(Season.season_id == season_id).first()
    if not season:
        return {}

    completed_count = (
        db.query(Fixture)
        .filter(Fixture.season_id == season_id, Fixture.status == "completed")
        .count()
    )
    return {
        "season_id": str(season.season_id),
        "tournament_name": season.tournament_name,
        "league_name": " ".join(season.tournament_name.split()[:-1]),
        "current_gwk": season.current_gwk,
        "completed_matches": completed_count,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "table": build_league_table(db, season_id),
    }


def persist_league_table(db: Session, season_id: uuid.UUID) -> Optional[Dict[str, Any]]:
    """Write computed ranks back to teams.league_rank. Returns leader summary for logging."""
    rows = build_league_table(db, season_id)
    team_map = {
        str(t.team_id): t
        for t in db.query(Team).filter(Team.season_id == season_id).all()
    }
    for row in rows:
        team = team_map.get(row["team_id"])
        if not team:
            continue
        team.league_rank = row["rank"]
        if not team.team_data:
            team.team_data = {}
        team.team_data["live_table"] = {
            "points": row["points"],
            "played": row["played"],
            "wins": row["wins"],
            "draws": row["draws"],
            "losses": row["losses"],
            "goals_scored": row["goals_scored"],
            "goals_conceded": row["goals_conceded"],
            "goal_diff": row["goal_diff"],
            "last_5": row["last_5"],
        }
    db.commit()
    if not rows:
        return None
    leader = rows[0]
    return {
        "leader": leader["team_name"],
        "points": leader["points"],
        "played": leader["played"],
    }
