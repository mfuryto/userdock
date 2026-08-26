#!/bin/sh
set -eu

project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
version=${1:-$(sed -n 's/^version = "\([^"]*\)"/\1/p' "$project_dir/pyproject.toml")}
binary=${2:-$project_dir/dist/userdock-linux-x86_64}
output=${3:-$project_dir/dist/userdock_${version}_amd64.deb}

test -n "$version"
test -x "$binary"

package_root=$(mktemp -d)
trap 'rm -rf "$package_root"' EXIT HUP INT TERM

mkdir -p \
  "$package_root/DEBIAN" \
  "$package_root/usr/bin" \
  "$package_root/usr/share/doc/userdock" \
  "$package_root/usr/share/man/man1"

install -m 0755 "$binary" "$package_root/usr/bin/userdock"
install -m 0644 "$project_dir/README.md" "$package_root/usr/share/doc/userdock/README.md"
install -m 0644 "$project_dir/CHANGELOG.md" "$package_root/usr/share/doc/userdock/changelog"
gzip -n -9 "$package_root/usr/share/doc/userdock/changelog"
gzip -n -9 -c "$project_dir/docs/userdock.1" > "$package_root/usr/share/man/man1/userdock.1.gz"
chmod 0755 \
  "$package_root" \
  "$package_root/DEBIAN" \
  "$package_root/usr" \
  "$package_root/usr/bin" \
  "$package_root/usr/share" \
  "$package_root/usr/share/doc" \
  "$package_root/usr/share/doc/userdock" \
  "$package_root/usr/share/man" \
  "$package_root/usr/share/man/man1"
chmod 0644 "$package_root/usr/share/man/man1/userdock.1.gz"

installed_size=$(du -sk "$package_root/usr" | cut -f1)
cat > "$package_root/DEBIAN/control" <<EOF
Package: userdock
Version: $version
Section: admin
Priority: optional
Architecture: amd64
Depends: libc6 (>= 2.35)
Installed-Size: $installed_size
Maintainer: UserDock contributors
Homepage: https://github.com/mfuryto/userdock
Description: keyboard-first Linux user and group administration
 UserDock is a terminal interface and CLI for managing local Linux users,
 groups, login shells, supplementary memberships, and account access.
EOF

mkdir -p "$(dirname -- "$output")"
dpkg-deb --root-owner-group --build "$package_root" "$output"
dpkg-deb --info "$output"
dpkg-deb --contents "$output"
