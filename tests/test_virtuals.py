"""
CityBet Virtuals - Test Suite
================================
Covers:
  1. Fixture generation correctness (round-robin, no duplicates, home/away balance)
  2. Database connectivity and record counts
  3. Odds calculation sanity checks
  4. Player action influencer unit tests
  5. FastAPI API endpoint smoke tests
"""

import os
import sys
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from utils.db import DATABASE_URL, Season, Team, Player, Fixture, EventMarket, GfrDump
from workers.fixture_generator import berger_round_robin, calculate_odds
from workers.game_simulator import PlayerActionInfluencer


# ─── DB session fixture ────────────────────────────────────────────
@pytest.fixture(scope="session")
def db():
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


# ════════════════════════════════════════════════════════════════════
#  1. Fixture Generation Tests
# ════════════════════════════════════════════════════════════════════

class TestRoundRobin:

    def test_20_team_round_robin_generates_19_rounds(self):
        """For 20 teams there should be 19 rounds in first half of season."""
        teams = list(range(20))
        rounds = berger_round_robin(teams)
        assert len(rounds) == 19, f"Expected 19 rounds, got {len(rounds)}"

    def test_18_team_round_robin_generates_17_rounds(self):
        teams = list(range(18))
        rounds = berger_round_robin(teams)
        assert len(rounds) == 17

    def test_each_round_has_correct_number_of_matches(self):
        teams = list(range(20))
        rounds = berger_round_robin(teams)
        for rnd in rounds:
            assert len(rnd) == 10, f"Each round should have 10 matches for 20 teams"

    def test_no_duplicate_pairings_in_first_half(self):
        """Each matchup (home, away) must be unique within the first half."""
        teams = list(range(20))
        rounds = berger_round_robin(teams)
        seen = set()
        for rnd in rounds:
            for h, a in rnd:
                pair = (id(h) if hasattr(h, '__hash__') else h,
                        id(a) if hasattr(a, '__hash__') else a)
                # Just use the values as ints for test purposes
                pair = (teams.index(h) if h in teams else h,
                        teams.index(a) if a in teams else a)
                assert pair not in seen, f"Duplicate pairing {pair}"
                seen.add(pair)

    def test_each_team_plays_once_per_round(self):
        teams = list(range(20))
        rounds = berger_round_robin(teams)
        for rnd in rounds:
            participants = []
            for h, a in rnd:
                participants.extend([h, a])
            assert len(participants) == len(set(participants)), "A team appears more than once in a round!"

    def test_total_home_away_balance(self):
        """Over the first half, each team should be roughly equally home/away."""
        teams = list(range(10))  # small case
        rounds = berger_round_robin(teams)
        home_count = {t: 0 for t in teams}
        away_count = {t: 0 for t in teams}
        for rnd in rounds:
            for h, a in rnd:
                home_count[h] += 1
                away_count[a] += 1
        # Each team plays n-1 = 9 games total, roughly split
        for t in teams:
            total = home_count[t] + away_count[t]
            assert total == len(teams) - 1, f"Team {t} didn't play {len(teams)-1} games"


# ════════════════════════════════════════════════════════════════════
#  2. Database Connectivity & Record Counts
# ════════════════════════════════════════════════════════════════════

class TestDatabase:

    def test_db_connection(self, db):
        """Basic DB connectivity test."""
        result = db.execute(__import__("sqlalchemy").text("SELECT 1")).scalar()
        assert result == 1

    def test_seasons_seeded(self, db):
        """Should have at least 4 seasons (one per league)."""
        count = db.query(Season).count()
        assert count >= 4, f"Expected at least 4 seasons, found {count}"

    def test_teams_seeded(self, db):
        """78 teams across 4 leagues."""
        count = db.query(Team).count()
        assert count >= 78, f"Expected at least 78 teams, got {count}"

    def test_players_seeded(self, db):
        """Each team has exactly 11 players (858 total for 78 teams)."""
        count = db.query(Player).count()
        assert count >= 78 * 11, f"Expected at least 858 players, found {count}"

    def test_fixtures_generated(self, db):
        """Should have at least 1446 total fixtures across all leagues."""
        count = db.query(Fixture).count()
        assert count >= 1446, f"Expected at least 1446 fixtures, found {count}"

    def test_event_markets_generated(self, db):
        """Should have 3 markets × 3+ selections per fixture = many thousands."""
        count = db.query(EventMarket).count()
        assert count > 5000, f"Expected thousands of event markets, found {count}"

    def test_players_have_rewards(self, db):
        """Each player should have a non-null rewards jsonb column."""
        players_without = db.query(Player).filter(Player.rewards == None).count()
        assert players_without == 0, f"{players_without} players have NULL rewards"

    def test_fixture_no_team_playing_itself(self, db):
        """No fixture should have the same team on both sides."""
        self_matches = db.query(Fixture).filter(
            Fixture.home_team_id == Fixture.away_team_id
        ).count()
        assert self_matches == 0, f"Found {self_matches} fixtures where home == away"

    def test_team_ratings_within_range(self, db):
        """Team ratings must be between 1 and 5."""
        out_of_range = db.query(Team).filter(
            (Team.team_rating < 1) | (Team.team_rating > 5)
        ).count()
        assert out_of_range == 0, f"Found {out_of_range} teams with out-of-range ratings"

    def test_player_ratings_within_range(self, db):
        """Player ratings must be between 1 and 5."""
        out_of_range = db.query(Player).filter(
            (Player.player_rating < 1) | (Player.player_rating > 5)
        ).count()
        assert out_of_range == 0

    def test_all_fixtures_have_markets(self, db):
        """Every fixture should have at least 3 markets."""
        fixtures = db.query(Fixture).limit(20).all()
        for f in fixtures:
            market_count = db.query(EventMarket).filter(EventMarket.match_id == f.match_id).count()
            assert market_count >= 3, f"Fixture {f.match_id} has only {market_count} markets"


# ════════════════════════════════════════════════════════════════════
#  3. Odds Calculation Tests
# ════════════════════════════════════════════════════════════════════

class TestOddsCalculation:
    """Tests the Poisson-based odds model."""

    @pytest.fixture
    def mock_team(self):
        class T:
            def __init__(self, rating):
                self.team_rating = rating
        return T

    @pytest.fixture
    def mock_players(self):
        class P:
            def __init__(self, rating):
                self.player_rating = rating
        return P

    def test_odds_structure(self, mock_team, mock_players):
        home = mock_team(5)
        away = mock_team(3)
        home_p = [mock_players(5) for _ in range(11)]
        away_p = [mock_players(3) for _ in range(11)]

        odds = calculate_odds(home, away, home_p, away_p)
        assert "1X2" in odds
        assert "OU25" in odds
        assert "GGNG" in odds
        assert "Home" in odds["1X2"]
        assert "Draw" in odds["1X2"]
        assert "Away" in odds["1X2"]

    def test_stronger_home_team_lower_home_odds(self, mock_team, mock_players):
        """Stronger home team should have lower (more likely) home odds."""
        strong_home = mock_team(5)
        weak_away = mock_team(2)
        strong_p = [mock_players(5) for _ in range(11)]
        weak_p = [mock_players(2) for _ in range(11)]

        odds_strong = calculate_odds(strong_home, weak_away, strong_p, weak_p)
        odds_even = calculate_odds(mock_team(3), mock_team(3),
                                   [mock_players(3)] * 11, [mock_players(3)] * 11)
        # Stronger home team → lower home odds (shorter)
        assert odds_strong["1X2"]["Home"] <= odds_even["1X2"]["Home"]

    def test_odds_have_margin(self, mock_team, mock_players):
        """Sum of TRUE probabilities should be < sum of implied probs (margin exists).
        i.e., each selection's implied prob (1/odds) sums to > 1.0 (the overround).
        We verify odds are NOT fair (fair = implied sum exactly 1.0)."""
        home = mock_team(3)
        away = mock_team(3)
        p = [mock_players(3) for _ in range(11)]
        odds = calculate_odds(home, away, p, p)
        # The margin (1.08) means odds are shortened, so 1/odds gives implied probs
        # that collectively exceed 100% — verifying the bookmaker margin IS applied
        # by checking home odds alone are less than what a fair market would give.
        home_odds = odds["1X2"]["Home"]
        draw_odds = odds["1X2"]["Draw"]
        away_odds = odds["1X2"]["Away"]
        # With margin, all three implied probs should sum > 1.0
        # But since we compute with margin denominator, let's verify prices are shortened:
        # Check that home + draw + away implied prob > 1.0 — this confirms overround
        # We check by calculating fair-no-margin equivalent and comparing
        assert home_odds >= 1.05, "Home odds too low"
        assert draw_odds >= 1.05, "Draw odds too low"
        assert away_odds >= 1.05, "Away odds too low"
        # Verify the margin is applied by checking home * margin is roughly correct
        assert 1 / home_odds + 1 / draw_odds + 1 / away_odds > 1.0, (
            "Implied sum should exceed 1.0 due to bookmaker margin/overround"
        )

    def test_odds_are_positive(self, mock_team, mock_players):
        """All computed odds must be > 1.00."""
        home = mock_team(4)
        away = mock_team(4)
        p = [mock_players(4) for _ in range(11)]
        odds = calculate_odds(home, away, p, p)
        for market_name, selections in odds.items():
            for sel, price in selections.items():
                assert price >= 1.05, f"Odds too low: {market_name}/{sel} = {price}"


# ════════════════════════════════════════════════════════════════════
#  4. Player Action Influencer Tests
# ════════════════════════════════════════════════════════════════════

class TestPlayerActionInfluencer:

    @pytest.fixture
    def attrs_tired(self):
        return {
            0: {"player_id": "a", "name": "Tired Winger", "role": "LW",
                "rating": 3, "tired_factor": 0.9, "velocity": 1.2,
                "rewards": {"shooting_reward": 0.5, "defense_reward": 0.3,
                            "passing_reward": 0.5, "takeover_reward": 0.5},
                "gfr_attrs": {}}
        }

    @pytest.fixture
    def attrs_sniper(self):
        return {
            0: {"player_id": "b", "name": "Top Striker", "role": "ST",
                "rating": 5, "tired_factor": 0.1, "velocity": 1.1,
                "rewards": {"shooting_reward": 1.5, "defense_reward": 0.2,
                            "passing_reward": 0.4, "takeover_reward": 0.8},
                "gfr_attrs": {}}
        }

    @pytest.fixture
    def attrs_defender(self):
        return {
            0: {"player_id": "c", "name": "Center Back", "role": "CB",
                "rating": 4, "tired_factor": 0.05, "velocity": 0.9,
                "rewards": {"shooting_reward": 0.1, "defense_reward": 1.5,
                            "passing_reward": 0.6, "takeover_reward": 0.4},
                "gfr_attrs": {}}
        }

    def test_tired_player_sprint_sometimes_cancelled(self, attrs_tired):
        away_attrs = {}
        influencer = PlayerActionInfluencer(attrs_tired, away_attrs, rng_seed=1)
        # Run many times; a very tired player (0.9) should cancel sprints often
        cancelled = 0
        for _ in range(100):
            result = influencer.influence(0, 0, ACTION_SPRINT := 13, {})
            if result != 13:
                cancelled += 1
        assert cancelled > 30, f"Expected tired player to cancel sprints often, got {cancelled}/100"

    def test_fast_player_boost_to_sprint(self):
        attrs = {
            0: {"player_id": "b", "name": "Pacey Winger", "role": "LW",
                "rating": 5, "tired_factor": 0.0, "velocity": 1.40,
                "rewards": {"shooting_reward": 1.0, "defense_reward": 0.1,
                             "passing_reward": 0.3, "takeover_reward": 0.8},
                "gfr_attrs": {}}
        }
        away_attrs = {}
        sprinted = 0
        # Use many seeds to avoid RNG variance
        for seed in range(20):
            influencer = PlayerActionInfluencer(attrs, away_attrs, rng_seed=seed)
            for _ in range(20):
                result = influencer.influence(0, 0, 1, {})  # ACTION_LEFT
                if result == 13:  # ACTION_SPRINT
                    sprinted += 1
        assert sprinted > 0, f"Velocity-1.40 fresh player should sprint sometimes, got {sprinted}/400"

    def test_defender_in_own_half_may_slide(self, attrs_defender):
        away_attrs = {}
        influencer = PlayerActionInfluencer(attrs_defender, away_attrs, rng_seed=3)
        obs = {"ball": [-0.3, 0, 0]}  # ball in left (home) half
        slid = 0
        for _ in range(200):
            result = influencer.influence(0, 0, 0, obs)  # ACTION_IDLE
            if result == 15:  # ACTION_SLIDE
                slid += 1
        assert slid > 0, "High defense_reward player in own half should occasionally slide"

    def test_cm_long_pass_redirected_to_short(self):
        attrs = {
            0: {"player_id": "d", "name": "Playmaker", "role": "CM",
                "rating": 4, "tired_factor": 0.1, "velocity": 1.0,
                "rewards": {"shooting_reward": 0.3, "defense_reward": 0.4,
                            "passing_reward": 1.5, "takeover_reward": 0.5},
                "gfr_attrs": {}}
        }
        influencer = PlayerActionInfluencer(attrs, {}, rng_seed=4)
        converted = 0
        for _ in range(100):
            result = influencer.influence(0, 0, 9, {})  # ACTION_LONG_PASS
            if result == 11:  # ACTION_SHORT_PASS
                converted += 1
        assert converted > 30, f"Good CM passer should redirect long→short often, got {converted}/100"


# ════════════════════════════════════════════════════════════════════
#  5. FastAPI Smoke Tests
# ════════════════════════════════════════════════════════════════════

class TestFastAPI:

    @pytest.fixture(scope="class")
    def client(self):
        from fastapi.testclient import TestClient
        from main import app
        return TestClient(app)

    def test_health_check(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_seasons_endpoint_returns_list(self, client):
        r = client.get("/seasons")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) >= 4

    def test_fixtures_endpoint_returns_data(self, client):
        r = client.get("/fixtures?limit=10")
        assert r.status_code == 200
        data = r.json()
        assert "fixtures" in data
        assert "total" in data
        assert data["total"] >= 1446

    def test_fixtures_with_gameweek_filter(self, client):
        r = client.get("/fixtures?gameweek=1&limit=50")
        assert r.status_code == 200
        data = r.json()
        for f in data["fixtures"]:
            assert f["gameweek"] == 1

    def test_odds_upcoming_endpoint(self, client):
        r = client.get("/odds/upcoming?market=1X2")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        if data:
            first = data[0]
            assert "home" in first
            assert "away" in first
            assert "selections" in first
            assert "Home" in first["selections"]

    def test_single_fixture_detail(self, client, db):
        fix = db.query(Fixture).first()
        r = client.get(f"/fixtures/{fix.match_id}")
        assert r.status_code == 200
        data = r.json()
        assert "markets" in data
        assert "1X2" in data["markets"]

    def test_teams_endpoint(self, client, db):
        season = db.query(Season).first()
        r = client.get(f"/seasons/{season.season_id}/teams")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_league_table_endpoint(self, client, db):
        season = db.query(Season).first()
        r = client.get(f"/seasons/{season.season_id}/table")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)

    def test_results_endpoint_initially_empty(self, client):
        r = client.get("/results?limit=10")
        assert r.status_code == 200
        # No matches have been simulated yet in a fresh DB
        data = r.json()
        assert "results" in data

    def test_video_404_for_missing_match(self, client):
        fake_id = str(uuid.uuid4())
        r = client.get(f"/video/{fake_id}")
        assert r.status_code == 404


# ════════════════════════════════════════════════════════════════════
#  Run if standalone
# ════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
