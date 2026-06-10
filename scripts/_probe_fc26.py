import csv
from collections import Counter

leagues = {"Premier League", "La Liga", "Serie A", "Bundesliga"}
clubs_by_league = {l: set() for l in leagues}
with open("FC26_20250921.csv", newline="", encoding="utf-8") as f:
    r = csv.DictReader(f)
    for row in r:
        ln = row.get("league_name", "")
        if ln in leagues:
            clubs_by_league[ln].add(row.get("club_name", ""))

for ln in sorted(leagues):
    print(ln, len(clubs_by_league[ln]))
    for c in sorted(clubs_by_league[ln]):
        print(" ", c)
