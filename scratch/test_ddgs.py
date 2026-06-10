from ddgs import DDGS

with DDGS() as ddgs:
    r = list(ddgs.images("Arsenal football match action", max_results=1))
print("ok", len(r), list(r[0].keys()) if r else [])
