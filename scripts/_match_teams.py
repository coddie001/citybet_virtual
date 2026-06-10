import csv
from utils.seeder import LEAGUE_TEAMS

CSV_PATH = "FC26_20250921.csv"

# Manual aliases: our name -> CSV club_name
ALIASES = {
    "Bayern Munich": "FC Bayern München",
    "Bayer Leverkusen": "Bayer 04 Leverkusen",
    "Borussia M'gladbach": "Borussia Mönchengladbach",
    "Mainz 05": "1. FSV Mainz 05",
    "Union Berlin": "1. FC Union Berlin",
    "Heidenheim": "1. FC Heidenheim 1846",
    "Werder Bremen": "SV Werder Bremen",
    "TSG Hoffenheim": "TSG 1899 Hoffenheim",
    "St. Pauli": "FC St. Pauli",
    "VfL Bochum": None,  # check
    "Holstein Kiel": None,
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
    "Monza": None,
    "Venezia": None,
    "Empoli": None,
    "Leicester City": None,
    "Ipswich Town": None,
    "Southampton": None,
}

clubs = {}
with open(CSV_PATH, newline="", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        key = (row["league_name"], row["club_name"])
        clubs[key] = clubs.get(key, 0) + 1

for league, teams in LEAGUE_TEAMS.items():
    print(f"\n=== {league} ===")
    csv_clubs = {c for (ln, c) in clubs if ln == league}
    for name, *_ in teams:
        alias = ALIASES.get(name, name)
        found = alias in csv_clubs if alias else False
        if not found and alias == name:
            # fuzzy: substring
            matches = [c for c in csv_clubs if name.lower() in c.lower() or c.lower() in name.lower()]
            found = bool(matches)
            alias = matches[0] if matches else alias
        print(f"  {'OK' if found else 'MISS'} {name} -> {alias}")
