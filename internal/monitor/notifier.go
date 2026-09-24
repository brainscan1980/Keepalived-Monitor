package monitor

import "context"

// IncidentNotifier is implemented by notification backends without coupling
// the monitor package to SMTP, Telegram or any other transport.
type IncidentNotifier interface {
	Send(context.Context, Incident) error
	Enabled() bool
}
