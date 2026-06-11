import urllib.request

mid = "bf7358e2-ccc6-41b0-9bf6-a35cd10ca2cf"
url = f"http://127.0.0.1:8000/video/{mid}"
req = urllib.request.Request(url, headers={"Range": "bytes=0-1023"})
with urllib.request.urlopen(req) as resp:
    data = resp.read()
    print("status", resp.status)
    print("len", len(data))
    print("content-range", resp.headers.get("Content-Range"))
    print("cache-control", resp.headers.get("Cache-Control"))
