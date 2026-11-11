#!/bin/sh
# Start the Firestore emulator, importing prior data ONLY if an export exists.
# A bare `--import` against an empty/first-run data dir makes firebase-tools
# error out ("Could not find import directory"), so we gate it on the export
# metadata file. Either way we export on graceful exit so data persists.
set -e
PROJECT="${GCLOUD_PROJECT:-aic-local}"
DATA_DIR=/firebase/data
mkdir -p "$DATA_DIR"

if [ -f "$DATA_DIR/firebase-export-metadata.json" ]; then
  echo "[start-emulator] existing export found -> importing from $DATA_DIR"
  exec firebase emulators:start --project "$PROJECT" --only firestore \
    --import="$DATA_DIR" --export-on-exit="$DATA_DIR"
else
  echo "[start-emulator] no prior export -> starting fresh (will export on exit)"
  exec firebase emulators:start --project "$PROJECT" --only firestore \
    --export-on-exit="$DATA_DIR"
fi
