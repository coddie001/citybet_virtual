"""
Database seeder for CityBet Virtuals — creates starting 4 leagues,
teams, and player rosters.
"""

import os
import sys
import uuid
import random
from typing import Tuple, Optional, List
from sqlalchemy.orm import Session

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils.db import SessionLocal, Season, Team, Player
from utils.fc26_loader import build_roster_from_fc26

LEAGUE_TEAMS = {
    'Premier League': [
        ('Manchester City', 'SkyBlue', 'White', 5),
        ('Arsenal', 'Red', 'White', 5),
        ('Liverpool', 'Red', 'Red', 5),
        ('Aston Villa', 'Navy', 'White', 4),
        ('Tottenham Hotspur', 'White', 'Navy', 4),
        ('Chelsea', 'Blue', 'Blue', 4),
        ('Manchester United', 'Red', 'Black', 4),
        ('Newcastle United', 'Black', 'Black', 4),
        ('West Ham United', 'Navy', 'White', 3),
        ('Brighton & Hove Albion', 'Blue', 'White', 3),
        ('Bournemouth', 'Red', 'Black', 3),
        ('Crystal Palace', 'Blue', 'Red', 3),
        ('Wolverhampton Wanderers', 'Orange', 'Black', 3),
        ('Fulham', 'White', 'Black', 3),
        ('Everton', 'Blue', 'White', 3),
        ('Brentford', 'Red', 'White', 3),
        ('Nottingham Forest', 'Red', 'White', 3),
        ('Leicester City', 'Blue', 'White', 3),
        ('Ipswich Town', 'Blue', 'White', 3),
        ('Southampton', 'Red', 'White', 3)
    ],
    'La Liga': [
        ('Real Madrid', 'White', 'White', 5),
        ('Barcelona', 'Navy', 'Red', 5),
        ('Girona', 'Red', 'White', 4),
        ('Atletico Madrid', 'Red', 'Navy', 5),
        ('Athletic Bilbao', 'Red', 'Black', 4),
        ('Real Sociedad', 'Blue', 'White', 4),
        ('Real Betis', 'Green', 'White', 3),
        ('Villarreal', 'Yellow', 'Yellow', 4),
        ('Valencia', 'White', 'Black', 3),
        ('Sevilla', 'White', 'White', 3),
        ('Celta Vigo', 'SkyBlue', 'White', 3),
        ('Osasuna', 'Red', 'Navy', 3),
        ('Getafe', 'Blue', 'Blue', 3),
        ('Mallorca', 'Red', 'Black', 3),
        ('Las Palmas', 'Yellow', 'Blue', 3),
        ('Alaves', 'Blue', 'White', 3),
        ('Leganes', 'Blue', 'White', 3),
        ('Rayo Vallecano', 'White', 'White', 3),
        ('Valladolid', 'Navy', 'White', 3),
        ('Espanyol', 'Blue', 'White', 3)
    ],
    'Serie A': [
        ('Inter Milan', 'Blue', 'Black', 5),
        ('AC Milan', 'Red', 'Black', 5),
        ('Juventus', 'Black', 'White', 5),
        ('Atalanta', 'Blue', 'Black', 4),
        ('Bologna', 'Navy', 'White', 4),
        ('Roma', 'Red', 'White', 4),
        ('Lazio', 'SkyBlue', 'White', 4),
        ('Fiorentina', 'Navy', 'Navy', 3),
        ('Napoli', 'SkyBlue', 'White', 4),
        ('Torino', 'Red', 'White', 3),
        ('Genoa', 'Red', 'Navy', 3),
        ('Monza', 'Red', 'White', 3),
        ('Verona', 'Blue', 'Yellow', 3),
        ('Cagliari', 'Red', 'Navy', 3),
        ('Lecce', 'Yellow', 'Red', 3),
        ('Udinese', 'Black', 'Black', 3),
        ('Parma', 'White', 'Black', 3),
        ('Como', 'Blue', 'White', 3),
        ('Venezia', 'Black', 'Black', 3),
        ('Empoli', 'Blue', 'Blue', 3)
    ],
    'Bundesliga': [
        ('Bayern Munich', 'Red', 'White', 5),
        ('Bayer Leverkusen', 'Black', 'Black', 5),
        ('VfB Stuttgart', 'White', 'White', 4),
        ('Borussia Dortmund', 'Yellow', 'Black', 5),
        ('RB Leipzig', 'White', 'Red', 4),
        ('Eintracht Frankfurt', 'Black', 'Black', 4),
        ('TSG Hoffenheim', 'Blue', 'White', 3),
        ('Heidenheim', 'Red', 'Blue', 3),
        ('Werder Bremen', 'Green', 'White', 3),
        ('SC Freiburg', 'Red', 'White', 3),
        ('FC Augsburg', 'White', 'Green', 3),
        ('VfL Wolfsburg', 'Green', 'Green', 3),
        ('Mainz 05', 'Red', 'White', 3),
        ("Borussia M'gladbach", 'White', 'White', 3),
        ('Union Berlin', 'Red', 'White', 3),
        ('VfL Bochum', 'Blue', 'White', 3),
        ('St. Pauli', 'Brown', 'White', 3),
        ('Holstein Kiel', 'Blue', 'White', 3)
    ]
}

STAR_PLAYERS = {
    'Manchester City': ['Erling Haaland', 'Kevin De Bruyne', 'Phil Foden', 'Rodri'],
    'Arsenal': ['Bukayo Saka', 'Martin Odegaard', 'Declan Rice', 'William Saliba'],
    'Liverpool': ['Mohamed Salah', 'Virgil van Dijk', 'Trent Alexander-Arnold', 'Luis Diaz'],
    'Chelsea': ['Cole Palmer', 'Nicolas Jackson', 'Enzo Fernandez', 'Moises Caicedo'],
    'Manchester United': ['Bruno Fernandes', 'Marcus Rashford', 'Alejandro Garnacho', 'Rasmus Hojlund'],
    'Real Madrid': ['Kylian Mbappe', 'Jude Bellingham', 'Vinicius Junior', 'Federico Valverde'],
    'Barcelona': ['Robert Lewandowski', 'Lamine Yamal', 'Pedri', 'Raphinha'],
    'Bayern Munich': ['Harry Kane', 'Jamal Musiala', 'Leroy Sane', 'Joshua Kimmich'],
    'Bayer Leverkusen': ['Florian Wirtz', 'Granit Xhaka', 'Victor Boniface', 'Jeremie Frimpong'],
    'Borussia Dortmund': ['Serhou Guirassy', 'Julian Brandt', 'Emre Can', 'Nico Schlotterbeck'],
    'Inter Milan': ['Lautaro Martinez', 'Marcus Thuram', 'Nicolo Barella', 'Hakan Calhanoglu'],
    'AC Milan': ['Rafael Leao', 'Christian Pulisic', 'Alvaro Morata', 'Theo Hernandez'],
    'Juventus': ['Dusan Vlahovic', 'Kenan Yildiz', 'Teun Koopmeiners', 'Gleison Bremer'],
    'Napoli': ['Victor Osimhen', 'Khvicha Kvaratskhelia', 'Romelu Lukaku', 'Frank Anguissa']
}

PLAYER_NAMES_POOL = {
    'GK': ['Ederson', 'Alisson', 'Raya', 'Ramsdale', 'Vicario', 'Martinez', 'Onana', 'Courtois', 'Ter Stegen', 'Oblak', 'Sommer', 'Maignan', 'Di Gregorio', 'Neuer', 'Hradecky', 'Kobel'],
    'DEF': ['Gabriel', 'Saliba', 'Dias', 'Stones', 'Walker', 'Gvardiol', 'Van Dijk', 'Konate', 'Ake', 'White', 'James', 'Chilwell', 'Shaw', 'Martinez', 'Dalot', 'Romero', 'Van de Ven', 'Udogie', 'Trippier', 'Schar', 'Botman', 'Militao', 'Rudiger', 'Carvajal', 'Mendy', 'Araujo', 'Kounde', 'Cubarsi', 'Balde', 'Bastoni', 'Acerbi', 'Pavard', 'Dimarco', 'Tomori', 'Thiaw', 'Calabria', 'Gatti', 'Bremer', 'Danilo', 'Kim', 'Upamecano', 'Tah', 'Tapsoba', 'Hincapie', 'Grimaldo', 'Schlotterbeck', 'Sule'],
    'MID': ['Rodri', 'Kovacic', 'Gundogan', 'Rice', 'Odegaard', 'Partey', 'Jorginho', 'Mac Allister', 'Szoboszlai', 'Jones', 'Fernandez', 'Caicedo', 'Gallagher', 'Fernandes', 'Mainoo', 'Casemiro', 'Eriksen', 'Madison', 'Bentancur', 'Bellingham', 'Valverde', 'Tchouameni', 'Camavinga', 'Modric', 'Pedri', 'Gavi', 'De Jong', 'De Paul', 'Koke', 'Llorente', 'Barella', 'Calhanoglu', 'Mkhitaryan', 'Frattesi', 'Reijnders', 'Loftus-Cheek', 'Koopmeiners', 'Locatelli', 'Anguissa', 'Musiala', 'Kimmich', 'Goretzka', 'Palacios', 'Xhaka', 'Andrich', 'Brandt', 'Sabitzer', 'Wirtz'],
    'FWD': ['Haaland', 'Foden', 'Saka', 'Salah', 'Diaz', 'Jota', 'Nunez', 'Palmer', 'Jackson', 'Madueke', 'Rashford', 'Hojlund', 'Garnacho', 'Son', 'Solanke', 'Isak', 'Gordon', 'Mbappe', 'Vinicius', 'Rodrygo', 'Endrick', 'Lewandowski', 'Yamal', 'Raphinha', 'Griezmann', 'Sorloth', 'Martinez', 'Thuram', 'Leao', 'Pulisic', 'Morata', 'Vlahovic', 'Yildiz', 'Lukaku', 'Kvaratskhelia', 'Boniface', 'Schick', 'Kane', 'Sane', 'Coman', 'Gnabry', 'Guirassy', 'Adeyemi', 'Malen']
}


def _generate_random_player_roster(team_name, team_rating):
    players = []
    positions = [
        ('GK', 0, 'GK'),
        ('LB', 1, 'DEF'),
        ('CB', 2, 'DEF'),
        ('CB', 3, 'DEF'),
        ('RB', 4, 'DEF'),
        ('LM', 5, 'MID'),
        ('CM', 6, 'MID'),
        ('CM', 7, 'MID'),
        ('RM', 8, 'MID'),
        ('ST', 9, 'FWD'),
        ('ST', 10, 'FWD')
    ]
    used_names = set()
    stars = list(STAR_PLAYERS.get(team_name, []))

    for role, pos_idx, group in positions:
        name = None
        is_star = False
        
        if group == 'FWD' and stars and random.random() < 0.6:
            name = stars.pop(0)
            is_star = True
        elif group == 'MID' and stars and random.random() < 0.4:
            name = stars.pop(0)
            is_star = True
        elif group == 'DEF' and stars and random.random() < 0.2:
            name = stars.pop(0)
            is_star = True
            
        if not name:
            pool = PLAYER_NAMES_POOL.get(group, PLAYER_NAMES_POOL['MID'])
            random.shuffle(pool)
            for p_name in pool:
                if p_name not in used_names:
                    name = p_name
                    used_names.add(p_name)
                    break
            if not name:
                name = f"Player #{pos_idx + 1}"
                
        base_rating = max(1, min(5, team_rating + random.choice([-1, 0, 1])))
        if is_star:
            base_rating = max(4, base_rating)
            
        age = random.randint(18, 35)
        tired_factor = 0.0
        velocity = round(random.uniform(0.9, 1.3), 2)
        
        rewards = {
            'shooting_reward': round(random.uniform(0.8, 1.5), 2) if group in ('FWD', 'MID') else 0.5,
            'takeover_reward': round(random.uniform(0.8, 1.4), 2) if group in ('FWD', 'MID') else 0.5,
            'passing_reward': round(random.uniform(0.8, 1.4), 2) if group in ('MID', 'DEF') else 0.5,
            'defense_reward': round(random.uniform(0.8, 1.5), 2) if group in ('DEF', 'GK') else 0.3,
        }
        
        gfr_attrs = {
            'shooting_accuracy': round(random.uniform(0.6, 0.95), 2),
            'sprint_stamina': round(random.uniform(0.7, 0.98), 2),
            'tackle_rating': round(random.uniform(0.5, 0.92), 2),
        }
        
        players.append({
            'player_name': name,
            'role': role,
            'player_position': pos_idx,
            'player_rating': base_rating,
            'age': age,
            'tired_factor': tired_factor,
            'velocity': velocity,
            'gfr_attributes': gfr_attrs,
            'rewards': rewards,
            'player_face_url': None,
        })
        
    return players


def generate_player_roster(team_name: str, team_rating: int, league_name: Optional[str] = None):
    """Prefer FC26 dataset; fall back to synthetic roster for unmapped clubs."""
    if league_name:
        fc26_roster, fc26_rating = build_roster_from_fc26(league_name, team_name)
        if fc26_roster:
            return fc26_roster, fc26_rating
    return _generate_random_player_roster(team_name, team_rating), team_rating


def seed_database():
    print("[*] Starting CityBet Virtuals database seeding...")
    db = SessionLocal()
    try:
        existing_seasons = db.query(Season).count()
        if existing_seasons > 0:
            print("[+] Database already has season data. Seeding skipped.")
            db.close()
            return
            
        for league_name, teams_list in LEAGUE_TEAMS.items():
            print(f"[*] Seeding league: {league_name}...")
            season_uuid = uuid.uuid4()
            tournament_uuid = uuid.uuid4()
            
            season = Season(
                season_id=season_uuid,
                tournament_id=tournament_uuid,
                tournament_name=f"{league_name} 2026",
                season_status="active",
                cum_teams=len(teams_list),
                cum_gwk=38 if len(teams_list) == 20 else 34,
                current_gwk=1,
            )
            db.add(season)
            db.commit()
            
            for team_name, shirt, short, rating in teams_list:
                team_uuid = uuid.uuid4()
                team_data = {
                    'shirt_color': shirt,
                    'short_color': short,
                    'style_of_play': 'Balanced',
                    'style_of_attack': 'Attacking',
                    'style_of_ball_control': 'Tiki-Taka',
                    'style_of_defense': 'High press',
                }
                team = Team(
                    team_id=team_uuid,
                    season_id=season_uuid,
                    league_name=league_name,
                    team_name=team_name,
                    league_rank=1,
                    team_rating=rating,
                    team_data=team_data,
                )
                db.add(team)
                db.commit()
                
                roster, squad_rating = generate_player_roster(team_name, rating, league_name)
                for p in roster:
                    player = Player(
                        player_id=uuid.uuid4(),
                        team_id=team_uuid,
                        player_name=p['player_name'],
                        role=p['role'],
                        player_position=p['player_position'],
                        player_rating=p['player_rating'],
                        age=p['age'],
                        tired_factor=p.get('tired_factor', 0.0),
                        velocity=p.get('velocity', 1.0),
                        gfr_attributes=p.get('gfr_attributes', {}),
                        rewards=p.get('rewards', {}),
                        player_face_url=p.get('player_face_url'),
                    )
                    db.add(player)
                db.commit()
                
            print(f"  [+] Seeded {len(teams_list)} teams & rosters for {league_name}.")
            
        print("✅ Database successfully seeded!")
    except Exception as e:
        db.rollback()
        print(f"[-] Database seeding failed: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
