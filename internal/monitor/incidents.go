package monitor

import "sync"

type IncidentType string

const (
	IncidentFailover   IncidentType = "FAILOVER"
	IncidentNoMaster   IncidentType = "NO_MASTER"
	IncidentSplitBrain IncidentType = "SPLIT_BRAIN"
	IncidentNodeDown   IncidentType = "NODE_DOWN"
	IncidentRecovery   IncidentType = "RECOVERY"
)

type Incident struct {
	Type      IncidentType `json:"type"`
	Scope     string       `json:"scope"`
	Message   string       `json:"message"`
	OldMaster string       `json:"old_master,omitempty"`
	NewMaster string       `json:"new_master,omitempty"`
}

type incidentTracker struct {
	mu           sync.Mutex
	initialized  bool
	masters      map[string]string
	unhealthy    map[string]bool
	nodeFailures map[string]int
	nodeDown     map[string]bool
	threshold    int
}

func newIncidentTracker(threshold int) *incidentTracker {
	if threshold < 1 { threshold = 3 }
	return &incidentTracker{masters: map[string]string{}, unhealthy: map[string]bool{}, nodeFailures: map[string]int{}, nodeDown: map[string]bool{}, threshold: threshold}
}

func (t *incidentTracker) Evaluate(snapshot Snapshot) []Incident {
	t.mu.Lock(); defer t.mu.Unlock()
	incidents := make([]Incident, 0)
	for name, node := range snapshot.Nodes {
		if node.Online {
			t.nodeFailures[name] = 0
			if t.initialized && t.nodeDown[name] { incidents = append(incidents, Incident{Type: IncidentRecovery, Scope: name, Message: "Node is reachable again"}) }
			t.nodeDown[name] = false
			continue
		}
		t.nodeFailures[name]++
		if t.initialized && !t.nodeDown[name] && t.nodeFailures[name] >= t.threshold {
			t.nodeDown[name] = true
			incidents = append(incidents, Incident{Type: IncidentNodeDown, Scope: name, Message: "Node is unreachable"})
		}
	}
	for _, v := range snapshot.VRRP {
		master := "NONE"; if v.Master != nil { master = *v.Master }
		old := t.masters[v.Name]
		bad := master == "NONE" || master == "MULTIPLE"
		if t.initialized {
			if old != "" && old != master && old != "NONE" && old != "MULTIPLE" && master != "NONE" && master != "MULTIPLE" {
				incidents = append(incidents, Incident{Type: IncidentFailover, Scope: v.Name, Message: "VRRP master changed", OldMaster: old, NewMaster: master})
			}
			if !t.unhealthy[v.Name] && master == "NONE" { incidents = append(incidents, Incident{Type: IncidentNoMaster, Scope: v.Name, Message: "No node owns the virtual IP"}) }
			if !t.unhealthy[v.Name] && master == "MULTIPLE" { incidents = append(incidents, Incident{Type: IncidentSplitBrain, Scope: v.Name, Message: "Multiple nodes own the virtual IP"}) }
			if t.unhealthy[v.Name] && !bad { incidents = append(incidents, Incident{Type: IncidentRecovery, Scope: v.Name, Message: "VRRP instance is healthy again", NewMaster: master}) }
		}
		t.masters[v.Name] = master
		t.unhealthy[v.Name] = bad
	}
	t.initialized = true
	return incidents
}
