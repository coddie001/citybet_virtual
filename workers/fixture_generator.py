"""
Round-robin fixture generator and market pricing worker.
"""

import os
import sys
import uuid
import math
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils.db import SessionLocal, Season, Team, Player, Fixture, EventMarket
from utils.fixture_timing import assign_show_at_ms
from utils.fixture_assets import pick_fixture_image_url


def berger_round_robin(teams):
    """Generates Berger round-robin pairings for a list of teams."""
    n = len(teams)
    if n % 2 != 0:
        teams = list(teams) + [None]
        n += 1
    
    rounds = []
    team_list = list(teams)
    for r in range(n - 1):
        pairings = []
        for i in range(n // 2):
            t1 = team_list[i]
            t2 = team_list[n - 1 - i]
            if t1 is not None and t2 is not None:
                if (r + i) % 2 == 0:
                    pairings.append((t1, t2))
                else:
                    pairings.append((t2, t1))
        rounds.append(pairings)
        team_list = [team_list[0]] + [team_list[-1]] + team_list[1:-1]
    return rounds


def calculate_odds(home_team, away_team, home_players, away_players):
    """
    Prices match odds using relative team ratings and player strength.
    Uses bookmaker overround margin of 1.08.
    """
    margin = 1.08
    
    home_p_rating = sum(p.player_rating for p in home_players) / len(home_players) if home_players else 3.0
    away_p_rating = sum(p.player_rating for p in away_players) / len(away_players) if away_players else 3.0
    
    home_rating = getattr(home_team, 'team_rating', 3) or 3
    away_rating = getattr(away_team, 'team_rating', 3) or 3
    
    home_strength = home_rating * 0.6 + home_p_rating * 0.4
    away_strength = away_rating * 0.6 + away_p_rating * 0.4
    
    home_strength_effective = home_strength * 1.1
    total = home_strength_effective + away_strength
    if total <= 0:
        total = 1.0
        
    p_home_win_base = home_strength_effective / total
    prob_home = max(0.05, min(0.85, p_home_win_base * 0.75))
    prob_away = max(0.05, min(0.85, (1.0 - p_home_win_base) * 0.75))
    prob_draw = max(0.10, round(1.0 - prob_home - prob_away, 4))
    
    odds_home = round(margin / prob_home, 2)
    odds_draw = round(margin / prob_draw, 2)
    odds_away = round(margin / prob_away, 2)
    
    expected_goals = max(0.5, 1.6 + 0.2 * (home_strength - away_strength))
    
    prob_over = 0.52
    prob_under = 0.48
    odds_over = round(margin / prob_over, 2)
    odds_under = round(margin / prob_under, 2)
    
    prob_gg = 0.55
    prob_ng = 0.45
    odds_gg = round(margin / prob_gg, 2)
    odds_ng = round(margin / prob_ng, 2)
    
    markets = [
        {"market_name": "1X2", "selection_name": "Home", "odds": odds_home},
        {"market_name": "1X2", "selection_name": "Draw", "odds": odds_draw},
        {"market_name": "1X2", "selection_name": "Away", "odds": odds_away},
        {"market_name": "OU25", "selection_name": "Over 2.5", "odds": odds_over},
        {"market_name": "OU25", "selection_name": "Under 2.5", "odds": odds_under},
        {"market_name": "GGNG", "selection_name": "GG", "odds": odds_gg},
        {"market_name": "GGNG", "selection_name": "NG", "odds": odds_ng},
    ]
    
    predictions = {
        "win_probability": {"home": round(prob_home, 3), "draw": round(prob_draw, 3), "away": round(prob_away, 3)},
        "expected_goals": round(expected_goals, 2),
    }
    
    return markets, predictions


def generate_fixtures_for_season(db: Session, season: Season):
    """Generates round-robin fixtures and dynamically prices market odds for an open season."""
    teams = db.query(Team).filter(Team.season_id == season.season_id).all()
    if not teams or len(teams) < 2:
        print(f"[-] No teams found registered to Season {season.season_id}. Skipping.")
        return
    if len(teams) % 2 != 0:
        print("[-] Odd number of teams. Cannot create symmetrical round robin.")
        return

    print(f"[*] Generating double round-robin fixtures for '{season.tournament_name}'...")
    first_half_rounds = berger_round_robin(teams)
    
    start_date = datetime.now().date() + timedelta(days=1)
    while start_date.weekday() != 5:
        start_date += timedelta(days=1)
        
    sat_times = ['12:30:00', '15:00:00', '15:00:00', '15:00:00', '15:00:00', '17:30:00', '20:00:00']
    sun_times = ['14:00:00', '14:00:00', '16:30:00']
    
    total_rounds = len(first_half_rounds) * 2
    match_count = 0
    market_count = 0
    fixture_index = 0
    
    for gwk in range(1, total_rounds + 1):
        is_second_half = gwk > len(first_half_rounds)
        round_idx = (gwk - 1) % len(first_half_rounds)
        pairings = first_half_rounds[round_idx]
        
        gwk_sat_date = start_date + timedelta(weeks=gwk - 1)
        gwk_sun_date = gwk_sat_date + timedelta(days=1)
        
        for idx, (t1, t2) in enumerate(pairings):
            if is_second_half:
                home, away = t2, t1
            else:
                home, away = t1, t2
                
            if idx < len(sat_times):
                game_date = gwk_sat_date
                time_str = sat_times[idx]
            else:
                game_date = gwk_sun_date
                sun_idx = (idx - len(sat_times)) % len(sun_times)
                time_str = sun_times[sun_idx]
                
            game_time = datetime.strptime(time_str, "%H:%M:%S").time()
            show_at_ms = assign_show_at_ms(fixture_index)
            match_uuid = uuid.uuid4()
            
            img_url = pick_fixture_image_url(home.team_name, away.team_name, home.team_id, away.team_id, gwk)
            
            home_players = db.query(Player).filter(Player.team_id == home.team_id).all()
            away_players = db.query(Player).filter(Player.team_id == away.team_id).all()
            
            markets, predictions = calculate_odds(home, away, home_players, away_players)
            
            fixture = Fixture(
                match_id=match_uuid,
                season_id=season.season_id,
                gameweek=gwk,
                game_date=game_date,
                game_time=game_time,
                show_at_ms=show_at_ms,
                fixture_image_url=img_url,
                home_team_id=home.team_id,
                away_team_id=away.team_id,
                score="0-0",
                predictions=predictions,
                status="upcoming",
                settled=False,
            )
            db.add(fixture)
            match_count += 1
            fixture_index += 1
            
            for m in markets:
                market = EventMarket(
                    market_id=uuid.uuid4(),
                    match_id=match_uuid,
                    market_name=m["market_name"],
                    selection_name=m["selection_name"],
                    odds=m["odds"],
                    status="open",
                    winning_selection=False,
                )
                db.add(market)
                market_count += 1
                
    db.commit()
    print(f"[+] Successfully generated {match_count} fixtures and {market_count} event markets for '{season.tournament_name}'.")


def run_fixture_generator():
    db = SessionLocal()
    try:
        active_seasons = db.query(Season).filter(Season.season_status == "active").all()
        for season in active_seasons:
            count = db.query(Fixture).filter(Fixture.season_id == season.season_id).count()
            if count == 0:
                generate_fixtures_for_season(db, season)
    finally:
        db.close()


if __name__ == "__main__":
    run_fixture_generator()
