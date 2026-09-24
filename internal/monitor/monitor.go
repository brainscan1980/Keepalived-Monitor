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
)

const probeCommand = "printf 'KEEP='; systemctl is-active keepalived 2>/dev/null || true; printf 'UP='; uptime -p 2>/dev/null || true; printf 'ADDR='; ip -j addr show 2>/dev/null || true"

type NodeStatus struct {
	Name       string   `json:"name"`
	Host       string   `json:"host"`
	Online     bool     `json:"online"`
	Keepalived string   `json:"keepalived"`
	Uptime     string   `json:"uptime"`
	Addresses  []string `json:"addresses"`
	Error      string   `json:"error"`
}

type VRRPStatus struct {
	Name    string            `json:"name"`
	VIP     string            `json:"vip"`
	Nodes   []string          `json:"nodes"`
	Master  *string           `json:"master"`
	Healthy bool              `json:"healthy"`
	Roles   map[string]string `json:"roles"`
}

type Snapshot struct {
	Nodes   map[string]NodeStatus `json:"nodes"`
	VRRP    []VRRPStatus          `json:"vrrp"`
	Updated time.Time             `json:"updated"`
}

type Monitor struct {
	cfg    *config.Config
	logger *slog.Logger
	mu     sync.RWMutex
	state  Snapshot
}

func New(cfg *config.Config, logger *slog.Logger) *Monitor {
	return &Monitor{cfg: cfg, logger: logger, state: Snapshot{Nodes: map[string]NodeStatus{}}}
}

func (m *Monitor) Run(ctx context.Context) {
	m.Poll(ctx)
	ticker := time.NewTicker(time.Duration(m.cfg.RefreshSeconds) * time.Second)
	defer ticker.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			m.Poll(ctx)
		}
	}
}

func (m *Monitor) Snapshot() Snapshot {
	m.mu.RLock()
	defer m.mu.RUnlock()
	return cloneSnapshot(m.state)
}

func (m *Monitor) Poll(parent context.Context) {
	nodes := make(map[string]NodeStatus, len(m.cfg.Nodes))
	type result struct { name string; status NodeStatus }
	results := make(chan result, len(m.cfg.Nodes))
	var wg sync.WaitGroup
	for _, node := range m.cfg.Nodes {
		node := node
		wg.Add(1)
		go func() {
			defer wg.Done()
			results <- result{name: node.Name, status: m.pollNode(parent, node)}
		}()
	}
	wg.Wait()
	close(results)
	for r := range results { nodes[r.name] = r.status }

	vrrp := make([]VRRPStatus, 0, len(m.cfg.VRRP))
	for _, instance := range m.cfg.VRRP { vrrp = append(vrrp, evaluateVRRP(instance, nodes)) }

	snapshot := Snapshot{Nodes: nodes, VRRP: vrrp, Updated: time.Now()}
	m.mu.Lock()
	m.state = snapshot
	m.mu.Unlock()
}

func (m *Monitor) pollNode(parent context.Context, node config.Node) NodeStatus {
	status := NodeStatus{Name: node.Name, Host: node.Host, Keepalived: "unknown", Uptime: "-", Addresses: []string{}}
	timeout := 8 * time.Second
	ctx, cancel := context.WithTimeout(parent, timeout)
	defer cancel()

	args := []string{"-o", "BatchMode=yes", "-o", fmt.Sprintf("ConnectTimeout=%d", m.cfg.SSH.ConnectTimeout)}
	if m.cfg.SSH.KeyFile != "" { args = append(args, "-i", m.cfg.SSH.KeyFile) }
	if m.cfg.SSH.KnownHostsFile != "" {
		args = append(args, "-o", "UserKnownHostsFile="+m.cfg.SSH.KnownHostsFile, "-o", "StrictHostKeyChecking=yes")
	}
	args = append(args, node.User+"@"+node.Host, probeCommand)
	cmd := exec.CommandContext(ctx, "ssh", args...)
	var stdout, stderr bytes.Buffer
	cmd.Stdout, cmd.Stderr = &stdout, &stderr
	err := cmd.Run()
	if err != nil {
		if ctx.Err() != nil { status.Error = ctx.Err().Error() } else { status.Error = strings.TrimSpace(stderr.String()); if status.Error == "" { status.Error = err.Error() } }
		return status
	}
	status.Online = true
	parseProbe(stdout.String(), &status)
	return status
}

func parseProbe(output string, status *NodeStatus) {
	for _, line := range strings.Split(output, "\n") {
		switch {
		case strings.HasPrefix(line, "KEEP="):
			status.Keepalived = strings.TrimSpace(strings.TrimPrefix(line, "KEEP="))
		case strings.HasPrefix(line, "UP="):
			status.Uptime = strings.TrimSpace(strings.TrimPrefix(line, "UP="))
		case strings.HasPrefix(line, "ADDR="):
			var interfaces []struct { AddrInfo []struct { Local string `json:"local"` } `json:"addr_info"` }
			if err := json.Unmarshal([]byte(strings.TrimPrefix(line, "ADDR=")), &interfaces); err != nil { continue }
			for _, iface := range interfaces { for _, addr := range iface.AddrInfo { if addr.Local != "" { status.Addresses = append(status.Addresses, addr.Local) } } }
		}
	}
}

func evaluateVRRP(instance config.VRRP, nodes map[string]NodeStatus) VRRPStatus {
	owners := make([]string, 0, 2)
	for _, name := range instance.Nodes {
		if contains(nodes[name].Addresses, instance.VIP) { owners = append(owners, name) }
	}
	var master *string
	if len(owners) == 1 { value := owners[0]; master = &value } else if len(owners) > 1 { value := "MULTIPLE"; master = &value }
	roles := make(map[string]string, len(instance.Nodes))
	for _, name := range instance.Nodes {
		node := nodes[name]
		switch {
		case !node.Online || node.Keepalived != "active": roles[name] = "FAULT"
		case master != nil && *master == name: roles[name] = "MASTER"
		default: roles[name] = "BACKUP"
		}
	}
	return VRRPStatus{Name: instance.Name, VIP: instance.VIP, Nodes: append([]string(nil), instance.Nodes...), Master: master, Healthy: len(owners) == 1, Roles: roles}
}

func contains(values []string, wanted string) bool { for _, value := range values { if value == wanted { return true } }; return false }

func cloneSnapshot(in Snapshot) Snapshot {
	out := Snapshot{Nodes: make(map[string]NodeStatus, len(in.Nodes)), VRRP: make([]VRRPStatus, len(in.VRRP)), Updated: in.Updated}
	for name, node := range in.Nodes { node.Addresses = append([]string(nil), node.Addresses...); out.Nodes[name] = node }
	for i, v := range in.VRRP { v.Nodes = append([]string(nil), v.Nodes...); v.Roles = cloneRoles(v.Roles); if v.Master != nil { x := *v.Master; v.Master = &x }; out.VRRP[i] = v }
	return out
}

func cloneRoles(in map[string]string) map[string]string { out := make(map[string]string, len(in)); for k, v := range in { out[k] = v }; return out }
