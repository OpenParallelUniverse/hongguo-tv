# Hongguo LAN service for OpenWrt

Target: OpenWrt 25.12 APK v3, x86_64 / Go amd64 v1 (J1900 compatible).
The single `luci-app-hongguo` package bundles a static Go server and modern
JavaScript LuCI view. It does not depend on Android, Wails, Docker or FFmpeg.

Changes to upstream core:

- Opt-in `--lan`, validated IPv4 binding, mandatory password-file HTTP Basic
  authentication, private-source/Host validation, and same-origin enforcement.
- Preserve the original loopback-only behavior when LAN mode is disabled.
- Adjustable completed-media cleanup threshold and whole-file download limit.
- Cancelable semaphore limits concurrent media preparations (default one).
- LAN browser requests default to `?platform=desktop` for mouse/keyboard input.

The service is managed by procd as the dedicated `hongguo` user. The UCI file
is root-readable only; the daemon receives the password through a private file
in `/var/run/hongguo`. Logs go to logread. It does not change firewall/network.

## Build

Prerequisites: Linux, Go 1.25+, apk-tools 3.x with `mkpkg`, and unshare or fakeroot.
From the repository root, using your own toolchain paths:

```sh
unshare -Ur env GO=/path/to/go APK=/path/to/apk OUT=/path/to/output ./openwrt/build.sh
```

Use an unprivileged user namespace or fakeroot for root-owned APK metadata.
The server is built with CGO disabled and GOAMD64=v1. No OpenWrt SDK is required
for this pure-Go executable; native ABI-dependent libraries are not bundled.
The build invokes `go mod` using this checkout's pinned go.mod/go.sum dependency.

Install with `apk add --allow-untrusted ./luci-app-hongguo-0.1.0-r1_x86_64.apk`.
The package is unsigned; the install flag is deliberately explicit.

## Checks

```sh
go test ./core/cmd/hongguotv -count=1 -timeout=180s
python3 openwrt/tests/smoke.py
node --check openwrt/files/www/luci-static/resources/view/hongguo/settings.js
```

LuCI DOM compatibility test uses the actual JS from an extracted official
OpenWrt rootfs, jsdom 26.1.0, Node and Python. It mocks only ubus JSON-RPC:

```sh
JSDOM_MODULE=/path/to/node_modules/jsdom python3 openwrt/tests/luci_dom.py /path/to/openwrt-rootfs
```

See TEST-REPORT.txt in the release archive for exact verification boundaries.
Keep the default RAM cache small on 1GB systems. The cache threshold and Go
GOMEMLIMIT are not hard total-memory limits. Real playback requires device
acceptance; no live-content or real-account validation is asserted.
