#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
: "${SO101_FOLLOWER_BY_ID:?Set SO101_FOLLOWER_BY_ID to the Follower /dev/serial/by-id path}"
: "${SO101_TASK1_DATASET:?Set SO101_TASK1_DATASET}"
: "${SO101_TASK1_POSE:?Set SO101_TASK1_POSE}"
: "${SO101_TASK2_DATASET:?Set SO101_TASK2_DATASET}"
: "${SO101_TASK2_POSE:?Set SO101_TASK2_POSE}"
: "${SO101_TASK3_DATASET:?Set SO101_TASK3_DATASET}"
: "${SO101_TASK3_POSE:?Set SO101_TASK3_POSE}"
FOLLOWER_LINK="$SO101_FOLLOWER_BY_ID"
# The existing executor matches canonical comports() names, not symlink aliases.
if ! F_PORT=$(readlink -e -- "$FOLLOWER_LINK"); then
  echo "Follower USB board not found: $FOLLOWER_LINK" >&2
  exit 1
fi
exec "$HOME/miniforge3/envs/so101_voice/bin/python" -u \
  "$SCRIPT_DIR/voice_tasks_v3.py" \
  --port "$F_PORT" \
  --robot-python "$HOME/miniforge3/envs/so101/bin/python" \
  --helper "$HOME/lerobot/so101_home.py" \
  --dataset "$SO101_TASK1_DATASET" \
  --pose "$SO101_TASK1_POSE" \
  --dataset2 "$SO101_TASK2_DATASET" \
  --pose2 "$SO101_TASK2_POSE" \
  --dataset3 "$SO101_TASK3_DATASET" \
  --pose3 "$SO101_TASK3_POSE" \
  "$@"
