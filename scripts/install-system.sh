#!/bin/sh
set -eu

if [ "$(id -u)" -ne 0 ]; then
  echo "Run this installer with sudo." >&2
  exit 1
fi

binary=${1:-dist/userdock}
test -f "$binary"

install -o root -g root -m 0750 "$binary" /usr/local/bin/userdock
echo "Installed /usr/local/bin/userdock"
echo "Run it with: sudo userdock"
