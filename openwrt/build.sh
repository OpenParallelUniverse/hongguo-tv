#!/bin/sh
# Run as root or in a user namespace (unshare -Ur) for root-owned APK paths.
set -eu
[ "$(id -u)" = 0 ] || { echo "Run this build under unshare -Ur or sudo for root-owned APK paths" >&2; exit 1; }
cd "$(dirname "$0")/.."
: "${GO:=go}"
: "${APK:=apk}"
: "${OUT:=../output}"
: "${HONGGUO_PKG_VERSION:=0.1.0-r1}"
: "${HONGGUO_CORE_VERSION:=0.1.0-openwrt}"
case "$HONGGUO_PKG_VERSION" in ''|*[!0-9.r-]*) echo 'Invalid APK version' >&2; exit 1;; esac
case "$HONGGUO_CORE_VERSION" in ''|*[!A-Za-z0-9._+-]*) echo 'Invalid core version' >&2; exit 1;; esac
stage="$(mktemp -d)"
trap 'rm -rf "$stage"' EXIT HUP INT TERM
mkdir -p "$OUT" openwrt/files/usr/bin
CGO_ENABLED=0 GOOS=linux GOARCH=amd64 GOAMD64=v1 "$GO" build \
	-trimpath -ldflags="-s -w -X main.version=$HONGGUO_CORE_VERSION" \
	-o openwrt/files/usr/bin/hongguo-server ./core/cmd/hongguotv
cp -R openwrt/files/. "$stage/"
chmod 755 "$stage"
chmod 755 "$stage/usr/bin/hongguo-server" "$stage/etc/init.d/hongguo"
chmod 600 "$stage/etc/config/hongguo"
chown -R 0:0 "$stage"
printf '\nOpenWrt package version: %s\nCore version: %s\n' "$HONGGUO_PKG_VERSION" "$HONGGUO_CORE_VERSION" >> "$stage/usr/share/doc/hongguo/NOTICE.txt"
"$APK" mkpkg \
	--info 'name:luci-app-hongguo' \
	--info "version:$HONGGUO_PKG_VERSION" \
	--info 'arch:x86_64' \
	--info 'description:Hongguo LAN Web service and LuCI settings for OpenWrt' \
	--info 'license:LicenseRef-Upstream' \
	--info 'origin:luci-app-hongguo' \
	--info 'url:https://github.com/aston314/hongguo-tv' \
	--info 'depends:luci-base rpcd rpcd-mod-file ca-bundle procd uci' \
	--script post-install:openwrt/scripts/post-install \
	--script post-upgrade:openwrt/scripts/post-install \
	--script pre-upgrade:openwrt/scripts/pre-upgrade \
	--script pre-deinstall:openwrt/scripts/pre-deinstall \
	--files "$stage" \
	--output "$OUT/luci-app-hongguo-${HONGGUO_PKG_VERSION}_x86_64.apk"
