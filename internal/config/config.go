package config

import (
	"fmt"
	"os"

	"gopkg.in/yaml.v3"
)

type Config struct {
	RefreshSeconds int           `yaml:"refresh_seconds"`
	SSH            SSHConfig     `yaml:"ssh"`
	Notifications  Notifications `yaml:"notifications"`
	Nodes          []Node        `yaml:"nodes"`
	VRRP           []VRRP        `yaml:"vrrp"`
}

type SSHConfig struct {
	ConnectTimeout int    `yaml:"connect_timeout"`
	KeyFile        string `yaml:"key_file"`
	KnownHostsFile string `yaml:"known_hosts_file"`
}

type Notifications struct {
	NodeDown NodeDown `yaml:"node_down"`
}

type NodeDown struct {
	Enabled             bool `yaml:"enabled"`
	FailuresBeforeAlert int  `yaml:"failures_before_alert"`
	RecoveryMail        bool `yaml:"recovery_mail"`
}

type Node struct {
	Name string `yaml:"name" json:"name"`
	Host string `yaml:"host" json:"host"`
	User string `yaml:"user" json:"user"`
}

type VRRP struct {
	Name  string   `yaml:"name" json:"name"`
	VIP   string   `yaml:"vip" json:"vip"`
	Nodes []string `yaml:"nodes" json:"nodes"`
}

func Load(path string) (*Config, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("read config: %w", err)
	}
	var cfg Config
	if err := yaml.Unmarshal(data, &cfg); err != nil {
		return nil, fmt.Errorf("parse config: %w", err)
	}
	if cfg.RefreshSeconds <= 0 {
		cfg.RefreshSeconds = 5
	}
	if cfg.SSH.ConnectTimeout <= 0 {
		cfg.SSH.ConnectTimeout = 3
	}
	if cfg.Notifications.NodeDown.FailuresBeforeAlert <= 0 {
		cfg.Notifications.NodeDown.FailuresBeforeAlert = 3
	}
	if err := cfg.Validate(); err != nil {
		return nil, err
	}
	return &cfg, nil
}

func (c *Config) Validate() error {
	seen := make(map[string]struct{}, len(c.Nodes))
	for _, node := range c.Nodes {
		if node.Name == "" || node.Host == "" || node.User == "" {
			return fmt.Errorf("node name, host and user are required")
		}
		if _, ok := seen[node.Name]; ok {
			return fmt.Errorf("duplicate node %q", node.Name)
		}
		seen[node.Name] = struct{}{}
	}
	for _, group := range c.VRRP {
		if group.Name == "" || group.VIP == "" {
			return fmt.Errorf("VRRP name and VIP are required")
		}
		for _, name := range group.Nodes {
			if _, ok := seen[name]; !ok {
				return fmt.Errorf("VRRP %q references unknown node %q", group.Name, name)
			}
		}
	}
	return nil
}
