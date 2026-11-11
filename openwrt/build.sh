#!/bin/sh
# Run in an unprivileged user namespace (unshare -Ur) or fakeroot so APK paths are root-owned.
set -eu
[ "$(id -u)" = 0 ] || { echo "Run this build under unshare -Ur or fakeroot for root-owned APK paths" >&2; exit 1; }
cd "$(dirname "$0")/.."
: "${GO:=go}"
: "${APK:=apk}"
: "${OUT:=../output}"
mkdir -p "$OUT" openwrt/files/usr/bin
CGO_ENABLED=0 GOOS=linux GOARCH=amd64 GOAMD64=v1 "$GO" build \
	-trimpath -ldflags='-s -w -X main.version=0.1.0-openwrt' \
	-o openwrt/files/usr/bin/hongguo-server ./core/cmd/hongguotv
chmod 755 openwrt/files/usr/bin/hongguo-server openwrt/files/etc/init.d/hongguo openwrt/scripts/*
chmod 600 openwrt/files/etc/config/hongguo
"$APK" mkpkg \
	--info 'name:luci-app-hongguo' \
	--info 'version:0.1.0-r1' \
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
	--files openwrt/files \
	--output "$OUT/luci-app-hongguo-0.1.0-r1_x86_64.apk"
