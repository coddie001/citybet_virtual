from utils.db import SessionLocal, Player, Team

db = SessionLocal()
team = db.query(Team).filter(Team.team_name == "Manchester City").first()
if team:
    players = (
        db.query(Player)
        .filter(Player.team_id == team.team_id)
        .order_by(Player.player_position)
        .all()
    )
    print(f"Manchester City ({len(players)} players):")
    for p in players:
        ovr = (p.gfr_attributes or {}).get("overall")
        print(f"  {p.role:3} {p.player_name[:35]:35} face={bool(p.player_face_url)} ovr={ovr}")
else:
    print("No Manchester City team found")

total = db.query(Player).count()
with_face = db.query(Player).filter(Player.player_face_url.isnot(None)).count()
print(f"\nAll players: total={total}, with_face_url={with_face}")
db.close()
