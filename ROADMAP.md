# 🗺️ Keepalived Monitor – Roadmap v1.7.0

Diese Roadmap beschreibt die geplante Entwicklung von **Keepalived Monitor v1.7.0**.

v1.7.0 baut auf dem Funktionsumfang von v1.6.x auf und entwickelt Keepalived Monitor stärker von einem reinen VRRP-Monitor zu einem **HA-Control-Center für Diagnose, Failover-Bereitschaft und sicheren Betrieb**.

## Status

- ⬜ geplant
- 🚧 in Entwicklung
- ✅ abgeschlossen

---

# Phase 1 – HA Intelligence

## ⬜ 1. Cluster Health & erweiterte HA-Diagnose

Ausbau der vorhandenen `cluster_validation`-Engine, ohne bestehende Prüfungen zu duplizieren.

Geplant:

- detaillierter Zustand je VRRP-Instanz
- konkrete Ursachen für eingeschränkte Redundanz
- Zeitpunkt der letzten relevanten Zustandsänderung
- bessere Unterscheidung zwischen gesundem, eingeschränktem und fehlerhaftem Clusterzustand
- verständliche Diagnosehinweise, z. B. „Node nicht erreichbar – Redundanz verloren“
- Nutzung der vorhandenen Node-, Keepalived-, Wartungs- und VRRP-Informationen

## ⬜ 2. Failover-Timeline

Grafische Historie des MASTER-Zustands pro VRRP-Instanz.

Geplant:

- Darstellung, welcher Node wann MASTER war
- MASTER-Wechsel und Failover-Ereignisse
- Zeiträume ohne MASTER
- Split-Brain-/Multiple-MASTER-Zustände
- Dauer eines MASTER-Wechsels, soweit aus den vorhandenen Messdaten ableitbar
- Auswahl geeigneter Zeiträume
- Integration mit der vorhandenen Statistik- und Ereignisdatenbasis

## ⬜ 3. Service-/Dependency-Monitoring

Optionale Überwachung zusätzlicher Dienste auf den Keepalived-Nodes.

Beispiele:

- Caddy
- Vaultwarden
- Blocky
- AdGuard Home
- weitere systemd-Dienste

Geplant:

- Services pro Node bzw. HA-Dienst konfigurierbar
- Statusabfrage über die vorhandene SSH-Infrastruktur
- Erkennung eines erreichbaren BACKUP-Nodes, dessen benötigter Dienst nicht betriebsbereit ist
- Integration in Clusterdiagnose und Dashboard
- keine automatische Service-Manipulation allein aufgrund eines Monitoring-Fehlers

## ⬜ 4. HA Readiness / Failover-Bereitschaft

Prüfung, ob ein Node bzw. eine VRRP-Instanz tatsächlich für einen Failover bereit ist.

Geplant:

- Node erreichbar
- Keepalived aktiv
- benötigte Services aktiv
- VIP-/VRRP-Zustand plausibel
- Wartungsmodus berücksichtigen
- vorhandene BACKUP-Kapazität prüfen
- Ergebniszustände wie `READY`, `DEGRADED` und `NOT READY`
- Einbindung in sichere Node-Aktionen
- Einbindung in den automatisierten Failover-Test

---

# Phase 2 – Operations

## ⬜ 5. Maintenance Scheduler

Erweiterung des vorhandenen Wartungsmodus um geplante Wartungsfenster.

Geplant:

- Startzeitpunkt festlegen
- Endzeitpunkt festlegen
- automatische Aktivierung des Wartungsmodus
- automatische Deaktivierung nach Ablauf
- Anzeige aktiver und kommender Wartungsfenster
- bestehende Availability- und Notification-Ausnahmen weiterhin berücksichtigen
- Audit-Logging für geplante Wartungsaktionen

## ⬜ 6. Notification Rules & Channels

Ausbau der vorhandenen E-Mail-Benachrichtigungen zu einem regelbasierten Benachrichtigungssystem.

### E-Mail

Die vorhandene SMTP-Unterstützung bleibt erhalten und wird in die neue Regelstruktur integriert.

### Telegram

Telegram wird als zusätzliche bzw. alternative Benachrichtigungsoption Bestandteil von v1.7.0.

Geplant:

- Telegram Bot API
- Bot-Token über `.env`
- Chat-ID über `.env`
- Telegram global aktivierbar/deaktivierbar
- E-Mail und Telegram einzeln oder parallel verwendbar
- Testnachricht aus den Einstellungen
- übersichtliche, formatierte Telegram-Meldungen

### Ereignisregeln

Benachrichtigungskanäle sollen je Ereignistyp konfigurierbar werden, unter anderem für:

- Node offline
- Node wieder online
- Keepalived ausgefallen
- Redundanz verloren
- Redundanz wiederhergestellt
- kein MASTER vorhanden
- mehrere MASTER / Split-Brain
- VRRP-Failover
- Ergebnis eines automatisierten Failover-Tests
- Wartungsereignisse

Wartungsmodus und geplante Wartungsfenster müssen bei der Benachrichtigungslogik berücksichtigt werden.

## ⬜ 7. System-/Diagnostics-Report

Erzeugung eines bereinigten Diagnoseberichts für Fehlersuche und Support.

Geplant:

- Keepalived-Monitor-Version
- Clusterzustand
- Node-Zustände
- VRRP-Instanzen und MASTER-Zustände
- HA-Diagnose
- Service-/Dependency-Zustände, sofern konfiguriert
- letzte relevante Ereignisse
- relevante Konfiguration ohne Secrets
- keine Passwörter, Tokens, privaten SSH-Keys oder Session-Secrets
- geeignete Ausgabe zum Anhängen an GitHub-Issues

---

# Phase 3 – UI & Backup

## ⬜ 8. Dashboard-Verbesserungen

Gezielter Ausbau des bestehenden Dashboards statt vollständigem Redesign.

Geplant:

- kompaktere Clusterübersicht
- MASTER-/BACKUP-Topologie
- Health-Zustand je VRRP-Instanz
- Failover-Bereitschaft auf einen Blick
- Anzahl verfügbarer/bereiter Nodes
- aktuelle Probleme und eingeschränkte Redundanz deutlicher hervorheben
- responsive Darstellung weiterhin für Desktop, Tablet und Smartphone
- Light- und Dark-Mode vollständig beibehalten

## ⬜ 9. Backup-/Restore-Verbesserungen

Ausbau der vorhandenen Config-Backup-/Restore-Funktionen.

Geplant:

- automatische Backup-Rotation
- Backup-Metadaten
- übersichtlichere Backup-Historie
- bessere Vorschau der Änderungen vor einem Restore
- sichere Bestätigung vor Restore-Aktionen
- Audit-Logging aller relevanten Aktionen

---

# Phase 4 – Stabilisierung & technische Qualität

## ⬜ 10. Architektur, Tests & Performance

Technische Konsolidierung vor dem Release von v1.7.0.

Geplant:

- weitere Modularisierung von `app.py`
- zusätzliche Unit-Tests
- Tests für Node Actions
- Tests für Failover-Test
- Tests für Config Transfer
- Tests für Audit-Log
- Tests für Cluster Health / HA Readiness
- Tests für Notification Rules und Telegram
- Datenbank-Indizes überprüfen und optimieren
- saubere Datenbank-Migrationen für neue Tabellen/Felder
- bestehende SSH-Multiplexing-Optimierung beibehalten
- Polling- und Datenbanklast gezielt messen
- Regressionstests der vorhandenen v1.6.x-Funktionen
- README und Dokumentation für v1.7.0 aktualisieren
- Release-Vorbereitung und Versionspflege

---

# Entwicklungsreihenfolge

Die Umsetzung erfolgt grundsätzlich in dieser Reihenfolge:

1. **Phase 1 – HA Intelligence**
2. **Phase 2 – Operations**
3. **Phase 3 – UI & Backup**
4. **Phase 4 – Stabilisierung & technische Qualität**

Jede größere Funktion soll zunächst isoliert implementiert und getestet werden, bevor sie tiefer in Dashboard, Aktionen oder Benachrichtigungen integriert wird.

---

# Release-Ziel v1.7.0

Mit v1.7.0 soll Keepalived Monitor nicht nur beantworten:

> **Welcher Node ist MASTER?**

sondern zusätzlich:

> **Ist der Cluster gesund, ist die Redundanz tatsächlich funktionsfähig und wäre ein Failover jetzt sicher möglich?**

Telegram ergänzt dabei E-Mail als schnellen Benachrichtigungskanal für wichtige HA-Ereignisse.
