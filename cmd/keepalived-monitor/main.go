package main

import (
	"context"
	"encoding/json"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"strconv"
	"syscall"
	"time"

	"github.com/brainscan1980/Keepalived-Monitor/internal/config"
	"github.com/brainscan1980/Keepalived-Monitor/internal/monitor"
	"github.com/brainscan1980/Keepalived-Monitor/internal/storage"
)

var version = "dev"
type healthResponse struct { Status string `json:"status"`; Version string `json:"version"` }

func main() {
	logger:=slog.New(slog.NewTextHandler(os.Stdout,nil));configPath:=getenv("CONFIG_FILE","/app/config/config.yml");cfg,err:=config.Load(configPath);if err!=nil{logger.Error("configuration failed","path",configPath,"error",err);os.Exit(1)}
	dbPath:=getenv("DB_FILE","/app/data/history.db");store,err:=storage.Open(dbPath);if err!=nil{logger.Error("database failed","path",dbPath,"error",err);os.Exit(1)};defer store.Close()
	logger.Info("configuration loaded","nodes",len(cfg.Nodes),"vrrp_groups",len(cfg.VRRP),"refresh_seconds",cfg.RefreshSeconds)
	ctx,cancelMonitor:=context.WithCancel(context.Background());defer cancelMonitor();mon:=monitor.New(cfg,logger,store);go mon.Run(ctx)

	mux:=http.NewServeMux();mux.HandleFunc("GET /healthz",func(w http.ResponseWriter,r *http.Request){writeJSON(w,http.StatusOK,healthResponse{Status:"ok",Version:version})})
	mux.HandleFunc("GET /api/v1/status",func(w http.ResponseWriter,r *http.Request){snapshot:=mon.Snapshot();writeJSON(w,http.StatusOK,map[string]any{"status":"ok","version":version,"refresh_seconds":cfg.RefreshSeconds,"nodes":snapshot.Nodes,"vrrp":snapshot.VRRP,"updated":snapshot.Updated})})
	mux.HandleFunc("GET /api/v1/events",func(w http.ResponseWriter,r *http.Request){limit:=50;if raw:=r.URL.Query().Get("limit");raw!=""{if n,e:=strconv.Atoi(raw);e==nil{limit=n}};events,e:=store.Events(limit);if e!=nil{logger.Error("read events failed","error",e);writeJSON(w,http.StatusInternalServerError,map[string]any{"ok":false,"error":"event history unavailable"});return};writeJSON(w,http.StatusOK,map[string]any{"ok":true,"events":events})})

	addr:=getenv("LISTEN_ADDR",":8080");srv:=&http.Server{Addr:addr,Handler:requestLogger(logger,mux),ReadHeaderTimeout:5*time.Second,ReadTimeout:15*time.Second,WriteTimeout:30*time.Second,IdleTimeout:60*time.Second};go func(){logger.Info("Keepalived Monitor Go starting","addr",addr,"version",version);if err:=srv.ListenAndServe();err!=nil&&err!=http.ErrServerClosed{logger.Error("HTTP server failed","error",err);os.Exit(1)}}()
	stop:=make(chan os.Signal,1);signal.Notify(stop,syscall.SIGINT,syscall.SIGTERM);<-stop;cancelMonitor();shutdownCtx,cancel:=context.WithTimeout(context.Background(),10*time.Second);defer cancel();if err:=srv.Shutdown(shutdownCtx);err!=nil{logger.Error("graceful shutdown failed","error",err)}
}
func getenv(name,fallback string)string{if value:=os.Getenv(name);value!=""{return value};return fallback}
func writeJSON(w http.ResponseWriter,status int,value any){w.Header().Set("Content-Type","application/json; charset=utf-8");w.WriteHeader(status);_=json.NewEncoder(w).Encode(value)}
func requestLogger(logger *slog.Logger,next http.Handler)http.Handler{return http.HandlerFunc(func(w http.ResponseWriter,r *http.Request){started:=time.Now();next.ServeHTTP(w,r);logger.Info("request","method",r.Method,"path",r.URL.Path,"duration",time.Since(started))})}
