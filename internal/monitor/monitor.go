package monitor

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"os/exec"
	"strings"
	"sync"
	"time"

	"github.com/brainscan1980/Keepalived-Monitor/internal/config"
	"github.com/brainscan1980/Keepalived-Monitor/internal/storage"
)

const probeCommand = "printf 'KEEP='; systemctl is-active keepalived 2>/dev/null || true; printf 'UP='; uptime -p 2>/dev/null || true; printf 'ADDR='; ip -j addr show 2>/dev/null || true"

type NodeStatus struct {
	Name string `json:"name"`
	Host string `json:"host"`
	Online bool `json:"online"`
	Keepalived string `json:"keepalived"`
	Uptime string `json:"uptime"`
	Addresses []string `json:"addresses"`
	Error string `json:"error"`
}
type VRRPStatus struct { Name string `json:"name"`; VIP string `json:"vip"`; Nodes []string `json:"nodes"`; Master *string `json:"master"`; Healthy bool `json:"healthy"`; Roles map[string]string `json:"roles"` }
type Snapshot struct { Nodes map[string]NodeStatus `json:"nodes"`; VRRP []VRRPStatus `json:"vrrp"`; Updated time.Time `json:"updated"` }
type Monitor struct { cfg *config.Config; logger *slog.Logger; store *storage.Store; notifier IncidentNotifier; tracker *incidentTracker; mu sync.RWMutex; state Snapshot }

func New(cfg *config.Config, logger *slog.Logger, store *storage.Store, notifier IncidentNotifier) *Monitor { return &Monitor{cfg:cfg, logger:logger, store:store, notifier:notifier, tracker:newIncidentTracker(cfg.Notifications.NodeDown.FailuresBeforeAlert), state:Snapshot{Nodes:map[string]NodeStatus{}}} }
func (m *Monitor) Run(ctx context.Context) { m.Poll(ctx); t:=time.NewTicker(time.Duration(m.cfg.RefreshSeconds)*time.Second); defer t.Stop(); for { select { case <-ctx.Done(): return; case <-t.C: m.Poll(ctx) } } }
func (m *Monitor) Snapshot() Snapshot { m.mu.RLock(); defer m.mu.RUnlock(); return cloneSnapshot(m.state) }
func (m *Monitor) Poll(parent context.Context) { nodes:=map[string]NodeStatus{}; type result struct{name string; status NodeStatus}; ch:=make(chan result,len(m.cfg.Nodes)); var wg sync.WaitGroup; for _,n:=range m.cfg.Nodes { n:=n; wg.Add(1); go func(){defer wg.Done(); ch<-result{n.Name,m.pollNode(parent,n)}}() }; wg.Wait(); close(ch); for r:=range ch {nodes[r.name]=r.status}; vrrp:=make([]VRRPStatus,0,len(m.cfg.VRRP)); for _,v:=range m.cfg.VRRP {s:=evaluateVRRP(v,nodes); vrrp=append(vrrp,s); m.persistTransition(s)}; snap:=Snapshot{Nodes:nodes,VRRP:vrrp,Updated:time.Now()}; for _,i:=range m.tracker.Evaluate(snap){m.handleIncident(parent,i)}; m.mu.Lock(); m.state=snap; m.mu.Unlock() }
func (m *Monitor) persistTransition(v VRRPStatus) { if m.store==nil{return}; master:="NONE"; if v.Master!=nil{master=*v.Master}; changed,old,err:=m.store.RecordMaster(v.Name,master); if err!=nil{m.logger.Error("persist VRRP state failed","name",v.Name,"error",err);return}; if changed{m.logger.Info("VRRP master changed","name",v.Name,"old_master",old,"new_master",master)} }
func (m *Monitor) handleIncident(ctx context.Context,i Incident) { m.logger.Warn("cluster incident","type",i.Type,"scope",i.Scope,"message",i.Message); if m.store!=nil {if err:=m.store.RecordIncident(string(i.Type),i.Scope,i.Message,i.OldMaster,i.NewMaster);err!=nil{m.logger.Error("persist incident failed","error",err)}}; if !m.shouldNotify(i){return}; if m.notifier!=nil&&m.notifier.Enabled(){go func(){nctx,cancel:=context.WithTimeout(context.Background(),15*time.Second);defer cancel();if err:=m.notifier.Send(nctx,i);err!=nil{m.logger.Error("send incident notification failed","type",i.Type,"scope",i.Scope,"error",err)}}()} }
func (m *Monitor) shouldNotify(i Incident) bool { if i.Type==IncidentNodeDown&&!m.cfg.Notifications.NodeDown.Enabled{return false}; if i.Type==IncidentRecovery&&!m.cfg.Notifications.NodeDown.RecoveryMail{return false}; return true }
func (m *Monitor) pollNode(parent context.Context,n config.Node) NodeStatus { s:=NodeStatus{Name:n.Name,Host:n.Host,Keepalived:"unknown",Uptime:"-",Addresses:[]string{}}; ctx,cancel:=context.WithTimeout(parent,8*time.Second);defer cancel(); args:=[]string{"-o","BatchMode=yes","-o",fmt.Sprintf("ConnectTimeout=%d",m.cfg.SSH.ConnectTimeout)}; if m.cfg.SSH.KeyFile!=""{args=append(args,"-i",m.cfg.SSH.KeyFile)}; if m.cfg.SSH.KnownHostsFile!=""{args=append(args,"-o","UserKnownHostsFile="+m.cfg.SSH.KnownHostsFile,"-o","StrictHostKeyChecking=yes")}; args=append(args,n.User+"@"+n.Host,probeCommand); cmd:=exec.CommandContext(ctx,"ssh",args...); var out,er bytes.Buffer;cmd.Stdout=&out;cmd.Stderr=&er; if err:=cmd.Run();err!=nil{if ctx.Err()!=nil{s.Error=ctx.Err().Error()}else{s.Error=strings.TrimSpace(er.String());if s.Error==""{s.Error=err.Error()}};return s}; s.Online=true;parseProbe(out.String(),&s);return s }

func parseProbe(out string,s *NodeStatus) {
	for _,line:=range strings.Split(out,"\n") {
		switch {
		case strings.HasPrefix(line,"KEEP="):
			s.Keepalived=strings.TrimSpace(strings.TrimPrefix(line,"KEEP="))
		case strings.HasPrefix(line,"UP="):
			s.Uptime=strings.TrimSpace(strings.TrimPrefix(line,"UP="))
		case strings.HasPrefix(line,"ADDR="):
			var x []struct { AddrInfo []struct { Local string `json:"local"` } `json:"addr_info"` }
			if json.Unmarshal([]byte(strings.TrimPrefix(line,"ADDR=")),&x)==nil {
				for _,in:=range x { for _,a:=range in.AddrInfo { if a.Local!="" { s.Addresses=append(s.Addresses,a.Local) } } }
			}
		}
	}
}

func evaluateVRRP(v config.VRRP,n map[string]NodeStatus) VRRPStatus { o:=[]string{};for _,name:=range v.Nodes{if contains(n[name].Addresses,v.VIP){o=append(o,name)}};var master *string;if len(o)==1{x:=o[0];master=&x}else if len(o)>1{x:="MULTIPLE";master=&x};roles:=map[string]string{};for _,name:=range v.Nodes{node:=n[name];if !node.Online||node.Keepalived!="active"{roles[name]="FAULT"}else if master!=nil&&*master==name{roles[name]="MASTER"}else{roles[name]="BACKUP"}};return VRRPStatus{Name:v.Name,VIP:v.VIP,Nodes:append([]string(nil),v.Nodes...),Master:master,Healthy:len(o)==1,Roles:roles} }
func contains(v []string,w string) bool {for _,x:=range v{if x==w{return true}};return false}
func cloneSnapshot(in Snapshot) Snapshot {out:=Snapshot{Nodes:map[string]NodeStatus{},VRRP:make([]VRRPStatus,len(in.VRRP)),Updated:in.Updated};for k,n:=range in.Nodes{n.Addresses=append([]string(nil),n.Addresses...);out.Nodes[k]=n};for i,v:=range in.VRRP{v.Nodes=append([]string(nil),v.Nodes...);v.Roles=cloneRoles(v.Roles);if v.Master!=nil{x:=*v.Master;v.Master=&x};out.VRRP[i]=v};return out}
func cloneRoles(in map[string]string) map[string]string {out:=map[string]string{};for k,v:=range in{out[k]=v};return out}
