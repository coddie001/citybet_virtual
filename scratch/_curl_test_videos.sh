#!/bin/bash
set -e
cd /home/Warta/projects/citybet_virtuals
IDS=(
  "88e1925e-a6f2-4ab5-ae56-bcf41272de3d"
  "33ebd0bc-1d4e-4346-a8d6-efd6fc3e6bac"
  "fc0a1fc4-a190-4cf2-b253-eb64d363d00e"
)
for id in "${IDS[@]}"; do
  echo "=== $id ==="
  curl -sI -H "Range: bytes=0-1023" "http://127.0.0.1:8000/video/$id" | head -5
  ls -la "videos/${id}_full.mp4" 2>&1 || true
done
