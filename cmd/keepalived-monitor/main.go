package main

import (
	"context"
	"encoding/json"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/brainscan1980/Keepalived-Monitor/internal/config"
)

var version = "dev"

type healthResponse struct {
	Status  string `json:"status"`
	Version string `json:"version"`
}

func main() {
	logger := slog.New(slog.NewTextHandler(os.Stdout, nil))

	configPath := getenv("CONFIG_FILE", "/app/config/config.yml")
	cfg, err := config.Load(configPath)
	if err != nil {
		logger.Error("configuration failed", "path", configPath, "error", err)
		os.Exit(1)
	}
	logger.Info("configuration loaded", "nodes", len(cfg.Nodes), "vrrp_groups", len(cfg.VRRP), "refresh_seconds", cfg.RefreshSeconds)

	mux := http.NewServeMux()
	mux.HandleFunc("GET /healthz", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, http.StatusOK, healthResponse{Status: "ok", Version: version})
	})
	mux.HandleFunc("GET /api/v1/status", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, http.StatusOK, map[string]any{
			"status":          "starting",
			"version":         version,
			"refresh_seconds": cfg.RefreshSeconds,
			"nodes":           cfg.Nodes,
			"vrrp":            cfg.VRRP,
		})
	})

	addr := getenv("LISTEN_ADDR", ":8080")
	srv := &http.Server{
		Addr:              addr,
		Handler:           requestLogger(logger, mux),
		ReadHeaderTimeout: 5 * time.Second,
		ReadTimeout:       15 * time.Second,
		WriteTimeout:      30 * time.Second,
		IdleTimeout:       60 * time.Second,
	}

	go func() {
		logger.Info("Keepalived Monitor Go starting", "addr", addr, "version", version)
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			logger.Error("HTTP server failed", "error", err)
			os.Exit(1)
		}
	}()

	stop := make(chan os.Signal, 1)
	signal.Notify(stop, syscall.SIGINT, syscall.SIGTERM)
	<-stop

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	if err := srv.Shutdown(ctx); err != nil {
		logger.Error("graceful shutdown failed", "error", err)
	}
}

func getenv(name, fallback string) string {
	if value := os.Getenv(name); value != "" {
		return value
	}
	return fallback
}

func writeJSON(w http.ResponseWriter, status int, value any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(value)
}

func requestLogger(logger *slog.Logger, next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		started := time.Now()
		next.ServeHTTP(w, r)
		logger.Info("request", "method", r.Method, "path", r.URL.Path, "duration", time.Since(started))
	})
}
