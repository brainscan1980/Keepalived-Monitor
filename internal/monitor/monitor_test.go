package monitor

import (
	"testing"

	"github.com/brainscan1980/Keepalived-Monitor/internal/config"
)

func TestEvaluateVRRPSingleMaster(t *testing.T) {
	vip := "192.168.178.11"
	nodes := map[string]NodeStatus{
		"node1": {Name: "node1", Online: true, Keepalived: "active", Addresses: []string{vip}},
		"node2": {Name: "node2", Online: true, Keepalived: "active", Addresses: []string{"192.168.178.8"}},
	}
	got := evaluateVRRP(config.VRRP{Name: "DNS", VIP: vip, Nodes: []string{"node1", "node2"}}, nodes)
	if !got.Healthy || got.Master == nil || *got.Master != "node1" { t.Fatalf("unexpected VRRP state: %#v", got) }
	if got.Roles["node1"] != "MASTER" || got.Roles["node2"] != "BACKUP" { t.Fatalf("unexpected roles: %#v", got.Roles) }
}

func TestEvaluateVRRPMultipleOwners(t *testing.T) {
	vip := "192.168.178.11"
	nodes := map[string]NodeStatus{
		"node1": {Name: "node1", Online: true, Keepalived: "active", Addresses: []string{vip}},
		"node2": {Name: "node2", Online: true, Keepalived: "active", Addresses: []string{vip}},
	}
	got := evaluateVRRP(config.VRRP{Name: "DNS", VIP: vip, Nodes: []string{"node1", "node2"}}, nodes)
	if got.Healthy || got.Master == nil || *got.Master != "MULTIPLE" { t.Fatalf("expected split brain state, got %#v", got) }
}

func TestEvaluateVRRPFaultRole(t *testing.T) {
	nodes := map[string]NodeStatus{"node1": {Name: "node1", Online: false, Keepalived: "unknown"}}
	got := evaluateVRRP(config.VRRP{Name: "DNS", VIP: "192.168.178.11", Nodes: []string{"node1"}}, nodes)
	if got.Roles["node1"] != "FAULT" { t.Fatalf("expected FAULT, got %q", got.Roles["node1"]) }
}
