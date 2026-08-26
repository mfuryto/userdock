#!/bin/sh
set -eu

project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$project_dir"

.venv/bin/pyinstaller \
  --clean \
  --onefile \
  --name userdock \
  --collect-all textual \
  src/userdock/__main__.py

