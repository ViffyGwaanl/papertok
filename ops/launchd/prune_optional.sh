#!/usr/bin/env bash
set -euo pipefail

# Unload and disable (rename) optional/heavy one-shot LaunchAgents.
# These jobs are deprecated in favor of Admin → Jobs enqueue.

DST_DIR="$HOME/Library/LaunchAgents"
TS=$(date +%Y%m%d-%H%M%S)

optional=(
  com.papertok.content_analysis.plist
  com.papertok.image_caption.plist
  com.papertok.image_caption_regen.plist
  com.papertok.paper_images.plist
  com.papertok.paper_images_regen.plist
  com.papertok.paper_images_glm_today.plist
  com.papertok.paper_images_glm_backfill.plist
)

for f in "${optional[@]}"; do
  path="$DST_DIR/$f"
  if [ ! -f "$path" ]; then
    continue
  fi

  echo "unload: $path"
  launchctl unload "$path" 2>/dev/null || true

  echo "disable: $path"
  mv -f "$path" "$path.disabled.$TS"
done

echo "OK: optional one-shot agents disabled (renamed with .disabled.$TS)."
