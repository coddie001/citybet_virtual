from utils.video_paths import resolve_streamable_video, video_path_for
from utils.video_faststart import mp4_has_moov_at_start
import uuid

match_id = uuid.UUID("114354b1-4298-4688-94c3-6032fa1a2fbe")
path = video_path_for(match_id)
print("path:", path)
print("exists:", path.is_file())
print("size:", path.stat().st_size if path.is_file() else "N/A")
if path.is_file():
    print("moov at start:", mp4_has_moov_at_start(path))

result = resolve_streamable_video(match_id)
print("resolve_streamable_video:", result)
