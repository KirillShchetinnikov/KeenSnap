#!/bin/sh

REPO_NAME="keensnap"
REPO_FILE="/opt/etc/opkg/${REPO_NAME}.conf"
FEED_URL="${FEED_URL:-https://KirillShchetinnikov.github.io/KeenSnap}"
found=0
opkg_repos=""

while read -r _ ARCH _; do
  case "$ARCH" in
    aarch64-3.10|armv7-3.2|mips-3.4|mipsel-3.4)
      echo "Architecture defined: $ARCH"
      found=1
      opkg_repos="${opkg_repos}src/gz ${REPO_NAME}_${ARCH} ${FEED_URL}/${ARCH}
"
      ;;
  esac
done <<EOF
$(/opt/bin/opkg print-architecture)
EOF

if [ "$found" -eq 0 ]; then
  echo "No supported architectures found" >&2
  exit 1
fi

opkg install wget-ssl >/dev/null 2>&1 || true
mkdir -p /opt/etc/opkg
printf "%s" "$opkg_repos" > "$REPO_FILE"
opkg update

exit 0
