package main

import (
	"crypto/sha256"
	"crypto/subtle"
	"errors"
	"net"
	"net/http"
	"net/url"
	"os"
	"strings"
)

var coreListenHost = "127.0.0.1"

type lanAccess struct{ passwordHash [32]byte }

func configureLAN(listen string, enabled bool, passwordFile string) (*lanAccess, error) {
	ip := net.ParseIP(listen)
	if ip == nil || ip.To4() == nil || !(ip.IsPrivate() || ip.IsLoopback() || ip.IsUnspecified()) {
		return nil, errors.New("listen must be a private, loopback, or unspecified IPv4 address")
	}
	if !enabled {
		if !ip.IsLoopback() {
			return nil, errors.New("non-loopback listen requires --lan and --password-file")
		}
		coreListenHost = listen
		return nil, nil
	}
	password, err := os.ReadFile(passwordFile)
	if err != nil {
		return nil, errors.New("cannot read LAN password file")
	}
	password = []byte(strings.TrimRight(string(password), "\r\n"))
	if len(password) < 12 || len(password) > 128 || strings.ContainsAny(string(password), "\r\n") {
		return nil, errors.New("LAN password must contain 12..128 bytes and no newlines")
	}
	coreListenHost = listen
	return &lanAccess{passwordHash: sha256.Sum256(password)}, nil
}

// Never trust X-Forwarded-For. A LAN listener is not an Internet-facing proxy.
func (a *lanAccess) allowed(r *http.Request) bool {
	host, _, err := net.SplitHostPort(r.RemoteAddr)
	if err != nil {
		return false
	}
	ip := net.ParseIP(host)
	if ip == nil || ip.To4() == nil || !(ip.IsPrivate() || ip.IsLoopback()) {
		return false
	}
	u, err := url.Parse("http://" + r.Host)
	if err != nil || u.User != nil {
		return false
	}
	ip = net.ParseIP(u.Hostname())
	if u.Hostname() != "localhost" && (ip == nil || ip.To4() == nil || !(ip.IsPrivate() || ip.IsLoopback())) {
		return false
	}
	if r.Header.Get("Sec-Fetch-Site") == "cross-site" {
		return false
	}
	for _, name := range []string{"Origin", "Referer"} {
		if value := r.Header.Get(name); value != "" {
			origin, err := url.Parse(value)
			if err != nil || origin.Scheme != "http" || origin.Host != r.Host || origin.User != nil {
				return false
			}
		}
	}
	return true
}

func (s *server) privateRequestAllowed(r *http.Request) bool {
	if s.lanAccess != nil {
		return s.lanAccess.allowed(r)
	}
	return privateLocalRequest(r)
}

func (s *server) withLANAccess(next http.Handler) http.Handler {
	if s.lanAccess == nil {
		return next
	}
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("X-Content-Type-Options", "nosniff")
		w.Header().Set("Referrer-Policy", "same-origin")
		w.Header().Set("X-Frame-Options", "SAMEORIGIN")
		w.Header().Set("Cache-Control", "no-store")
		if !s.lanAccess.allowed(r) {
			http.Error(w, "仅允许局域网同源访问，请通过路由器 IP 打开", http.StatusForbidden)
			return
		}
		user, password, ok := r.BasicAuth()
		hash := sha256.Sum256([]byte(password))
		if !ok || user != "hongguo" || subtle.ConstantTimeCompare(hash[:], s.lanAccess.passwordHash[:]) != 1 {
			w.Header().Set("WWW-Authenticate", `Basic realm="Hongguo LAN", charset="UTF-8"`)
			http.Error(w, "请输入 LuCI 中设置的观看密码，用户名 hongguo", http.StatusUnauthorized)
			return
		}
		// Browser mode supports ordinary mouse/keyboard input by default.
		if r.URL.Path == "/" && r.Method == http.MethodGet && r.URL.Query().Get("platform") == "" {
			q := r.URL.Query()
			q.Set("platform", "desktop")
			http.Redirect(w, r, "/?"+q.Encode(), http.StatusFound)
			return
		}
		next.ServeHTTP(w, r)
	})
}
