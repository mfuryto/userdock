#!/bin/sh
set -eu

project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$project_dir"

.venv/bin/pyinstaller \
  --clean \
  --onefile \
  --name userdock \
  --paths "$project_dir/../sambactl" \
  --hidden-import sambactl.backup \
  --hidden-import sambactl.models \
  --hidden-import sambactl.paths \
  --hidden-import sambactl.samba.config \
  --hidden-import sambactl.samba.service \
  --hidden-import sambactl.samba.shares \
  --hidden-import sambactl.samba.users \
  --hidden-import sambactl.samba.validation \
  --hidden-import sambactl.system.commands \
  --hidden-import sambactl.system.filesystem \
  --hidden-import sambactl.system.identity \
  --hidden-import sambactl.transaction \
  --collect-all textual \
  src/userdock/__main__.py
