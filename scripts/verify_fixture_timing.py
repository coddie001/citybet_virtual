import uuid
from utils.fixture_timing import assign_show_at_ms, FIXTURE_INTERVAL_MS
from utils.fixture_assets import pick_fixture_image_url

print("interval_ms", FIXTURE_INTERVAL_MS)
print("gw1 m0", assign_show_at_ms(0))
print("gw1 m1", assign_show_at_ms(1))
print("gw2 m0 (10th match)", assign_show_at_ms(10))
url = pick_fixture_image_url("Liverpool", "Crystal Palace", uuid.uuid4(), uuid.uuid4(), 1)
print("liverpool-palace", url)
