#!/usr/bin/env bash
# Fix MP4 files that don't have moov-at-start (required for browser streaming)
VIDEO_DIR="/home/Warta/projects/citybet_virtuals/videos"

for f in \
  "114354b1-4298-4688-94c3-6032fa1a2fbe_full.mp4" \
  "7c8c6f8a-45a1-4e84-8588-d8bfe87e09f0_full.mp4" \
  "b95a777d-21bc-4244-9062-bfea93bb00c6_full.mp4" \
  "da6e96d0-e19d-4f6f-8c27-9e1f88600b68_full.mp4"
do
  SRC="$VIDEO_DIR/$f"
  TMP="$VIDEO_DIR/${f%.mp4}_faststart_tmp.mp4"
  
  if [ ! -f "$SRC" ]; then
    echo "SKIP (not found): $f"
    continue
  fi
  
  echo "Fixing: $f ..."
  ffmpeg -y -i "$SRC" -c copy -movflags faststart "$TMP" 2>/dev/null
  
  if [ $? -eq 0 ] && [ -f "$TMP" ]; then
    mv "$TMP" "$SRC"
    echo "  DONE: $f"
  else
    rm -f "$TMP"
    echo "  FAILED: $f"
  fi
done

echo ""
echo "All done."
