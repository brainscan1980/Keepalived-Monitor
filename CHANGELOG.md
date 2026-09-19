# Changelog

Alle wichtigen Änderungen an Keepalived Monitor werden in dieser Datei dokumentiert.

## [1.8.0] - 2026-09-19

### Hinzugefügt

- automatische Benachrichtigungen bei VRRP-MASTER-Wechseln
- Benachrichtigungen bei kritischen VRRP-Zuständen wie fehlendem MASTER und Split-Brain
- Benachrichtigungen bei Wiederherstellung eines MASTERs und Auflösung eines Split-Brain-Zustands
- getrennte Schalter für VRRP-Failover- und VRRP-Health-Benachrichtigungen
- zentrale Klassifizierung von VRRP-Ereignissen als `FAILOVER`, `NO_MASTER`, `SPLIT_BRAIN`, `RECOVERY` und `NORMALIZED`
- detailliertere VRRP-Ereignisinformationen im Dashboard
- Kategorie-Filter auf der Ereignisseite für Alle, VRRP, Nodes und Wartung
- `requirements.txt` mit fest definierten Python-Abhängigkeiten
- Dependabot-Konfiguration für Docker- und Python-Abhängigkeiten

### Geändert

- VRRP-Statistiken unterscheiden jetzt echte MASTER-Wechsel von kritischen und wiederhergestellten Zuständen
- Statistikseite verwendet die zentrale VRRP-Ereignisklassifizierung
- MASTER-Wechsel werden in Statistik und Ereignishistorie konsistent bezeichnet
- Split-Brain und fehlender MASTER werden in der Statistik getrennt ausgewiesen
- Ereignisseite verwendet verständliche Bezeichnungen für VRRP-Ereignisse
- Kategorie-Filterung der Ereignishistorie erfolgt serverseitig vor der Pagination
- Pagination und Einträge-pro-Seite-Auswahl berücksichtigen den aktiven Ereignisfilter
- Dashboard unterscheidet letzten MASTER-Wechsel und letztes kritisches VRRP-Ereignis
- Benachrichtigungseinstellungen wurden übersichtlicher strukturiert
- Detailoptionen für E-Mail und Telegram werden nur angezeigt, wenn der jeweilige Kanal aktiviert ist
- Abstände und Layout der Benachrichtigungseinstellungen wurden verbessert
- Python-Abhängigkeiten werden zentral über `requirements.txt` installiert

### Benachrichtigungen

- VRRP-MASTER-Wechsel können unabhängig von VRRP-Health-Ereignissen aktiviert oder deaktiviert werden
- E-Mail und Telegram können VRRP-Ereignisse parallel melden
- bestehender globaler Benachrichtigungs-Master bleibt übergeordnet
- Node-Benachrichtigungen und VRRP-Benachrichtigungen lassen sich unabhängig voneinander konfigurieren
- kritische Zustände und deren Wiederherstellung verwenden dieselbe zentrale Ereignisklassifizierung wie Dashboard, Statistik und Historie

### Kompatibilität

- bestehende Node-, E-Mail- und Telegram-Einstellungen bleiben erhalten
- bestehende Ereignisdaten werden weiterhin verwendet und bei der Auswertung anhand der zentralen VRRP-Klassifizierung interpretiert
- bestehende `/api/events`-Nutzung bleibt unverändert; die Kategorie-Filterung erweitert die paginierte Ereignis-API
- keine Datenbankmigration für den neuen Ereignisfilter erforderlich

## [1.7.0] - 2026-09-17

### Hinzugefügt

- Telegram als zusätzlicher Benachrichtigungskanal
- Telegram Bot-Token und Chat-ID direkt über die Einstellungsseite konfigurierbar
- Telegram-Testnachricht über die Weboberfläche
- automatische Telegram-Benachrichtigungen bei Node-Ausfall
- automatische Telegram-Benachrichtigungen bei Wiederherstellung eines Nodes
- globaler Master-Schalter für Benachrichtigungen
- unabhängige Aktivierung von E-Mail und Telegram
- getrennte Schalter für Node-DOWN- und Node-ONLINE-Benachrichtigungen
- Statusanzeige für E-Mail- und Telegram-Konfiguration

### Geändert

- Benachrichtigungseinstellungen vollständig neu strukturiert
- E-Mail- und Telegram-Konfiguration in getrennte Bereiche aufgeteilt
- E-Mail- und Telegram-Einstellungen werden bei deaktiviertem Benachrichtigungs-Master gesperrt
- gespeicherte Kanal-Einstellungen bleiben beim Ausschalten des Masters erhalten
- Benachrichtigungsstatus berücksichtigt den globalen Master-Schalter
- Node-DOWN- und Recovery-Benachrichtigungen können gleichzeitig über mehrere Kanäle versendet werden
- Fehler eines Benachrichtigungskanals blockieren den jeweils anderen Kanal nicht
- Änderungen am globalen Benachrichtigungsstatus werden im Audit-Log berücksichtigt

### Sicherheit

- Telegram Bot-Token wird verschlüsselt gespeichert
- gespeicherter Telegram Bot-Token wird nicht wieder im Webinterface ausgegeben
- Telegram-Zugangsdaten werden nicht über `.env` konfiguriert
- sensible Telegram-Daten werden nicht als Klartext ins Audit-Log geschrieben
- bestehender CSRF-Schutz gilt auch für Telegram-Test und Benachrichtigungseinstellungen

### Kompatibilität

- bestehende Installationen erhalten für den neuen globalen Benachrichtigungs-Master standardmäßig den aktivierten Zustand
- bestehende E-Mail-Konfigurationen bleiben erhalten
