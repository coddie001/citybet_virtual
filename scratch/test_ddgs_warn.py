import warnings
warnings.simplefilter("error", RuntimeWarning)
from utils.fixture_image_search import _search_ddg
r = _search_ddg("Liverpool vs Crystal Palace football match 2024", max_results=1)
print("ok", len(r))
