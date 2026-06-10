"""
Load FIFA FC26 squad data and derive GFootball simulation attributes.
"""
import csv
import os
import re
from functools import lru_cache
from typing import Dict, List, Optional, Tuple

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_CSV_PATH = os.path.join(PROJECT_ROOT, "FC26_20250921.csv")

TARGET_LEAGUES = {"Premier League", "La Liga", "Serie A", "Bundesliga"}

# Our seeder team_name -> FIFA club_name in CSV
CLUB_ALIASES: Dict[str, str] = {
    "Bayern Munich": "FC Bayern München",
    "Bayer Leverkusen": "Bayer 04 Leverkusen",
    "Borussia M'gladbach": "Borussia Mönchengladbach",
    "Mainz 05": "1. FSV Mainz 05",
    "Union Berlin": "1. FC Union Berlin",
    "Heidenheim": "1. FC Heidenheim 1846",
    "Werder Bremen": "SV Werder Bremen",
    "TSG Hoffenheim": "TSG 1899 Hoffenheim",
    "St. Pauli": "FC St. Pauli",
    "Bournemouth": "AFC Bournemouth",
    "Fulham": "Fulham FC",
    "Inter Milan": "Inter",
    "Atletico Madrid": "Atlético Madrid",
    "Athletic Bilbao": "Athletic Club",
    "Real Betis": "Real Betis Balompié",
    "Celta Vigo": "RC Celta",
    "Osasuna": "CA Osasuna",
    "Mallorca": "RCD Mallorca",
    "Alaves": "Deportivo Alavés",
    "Espanyol": "RCD Espanyol",
    "Sevilla": "Sevilla FC",
    "Getafe": "Getafe CF",
    "Girona": "Girona FC",
    "Barcelona": "FC Barcelona",
    "Villarreal": "Villarreal CF",
    "Valencia": "Valencia CF",
    "Verona": "Hellas Verona FC",
}

# role, player_position, group, FIFA rating columns, position tags for bonus
SQUAD_SLOTS = [
    ("GK", 0, "GK", ["gk"], ["GK"]),
    ("LB", 1, "DEF", ["lb", "lwb"], ["LB", "LWB"]),
    ("CB", 2, "DEF", ["cb", "lcb"], ["CB"]),
    ("CB", 3, "DEF", ["cb", "rcb"], ["CB"]),
    ("RB", 4, "DEF", ["rb", "rwb"], ["RB", "RWB"]),
    ("LM", 5, "MID", ["lm", "lw"], ["LM", "LW"]),
    ("CM", 6, "MID", ["cm", "lcm", "cdm"], ["CM", "CDM", "CAM"]),
    ("CM", 7, "MID", ["cm", "rcm", "cdm"], ["CM", "CDM", "CAM"]),
    ("RM", 8, "MID", ["rm", "rw"], ["RM", "RW"]),
    ("ST", 9, "FWD", ["st", "cf"], ["ST", "CF"]),
    ("ST", 10, "FWD", ["st", "cf"], ["ST", "CF"]),
]


def _int(row: dict, key: str, default: int = 50) -> int:
    raw = row.get(key, "")
    if raw is None or raw == "":
        return default
    try:
        return int(str(raw).split("+")[0].strip())
    except (TypeError, ValueError):
        return default


def parse_position_rating(value: Optional[str]) -> int:
    if not value:
        return 0
    match = re.match(r"(\d+)", str(value).strip())
    return int(match.group(1)) if match else 0


def overall_to_rating(overall: int) -> int:
    if overall >= 87:
        return 5
    if overall >= 82:
        return 4
    if overall >= 76:
        return 3
    if overall >= 70:
        return 2
    return 1


def _norm_reward(*values: int) -> float:
    if not values:
        return 0.3
    avg = sum(values) / len(values)
    return round(0.2 + (avg / 99.0) * 1.6, 2)


def calc_velocity(row: dict) -> float:
    sprint = _int(row, "movement_sprint_speed")
    accel = _int(row, "movement_acceleration")
    pace = _int(row, "pace")
    composite = (sprint * 0.5 + accel * 0.3 + pace * 0.2) / 99.0
    return float(round(0.85 + composite * 0.45, 2))


def calc_rewards(row: dict, group: str) -> dict:
    if group == "GK":
        return {
            "shooting_reward": 0.1,
            "takeover_reward": 0.2,
            "passing_reward": _norm_reward(
                _int(row, "goalkeeping_kicking"),
                _int(row, "attacking_short_passing"),
            ),
            "defense_reward": _norm_reward(
                _int(row, "goalkeeping_reflexes"),
                _int(row, "goalkeeping_positioning"),
                _int(row, "goalkeeping_diving"),
                _int(row, "goalkeeping_handling"),
            ),
        }
    if group == "FWD":
        return {
            "shooting_reward": _norm_reward(
                _int(row, "attacking_finishing"),
                _int(row, "attacking_volleys"),
                _int(row, "power_long_shots"),
                _int(row, "shooting"),
            ),
            "takeover_reward": _norm_reward(
                _int(row, "skill_dribbling"),
                _int(row, "skill_ball_control"),
                _int(row, "dribbling"),
                _int(row, "movement_agility"),
            ),
            "passing_reward": _norm_reward(
                _int(row, "attacking_short_passing"),
                _int(row, "attacking_crossing"),
                _int(row, "passing"),
            ),
            "defense_reward": round(
                _norm_reward(
                    _int(row, "mentality_positioning"),
                    _int(row, "defending_marking_awareness"),
                )
                * 0.45,
                2,
            ),
        }
    if group == "MID":
        return {
            "shooting_reward": _norm_reward(
                _int(row, "power_long_shots"),
                _int(row, "attacking_finishing"),
                _int(row, "shooting"),
            ),
            "takeover_reward": _norm_reward(
                _int(row, "skill_dribbling"),
                _int(row, "skill_ball_control"),
                _int(row, "dribbling"),
                _int(row, "movement_agility"),
            ),
            "passing_reward": _norm_reward(
                _int(row, "passing"),
                _int(row, "attacking_short_passing"),
                _int(row, "skill_long_passing"),
                _int(row, "mentality_vision"),
            ),
            "defense_reward": _norm_reward(
                _int(row, "defending_marking_awareness"),
                _int(row, "defending_standing_tackle"),
                _int(row, "mentality_interceptions"),
                _int(row, "defending"),
            ),
        }
    # DEF
    return {
        "shooting_reward": _norm_reward(
            _int(row, "power_long_shots"),
            _int(row, "attacking_heading_accuracy"),
        ),
        "takeover_reward": _norm_reward(
            _int(row, "skill_ball_control"),
            _int(row, "dribbling"),
        ),
        "passing_reward": _norm_reward(
            _int(row, "attacking_short_passing"),
            _int(row, "skill_long_passing"),
            _int(row, "passing"),
        ),
        "defense_reward": _norm_reward(
            _int(row, "defending"),
            _int(row, "defending_marking_awareness"),
            _int(row, "defending_standing_tackle"),
            _int(row, "defending_sliding_tackle"),
        ),
    }


def calc_gfr_attributes(row: dict, group: str) -> dict:
    tackle_avg = (
        _int(row, "defending_marking_awareness")
        + _int(row, "defending_standing_tackle")
        + _int(row, "defending_sliding_tackle")
    ) / 3.0
    attrs = {
        "shooting_accuracy": round(_int(row, "attacking_finishing") / 99.0, 2),
        "sprint_stamina": round(_int(row, "power_stamina") / 99.0, 2),
        "tackle_rating": round(tackle_avg / 99.0, 2),
        "pace": _int(row, "pace"),
        "shooting": _int(row, "shooting"),
        "passing": _int(row, "passing"),
        "dribbling": _int(row, "dribbling"),
        "defending": _int(row, "defending"),
        "physic": _int(row, "physic"),
        "acceleration": _int(row, "movement_acceleration"),
        "sprint_speed": _int(row, "movement_sprint_speed"),
        "agility": _int(row, "movement_agility"),
        "reactions": _int(row, "movement_reactions"),
        "stamina": _int(row, "power_stamina"),
        "strength": _int(row, "power_strength"),
        "overall": _int(row, "overall"),
        "potential": _int(row, "potential"),
        "fifa_positions": row.get("player_positions", ""),
        "fifa_player_id": row.get("player_id", ""),
        "preferred_foot": row.get("preferred_foot", ""),
        "work_rate": row.get("work_rate", ""),
    }
    if group == "GK":
        attrs.update({
            "gk_diving": _int(row, "goalkeeping_diving"),
            "gk_handling": _int(row, "goalkeeping_handling"),
            "gk_kicking": _int(row, "goalkeeping_kicking"),
            "gk_positioning": _int(row, "goalkeeping_positioning"),
            "gk_reflexes": _int(row, "goalkeeping_reflexes"),
        })
    return attrs


def resolve_club_name(league_name: str, team_name: str) -> Optional[str]:
    if team_name in CLUB_ALIASES:
        return CLUB_ALIASES[team_name]
    return team_name


def _position_fit_score(row: dict, rating_cols: List[str], pos_tags: List[str]) -> float:
    best_rating = max(parse_position_rating(row.get(col)) for col in rating_cols)
    positions = [p.strip().upper() for p in row.get("player_positions", "").split(",")]
    tag_bonus = 6.0 if any(t.upper() in positions for t in pos_tags) else 0.0
    overall = _int(row, "overall")
    return best_rating + tag_bonus + overall * 0.05


def _row_to_player(row: dict, role: str, pos_idx: int, group: str) -> dict:
    overall = _int(row, "overall")
    return {
        "player_name": row.get("long_name") or row.get("short_name") or "Unknown",
        "role": role,
        "player_position": pos_idx,
        "player_rating": overall_to_rating(overall),
        "age": _int(row, "age", 25),
        "tired_factor": 0.0,
        "velocity": calc_velocity(row),
        "gfr_attributes": calc_gfr_attributes(row, group),
        "rewards": calc_rewards(row, group),
        "player_face_url": row.get("player_face_url") or None,
        "_fifa_overall": overall,
    }


@lru_cache(maxsize=1)
def _load_club_rosters(csv_path: str) -> Dict[Tuple[str, str], List[dict]]:
    rosters: Dict[Tuple[str, str], List[dict]] = {}
    if not os.path.isfile(csv_path):
        return rosters

    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            league = row.get("league_name", "")
            club = row.get("club_name", "")
            if league not in TARGET_LEAGUES or not club:
                continue
            rosters.setdefault((league, club), []).append(row)
    return rosters


def build_roster_from_fc26(
    league_name: str,
    team_name: str,
    csv_path: str = DEFAULT_CSV_PATH,
) -> Tuple[Optional[List[dict]], Optional[int]]:
    """
    Build an 11-man squad from FC26 data.
    Returns (roster, team_rating) or (None, None) if club not found.
    """
    club_rosters = _load_club_rosters(csv_path)
    club_name = resolve_club_name(league_name, team_name)
    squad_rows = club_rosters.get((league_name, club_name))
    if not squad_rows:
        return None, None

    used_ids = set()
    roster = []

    for role, pos_idx, group, rating_cols, pos_tags in SQUAD_SLOTS:
        candidates = []
        for row in squad_rows:
            pid = row.get("player_id")
            if pid in used_ids:
                continue
            score = _position_fit_score(row, rating_cols, pos_tags)
            if score <= 0 and group == "GK":
                continue
            if group == "GK" and "GK" not in row.get("player_positions", "").upper():
                if parse_position_rating(row.get("gk")) < 50:
                    continue
            candidates.append((score, row))

        if not candidates:
            return None, None

        candidates.sort(key=lambda x: x[0], reverse=True)
        _, best_row = candidates[0]
        used_ids.add(best_row.get("player_id"))
        player = _row_to_player(best_row, role, pos_idx, group)
        roster.append(player)

    avg_overall = sum(p.pop("_fifa_overall") for p in roster) / len(roster)
    team_rating = overall_to_rating(int(round(avg_overall)))
    return roster, team_rating


def compute_team_rating_from_roster(roster: List[dict]) -> int:
    overalls = [p.get("gfr_attributes", {}).get("overall", 75) for p in roster]
    if not overalls:
        return 3
    return overall_to_rating(int(round(sum(overalls) / len(overalls))))
