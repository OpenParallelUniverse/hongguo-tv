package main

import (
	"context"
	"crypto/sha256"
	"errors"
	"io/fs"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func TestLANConfigurationFailsClosed(t *testing.T) {
	oldHost := coreListenHost
	t.Cleanup(func() { coreListenHost = oldHost })
	file := filepath.Join(t.TempDir(), "password")
	if err := os.WriteFile(file, []byte("test-password-123"), 0600); err != nil {
		t.Fatal(err)
	}
	for _, tc := range []struct {
		host string
		lan  bool
		file string
	}{
		{"0.0.0.0", false, file}, {"8.8.8.8", true, file}, {"::", true, file},
		{"192.168.1.1", true, ""}, {"evil.example", true, file},
	} {
		if _, err := configureLAN(tc.host, tc.lan, tc.file); err == nil {
			t.Fatalf("accepted unsafe config: %+v", tc)
		}
	}
	access, err := configureLAN("0.0.0.0", true, file)
	if err != nil || access == nil || coreListenHost != "0.0.0.0" {
		t.Fatalf("LAN config: %v", err)
	}
	if err := os.WriteFile(file, []byte("short"), 0600); err != nil {
		t.Fatal(err)
	}
	if _, err := configureLAN("0.0.0.0", true, file); err == nil {
		t.Fatal("accepted weak password")
	}
}

func TestLANAuthenticationAndOriginCoverUIAPIAndMedia(t *testing.T) {
	s := &server{lanAccess: &lanAccess{passwordHash: sha256.Sum256([]byte("test-password-123"))}}
	var reached int
	h := s.withLANAccess(s.withCORS(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { reached++; w.WriteHeader(204) })))
	for _, path := range []string{"/?platform=desktop", "/api/v1/search?q=test", "/api/v1/account", "/api/v1/library", "/minireel-proxy/media/012345678901234567890123.mp4"} {
		for _, tc := range []struct {
			name, remote, host, origin, password, site string
			want                                       int
		}{
			{"allowed", "192.168.1.2:5000", "192.168.1.1:8797", "http://192.168.1.1:8797", "test-password-123", "same-origin", 204},
			{"no login", "192.168.1.2:5000", "192.168.1.1:8797", "", "", "", 401},
			{"wrong password", "192.168.1.2:5000", "192.168.1.1:8797", "", "wrong", "", 401},
			{"public source", "8.8.8.8:5000", "192.168.1.1:8797", "", "test-password-123", "", 403},
			{"rebound host", "192.168.1.2:5000", "evil.example:8797", "", "test-password-123", "", 403},
			{"cross origin", "192.168.1.2:5000", "192.168.1.1:8797", "http://192.168.1.9:8797", "test-password-123", "", 403},
			{"cross site", "192.168.1.2:5000", "192.168.1.1:8797", "", "test-password-123", "cross-site", 403},
		} {
			r := httptest.NewRequest("GET", "http://"+tc.host+path, nil)
			r.RemoteAddr = tc.remote
			r.Header.Set("Origin", tc.origin)
			r.Header.Set("Sec-Fetch-Site", tc.site)
			r.Header.Set("Range", "bytes=0-1023")
			if tc.password != "" {
				r.SetBasicAuth("hongguo", tc.password)
			}
			w := httptest.NewRecorder()
			before := reached
			h.ServeHTTP(w, r)
			if w.Code != tc.want {
				t.Fatalf("%s %s: got %d want %d", path, tc.name, w.Code, tc.want)
			}
			if tc.want != 204 && reached != before {
				t.Fatal("rejected request reached application")
			}
			if tc.want == 401 && w.Header().Get("WWW-Authenticate") == "" {
				t.Fatal("missing browser login challenge")
			}
		}
	}
}

func TestLANRealEmbeddedPageAndMediaRange(t *testing.T) {
	root, err := fs.Sub(uiFiles, "ui")
	if err != nil {
		t.Fatal(err)
	}
	s := &server{lanAccess: &lanAccess{passwordHash: sha256.Sum256([]byte("test-password-123"))}}
	mux := http.NewServeMux()
	mux.Handle("/", serveUI(root))
	mux.HandleFunc("/fixture.mp4", func(w http.ResponseWriter, r *http.Request) {
		http.ServeContent(w, r, "fixture.mp4", s.startedAt, strings.NewReader("0123456789"))
	})
	h := s.withLANAccess(s.withLANBrowserUI(s.withCORS(mux)))
	for _, tc := range []struct {
		path, byteRange string
		want            int
		body            string
	}{
		{"/", "", 302, ""}, {"/?platform=desktop", "", 200, "<html"}, {"/fixture.mp4", "bytes=2-5", 206, "2345"},
	} {
		r := httptest.NewRequest("GET", "http://192.168.1.1:8797"+tc.path, nil)
		r.RemoteAddr = "192.168.1.2:5000"
		r.SetBasicAuth("hongguo", "test-password-123")
		r.Header.Set("Range", tc.byteRange)
		w := httptest.NewRecorder()
		h.ServeHTTP(w, r)
		if w.Code != tc.want || tc.body != "" && !strings.Contains(w.Body.String(), tc.body) {
			t.Fatalf("%s: status=%d body=%.100s", tc.path, w.Code, w.Body.String())
		}
	}
}

func TestLANPreparationConcurrencyAndQueuedCancellation(t *testing.T) {
	isolatedMediaJobs(t)
	oldSlots := mediaPrepareSlots
	mediaPrepareSlots = make(chan struct{}, 1)
	t.Cleanup(func() { mediaPrepareSlots = oldSlots })
	entered := make(chan string, 4)
	release := make(chan struct{})
	prepare := func(ctx context.Context, job *miniReelMediaJob, token, series, vid, quality string, fallback bool) {
		entered <- vid
		select {
		case <-release:
		case <-ctx.Done():
		}
		job.Err = errors.New("test preparation complete")
	}
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	out := make(chan error, 3)
	go func() { _, err := resolveMiniReelMediaWith(ctx, "123", "111", "", true, prepare); out <- err }()
	select {
	case <-entered:
	case <-time.After(2 * time.Second):
		t.Fatal("first preparation did not enter")
	}
	queueCtx, queueCancel := context.WithCancel(ctx)
	go func() { _, err := resolveMiniReelMediaWith(queueCtx, "123", "222", "", true, prepare); out <- err }()
	waitMediaCondition(t, func() bool { miniReelState.Lock(); defer miniReelState.Unlock(); return len(miniReelState.jobs) == 2 })
	select {
	case <-entered:
		t.Fatal("second preparation bypassed concurrency limit")
	default:
	}
	queueCancel()
	select {
	case <-out:
	case <-time.After(2 * time.Second):
		t.Fatal("queued caller did not cancel")
	}
	close(release)
	select {
	case <-out:
	case <-time.After(2 * time.Second):
		t.Fatal("first preparation did not finish")
	}
	// Ensure the queued worker has observed cancellation before restoring globals.
	miniReelState.Lock()
	jobs := make([]*miniReelMediaJob, 0, len(miniReelState.jobs))
	for _, job := range miniReelState.jobs {
		jobs = append(jobs, job)
	}
	miniReelState.Unlock()
	for _, job := range jobs {
		awaitMediaSignal(t, job.Ready)
	}
	select {
	case id := <-entered:
		t.Fatalf("cancelled job entered expensive preparation: %s", id)
	default:
	}
}

func TestLANWholeFileDownloadLimitRemovesPartialFile(t *testing.T) {
	oldLimit := miniReelMaxBytes
	miniReelMaxBytes = 16
	t.Cleanup(func() { miniReelMaxBytes = oldLimit })
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { w.Write([]byte(strings.Repeat("x", 32))) }))
	defer upstream.Close()
	path := filepath.Join(t.TempDir(), "video.mp4")
	if err := downloadMiniReelMedia(context.Background(), upstream.URL, path); err == nil {
		t.Fatal("oversize download accepted")
	}
	if _, err := os.Stat(path); !os.IsNotExist(err) {
		t.Fatalf("partial download retained: %v", err)
	}
}

func TestLANMobileAssetsDoNotChangeEmbeddedUpstreamHTML(t *testing.T) {
	root, err := fs.Sub(uiFiles, "ui")
	if err != nil {
		t.Fatal(err)
	}
	s := &server{lanAccess: &lanAccess{passwordHash: sha256.Sum256([]byte("test-password-123"))}}
	for _, lan := range []bool{false, true} {
		handler := serveUI(root)
		if lan {
			handler = s.withLANAccess(s.withLANBrowserUI(handler))
		}
		r := httptest.NewRequest("GET", "http://127.0.0.1:8797/?platform=desktop", nil)
		r.RemoteAddr = "127.0.0.1:1234"
		r.SetBasicAuth("hongguo", "test-password-123")
		w := httptest.NewRecorder()
		handler.ServeHTTP(w, r)
		if w.Code != 200 {
			t.Fatalf("UI status: %d", w.Code)
		}
		for _, asset := range []string{"/openwrt-mobile.css", "/openwrt-mobile.js"} {
			if strings.Contains(w.Body.String(), asset) != lan {
				t.Fatalf("LAN-only asset %s (LAN=%v)", asset, lan)
			}
		}
	}
}
