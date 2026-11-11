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

Prerequisites: Linux, Go 1.25+, apk-tools 3.x with `mkpkg`, and unshare or sudo.
From the repository root, using your own toolchain paths:

```sh
unshare -Ur env GO=/path/to/go APK=/path/to/apk OUT=/path/to/output ./openwrt/build.sh
```

Use an unprivileged user namespace or real root for root-owned APK metadata.
A statically linked apk does not honor fakeroot ownership interception.
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

## Automatic upstream releases

The repository has an `OpenWrt auto release` GitHub Actions workflow. The
identical workflow file must exist on default branch `main` and integration
branch `openwrt`: scheduled events run only from the default branch. This
scheduler is the only OpenWrt file added to `main`; integration code stays on
`openwrt`. Keep the workflow copies identical when editing the scheduler.

The workflow checks the latest stable release in `aston314/hongguo-tv-releases`
at minute 17 of each hour, resolves the matching `vMAJOR.MINOR.PATCH` source tag
in `aston314/hongguo-tv`, and integrates its source changes into the current `openwrt`
branch with a three-way patch. The diff excludes `.github/workflows/**`, keeping
this fork's workflows intact and avoiding a workflow-write permission dependency
for the runtime `GITHUB_TOKEN`. The upstream commit is recorded as provenance;
upstream workflow commits are not added as Git parents. It never force-pushes or discards local changes. GitHub schedules may be
delayed; public-repository schedules can be disabled after 60 days of inactivity.
Fork workflows may need one-time enabling under the repository's Actions tab.

After a clean merge it runs release-tool regression tests, the full Go core
suite, the real standalone HTTP smoke test, JS/shell checks, APKv3 verification,
and the configuration page against matching LuCI JavaScript in a jsdom DOM
(ubus is mocked). The APK packer and LuCI test assets are checksum-pinned.
Building uses `sudo` only inside the GitHub-hosted runner to ensure root-owned
package metadata. It does not touch a router or need a router SSH credential.

Only after validation does it push the integration commit and release tag
atomically. It creates a draft release, uploads the APK, corresponding source
archive, installation notes, BUILD-INFO.json and SHA256SUMS, downloads and checks
the uploaded assets, then publishes the release. Merge/test failures stop
publication; upload failures leave a draft that can be retried. Existing
published releases are immutable. A missing release causes the initial build
without requiring a new upstream version. An already complete release is
skipped on the next hourly check.

Package versions combine the upstream version and the positive integration
revision in `openwrt/RELEASE`, e.g. `0.2.168-r2`; tags are
`openwrt-v0.2.168-r2`, which do not trigger upstream Android `v*` tag releases.
Increment `openwrt/RELEASE` when changing the integration after publishing that
upstream version. A new upstream version can reuse the same revision. The
package builder accepts `HONGGUO_PKG_VERSION` and `HONGGUO_CORE_VERSION`; the
workflow sets both from the validated plan. Its source provenance is recorded
in `openwrt/UPSTREAM.json` and release assets. Downgrades and moved upstream tags
require manual review rather than silently relabeling code.

Manual retry: Actions → OpenWrt auto release → Run workflow, using the default
branch. Leave `upstream_tag` empty for the latest stable version, or specify a
published source tag. No PAT or additional repository secret is required:
`GITHUB_TOKEN` is used only for GitHub metadata and final publication steps.
Repository/organization policy must permit Actions and contents writes.
CI success does not establish real playback or full router lifecycle acceptance.
Published packages are downloadable in Releases; routers are not auto-upgraded.

## Mobile browser layout

The authenticated LAN HTML wrapper adds `openwrt-mobile.css` and
`openwrt-mobile.js`; the upstream index.html, app.css and app.js stay untouched.
At widths up to 960px the page uses a touch-friendly navigation drawer,
responsive poster grids and dialogs, scrollable playback controls, safe-area
padding, inline video and visual-viewport sizing for the on-screen keyboard.
At wider widths the original desktop layout remains active. Android/Wails
hosts do not load these LAN-only presentation files.

CI tests the real LAN server in Chromium at 320, 390, 768, 844/932 landscape and
1280 pixel widths with synthetic APIs and a generated VP8/WebM clip. It checks
navigation, dialogs, account/settings, player bounds, orientation changes and
returning to desktop, and retains layout screenshots for seven days. No real
account or upstream video is used. These presentation assets remain independent
of upstream UI files; incompatible future DOM changes fail the browser test and
stop publication instead of silently shipping a broken mobile page.
