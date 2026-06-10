"""Post-match player stats aggregation (no simulation changes required)."""
from typing import List

from sqlalchemy.orm import Session

from utils.db import Fixture, Player, Team


SCORING_ROLES = ("ST", "FWD", "CF", "LW", "RW", "LM", "RM", "CAM", "CM")


def _scoring_order(players: List[Player]) -> List[Player]:
    role_rank = {r: i for i, r in enumerate(SCORING_ROLES)}
    return sorted(
        players,
        key=lambda p: (
            role_rank.get(p.role or "", 99),
            -(p.player_rating or 0),
            p.player_position or 0,
        ),
    )


def _distribute_goals(players: List[Player], goals: int) -> dict:
    """Credit goals to attacking players when per-scorer data is unavailable."""
    if goals <= 0:
        return {}
    scorers = _scoring_order([p for p in players if p.role != "GK"])
    if not scorers:
        scorers = players
    credits = {}
    for i in range(goals):
        scorer = scorers[i % len(scorers)]
        credits[scorer.player_id] = credits.get(scorer.player_id, 0) + 1
    return credits


def record_match_stats(db: Session, fixture: Fixture) -> None:
    """Update appearances and goal counts for a completed fixture."""
    if fixture.stats_recorded or fixture.status != "completed":
        return

    try:
        home_g, away_g = map(int, fixture.score.split("-"))
    except (ValueError, AttributeError):
        return

    home_players = db.query(Player).filter(Player.team_id == fixture.home_team_id).all()
    away_players = db.query(Player).filter(Player.team_id == fixture.away_team_id).all()

    for p in home_players + away_players:
        p.appearances = (p.appearances or 0) + 1

    for pid, count in _distribute_goals(home_players, home_g).items():
        player = next((p for p in home_players if p.player_id == pid), None)
        if player:
            player.goals = (player.goals or 0) + count

    for pid, count in _distribute_goals(away_players, away_g).items():
        player = next((p for p in away_players if p.player_id == pid), None)
        if player:
            player.goals = (player.goals or 0) + count

    fixture.stats_recorded = True
    db.commit()


def process_pending_match_stats(db: Session) -> int:
    """Aggregate stats for completed fixtures not yet recorded."""
    pending = db.query(Fixture).filter(
        Fixture.status == "completed",
        Fixture.stats_recorded.isnot(True),
    ).all()
    for fixture in pending:
        record_match_stats(db, fixture)
    return len(pending)


def get_top_scorers(db: Session, season_id, limit: int = 20) -> List[dict]:
    rows = (
        db.query(Player, Team)
        .join(Team, Player.team_id == Team.team_id)
        .filter(Team.season_id == season_id)
        .order_by(Player.goals.desc().nullslast(), Player.appearances.desc().nullslast())
        .limit(limit)
        .all()
    )
    return [
        {
            "rank": idx + 1,
            "player_id": str(p.player_id),
            "player_name": p.player_name,
            "team_id": str(t.team_id),
            "team_name": t.team_name,
            "role": p.role,
            "goals": p.goals or 0,
            "assists": p.assists or 0,
            "appearances": p.appearances or 0,
            "player_face_url": p.player_face_url,
        }
        for idx, (p, t) in enumerate(rows)
        if (p.goals or 0) > 0 or idx < limit
    ]
