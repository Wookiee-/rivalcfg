#!/usr/bin/env bash
# Build the complete Linux GUI release from the current checkout.
#
# The output is kept together in dist/packages/:
#   source archive, Fedora RPM, Arch package, and Debian package.
#
# Run from any directory inside the checkout:
#   ./scripts/build-packages.sh
#   ./scripts/build-packages.sh --deb
#   ./scripts/build-packages.sh --publish
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$SCRIPT_DIR/.." && pwd)"
DIST_DIR="${DIST_DIR:-$REPO/dist/packages}"
WORK_DIR="${WORK_DIR:-$REPO/dist/.package-work}"

usage() {
  cat <<'EOF'
Usage: scripts/build-packages.sh [TARGET ...]

Build the complete release by default. Targets may be selected with:
  --rpm       Fedora/RHEL RPM (requires rpmbuild)
  --arch      Arch Linux package (requires makepkg)
  --deb       Debian/Ubuntu package (requires dpkg-deb)
  --publish   Upload the complete bundle to a GitHub release (requires gh)
  --help      Show this help

The source archive is always built and included in dist/packages/.
Set DIST_DIR or WORK_DIR to override the output and temporary directories.
EOF
}

want_rpm=0
want_arch=0
want_deb=0
publish=0
selected=0
for arg in "$@"; do
  case "$arg" in
    --rpm) want_rpm=1; selected=1 ;;
    --arch) want_arch=1; selected=1 ;;
    --deb) want_deb=1; selected=1 ;;
    --publish) publish=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $arg" >&2; usage >&2; exit 2 ;;
  esac
done
if [[ "$selected" == 0 ]]; then
  want_rpm=1
  want_arch=1
  want_deb=1
fi

VERSION="$(sed -n 's/^version = "\([^"]*\)"/\1/p' "$REPO/pyproject.toml" | head -n 1)"
if [[ -z "$VERSION" ]]; then
  echo "Could not read project version from pyproject.toml" >&2
  exit 1
fi

RPM_VERSION="$(sed -n 's/^Version:[[:space:]]*\([^[:space:]]*\).*/\1/p' "$REPO/packaging/rpm/rivalcfg-gui.spec" | head -n 1)"
ARCH_VERSION="$(sed -n 's/^pkgver=//p' "$REPO/packaging/arch/PKGBUILD" | head -n 1)"
if [[ "$RPM_VERSION" != "$VERSION" || "$ARCH_VERSION" != "$VERSION" ]]; then
  echo "Package metadata version mismatch:" >&2
  echo "  pyproject.toml: $VERSION" >&2
  echo "  packaging/rpm/rivalcfg-gui.spec: $RPM_VERSION" >&2
  echo "  packaging/arch/PKGBUILD: $ARCH_VERSION" >&2
  echo "Update all release versions before building." >&2
  exit 1
fi

SOURCE_NAME="rivalcfg-gui-${VERSION}.tar.gz"
SOURCE_PATH="$DIST_DIR/$SOURCE_NAME"
mkdir -p "$DIST_DIR" "$WORK_DIR"

# Build from the checkout, so staged and unstaged project changes are included.
# User-local screenshots and previous build output are not release inputs.
echo "[1/4] Creating $SOURCE_NAME"
tar -czf "$SOURCE_PATH" \
  --exclude='./.git' \
  --exclude='./.git/*' \
  --exclude='./.agents' \
  --exclude='./.aws' \
  --exclude='./.codex' \
  --exclude='./.pytest_cache' \
  --exclude='./dist' \
  --exclude='./dist/*' \
  --exclude='./rival.jpg' \
  --transform="s,^\\./,rivalcfg-gui-${VERSION}/," \
  -C "$REPO" .

if [[ "$want_rpm" == 1 ]]; then
  command -v rpmbuild >/dev/null || { echo "RPM build requested but rpmbuild is unavailable" >&2; exit 1; }
  echo "[2/4] Building Fedora RPM"
  rpm_root="$WORK_DIR/rpm"
  rm -rf "$rpm_root"
  mkdir -p "$rpm_root"/{BUILD,BUILDROOT,RPMS,SOURCES,SPECS,SRPMS}
  cp "$SOURCE_PATH" "$rpm_root/SOURCES/"
  cp "$REPO/packaging/rpm/rivalcfg-gui.spec" "$rpm_root/SPECS/"
  rpmbuild -ba "$rpm_root/SPECS/rivalcfg-gui.spec" \
    --define "_topdir $rpm_root" \
    --define "_rpmdir $DIST_DIR" \
    --define "_srcrpmdir $DIST_DIR"
  find "$rpm_root/RPMS" "$rpm_root/SRPMS" -type f -name '*.rpm' -exec cp {} "$DIST_DIR/" \;
fi

if [[ "$want_arch" == 1 ]]; then
  command -v makepkg >/dev/null || { echo "Arch build requested but makepkg is unavailable" >&2; exit 1; }
  echo "[3/4] Building Arch package"
  arch_root="$WORK_DIR/arch"
  rm -rf "$arch_root"
  mkdir -p "$arch_root"
  cp "$SOURCE_PATH" "$arch_root/"
  cp "$REPO/packaging/arch/PKGBUILD" "$arch_root/"
  (cd "$arch_root" && makepkg --clean --nodeps --noconfirm)
  find "$arch_root" -maxdepth 1 -type f -name 'rivalcfg-gui-*.pkg.tar.*' -exec cp {} "$DIST_DIR/" \;
fi

if [[ "$want_deb" == 1 ]]; then
  command -v dpkg-deb >/dev/null || { echo "Debian build requested but dpkg-deb is unavailable" >&2; exit 1; }
  echo "[4/4] Building Debian package"
  OUT_DIR="$DIST_DIR" VER="$VERSION" bash "$REPO/packaging/deb/build-deb.sh"
fi

echo
echo "Release files in $DIST_DIR:"
find "$DIST_DIR" -maxdepth 1 -type f -printf '  %f\n' | sort

if [[ "$publish" == 1 ]]; then
  command -v gh >/dev/null || { echo "Publishing requested but gh is unavailable" >&2; exit 1; }
  gh auth status >/dev/null 2>&1 || {
    echo "Publishing requested but gh is not authenticated. Run: gh auth refresh -h github.com" >&2
    exit 1
  }

  mapfile -t release_files < <(find "$DIST_DIR" -maxdepth 1 -type f \( \
    -name 'rivalcfg-gui-*.tar.gz' -o -name 'rivalcfg-gui-*.rpm' -o \
    -name 'rivalcfg-gui-*.pkg.tar.*' -o -name 'rivalcfg-gui_*.deb' \
  \) -print | sort)
  if [[ "${#release_files[@]}" -lt 4 ]]; then
    echo "Publishing requires the source archive and all three distro packages." >&2
    exit 1
  fi

  tag="v${VERSION}"
  title="rivalcfg GUI ${VERSION}"
  echo "Publishing GitHub release $tag"
  if gh release view "$tag" >/dev/null 2>&1; then
    gh release upload "$tag" --clobber "${release_files[@]}"
  else
    gh release create "$tag" "${release_files[@]}" \
      --target "$(git rev-parse HEAD)" \
      --title "$title" \
      --generate-notes
  fi
fi
