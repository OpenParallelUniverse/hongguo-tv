package main

import (
	"net/http"
	"strings"
)

// LAN-only presentation keeps upstream HTML/CSS/JS independent of router UI.
func (s *server) withLANBrowserUI(next http.Handler) http.Handler {
	if s.lanAccess == nil {
		return next
	}
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if (r.URL.Path == "/" || r.URL.Path == "/index.html") && (r.Method == http.MethodGet || r.Method == http.MethodHead) {
			page, err := uiFiles.ReadFile("ui/index.html")
			if err != nil {
				http.Error(w, "Cannot load browser UI", http.StatusInternalServerError)
				return
			}
			// Keep the upstream HTML untouched so source updates can merge independently.
			content := strings.Replace(string(page), "</head>", `<link rel="stylesheet" href="/openwrt-mobile.css"><script defer src="/openwrt-mobile.js"></script></head>`, 1)
			w.Header().Set("Content-Type", "text/html; charset=utf-8")
			if r.Method != http.MethodHead {
				_, _ = w.Write([]byte(content))
			}
			return
		}
		next.ServeHTTP(w, r)
	})
}
