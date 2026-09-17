# Changelog

Alle wichtigen Änderungen an Keepalived Monitor werden in dieser Datei dokumentiert.

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
