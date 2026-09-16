# 🛡️ Keepalived Monitor

> Modernes, schlankes Webinterface zur zentralen Überwachung, Diagnose und Verwaltung von **Keepalived-/VRRP-Clustern**.

Keepalived Monitor überwacht Linux-Nodes agentenlos per SSH, erkennt MASTER und BACKUP-Zustände anhand der konfigurierten virtuellen IPs (VIPs), protokolliert Failover-Ereignisse und stellt Verfügbarkeit, historische Statistiken, Live-Logs und HA-Diagnosen in einer responsiven Weboberfläche bereit.

Das Projekt richtet sich besonders an Homelabs und kleinere HA-Umgebungen, in denen beispielsweise DNS, Reverse Proxies, Vaultwarden, Webserver oder andere Dienste mit Keepalived/VRRP hochverfügbar betrieben werden.

---

## ✨ Funktionsumfang

### 🖥️ Dashboard und Clusterstatus

- Übersicht aller konfigurierten Nodes
- Erreichbarkeitsstatus und Keepalived-Status
- Node-Uptime
- Übersicht aller VRRP-Instanzen und VIPs
- automatische Erkennung des aktuellen MASTER-Nodes
- Erkennung von fehlendem MASTER und mehreren gleichzeitigen MASTERs
- zentraler Cluster-Gesamtstatus
- klickbare Node-Karten mit Detailansicht
- responsive Oberfläche für Desktop, Tablet und Smartphone
- Light- und Dark-Mode

### 🧪 HA-/Cluster-Diagnose

Die integrierte Diagnose-Engine bewertet jede konfigurierte VRRP-Instanz und erkennt typische HA-Probleme:

- genau ein MASTER vorhanden
- kein MASTER vorhanden
- mehrere MASTER / Split-Brain
- unbekannte konfigurierte Nodes
- nicht erreichbare Nodes
- inaktiver Keepalived-Dienst
- verfügbare BACKUP-Nodes
- fehlende Backup-Kapazität
- fehlende Redundanz
- Wartungsmodus eines Cluster-Mitglieds

Die Diagnose liefert die Zustände **OK**, **WARNING**, **ERROR** und **UNKNOWN** und zeigt die Ergebnisse direkt im Dashboard an.

### ❤️ Verfügbarkeitsüberwachung

Für jeden Node werden dauerhaft Verfügbarkeitsdaten erfasst:

- überwachte Gesamtzeit
- gesamte Downtime
- Verfügbarkeit in Prozent
- Anzahl erkannter Ausfälle
- aktueller Ausfallzustand

Die Daten bleiben über Container-Neustarts hinweg erhalten. Geplante Wartung wird getrennt behandelt und fließt nicht als regulärer Ausfall in die Verfügbarkeitsberechnung ein. Die Verfügbarkeitsdaten können gezielt zurückgesetzt werden.

### 📊 Historische Statistiken

Eine eigene Statistikseite zeichnet Node- und VRRP-Zustände fortlaufend auf und stellt sie grafisch dar.

Verfügbare Zeitfenster:

- **24 Stunden**
- **7 Tage**
- **30 Tage**

Erfasst werden unter anderem Node-Verfügbarkeit, Keepalived-Verfügbarkeit, Wartungszeiten, VRRP-Gesundheit und MASTER-Zustände. Die Messwerte werden minütlich erfasst und bis zu 32 Tage vorgehalten. Historische Statistikdaten können über die Oberfläche zurückgesetzt werden.

### 🔄 VRRP- und Failover-Monitoring

Keepalived Monitor prüft regelmäßig, welcher Node die konfigurierte VIP besitzt. MASTER-Wechsel, Verlust einer VIP und Wiederherstellungen werden erkannt und protokolliert.

Damit lassen sich beispielsweise folgende HA-Dienste überwachen:

- DNS-Cluster
- Reverse Proxies
- Vaultwarden
- Webserver
- Load Balancer
- weitere Dienste mit Keepalived/VRRP

### 🧪 Automatisierter Failover-Test

Ein kontrollierter Failover-Test kann direkt über die Weboberfläche vorbereitet und ausgeführt werden.

Vor der Ausführung erfolgt ein Preflight-Check. Das Ergebnis wird strukturiert dargestellt, damit erkennbar ist, ob die Voraussetzungen für den Test erfüllt sind. Nach der Aktion wird der tatsächliche VRRP-/VIP-Zustand erneut geprüft und das Ergebnis des Failovers angezeigt.

### 🛡️ Sichere Node-Aktionen

Keepalived kann aus der Node-Ansicht heraus gestartet, gestoppt und neu gestartet werden. Vor kritischen Aktionen werden zusätzliche Prüfungen durchgeführt, um den aktuellen Clusterzustand und mögliche Auswirkungen auf die Redundanz zu berücksichtigen.

Nach relevanten Aktionen kann die Anwendung den resultierenden VRRP-Zustand verifizieren und anzeigen, ob der erwartete MASTER-/VIP-Wechsel tatsächlich stattgefunden hat.

> ⚠️ Administrative Keepalived-Aktionen können unmittelbar einen VRRP-Failover auslösen. Sie sollten nur von autorisierten Administratoren verwendet werden.

### 📜 Live-Logs

Die Node-Detailansicht zeigt die aktuellen Keepalived-Journal-Logs direkt aus `journalctl` an.

Enthalten sind:

- automatische Aktualisierung alle 2 Sekunden
- Pause / Fortsetzen
- manuelle Aktualisierung
- Auswahl von 50 / 100 / 250 / 500 Logzeilen
- Auto-Scroll
- Kopieren in die Zwischenablage
- Fehleranzeige bei nicht erreichbaren Nodes oder fehlgeschlagenen Log-Abfragen

### 🔧 Wartungsmodus

Nodes können gezielt in den Wartungsmodus versetzt werden. Während geplanter Wartung:

- wird die Downtime nicht als regulärer Verfügbarkeitsausfall gewertet
- werden normale Node-Down-/Recovery-Benachrichtigungen unterdrückt
- berücksichtigt die HA-Diagnose den Wartungszustand des Nodes

### 🔔 E-Mail-Benachrichtigungen

Optional können SMTP-Benachrichtigungen versendet werden, beispielsweise bei:

- Node-Ausfall
- Wiederherstellung eines Nodes

Die Anzahl fehlgeschlagener Prüfungen vor einer Benachrichtigung ist konfigurierbar. Zusätzlich besitzt die Anwendung eine Benachrichtigungs-Historie.

### 🕓 Ereignis-Historie

Relevante VRRP- und Cluster-Ereignisse werden persistent gespeichert. Das Dashboard zeigt die neuesten Ereignisse; eine eigene Ereignisseite bietet eine paginierte Historie mit 10, 20, 50 oder 100 Einträgen pro Seite.

Historieneinträge können gelöscht werden, ohne die internen VRRP-Failover-Zähler zu zerstören.

### 📦 Konfigurations-Export, Import und Backups

Die Anwendung besitzt Funktionen zur Verwaltung der Monitor-Konfiguration:

- Konfiguration exportieren
- Konfiguration importieren
- Import vor der Übernahme prüfen
- Änderungen bestätigen
- automatische bzw. verwaltete Konfigurations-Backups
- vorhandene Backups auflisten
- Backup wiederherstellen
- Backup löschen

Lokale produktive Konfigurationen und automatisch erzeugte `config.yml.backup-*`-Dateien werden nicht im Git-Repository versioniert.

### 🧾 Audit-Log

Administrative Aktionen werden in einem eigenen Audit-Log nachvollziehbar protokolliert. Dazu gehören unter anderem:

- Keepalived-Node-Aktionen
- Wartungsmodus-Änderungen
- automatisierte Failover-Tests
- Konfigurations- und Backup-Aktionen
- Statistik-, Ereignis- und Verfügbarkeits-Resets
- Änderungen an Anwendungseinstellungen

Sensible Zugangsdaten und Secrets werden dabei nicht als Klartext in das Audit-Log geschrieben. Für die Anzeige existiert eine eigene Audit-Seite in der Navigation.

### 🔐 Anmeldung und Sicherheit

- geschützter Web-Login
- Benutzername und Passwort über `.env`
- eigener Flask Session Secret Key
- CSRF-Schutz für schreibende Aktionen
- Secure-Cookie-Unterstützung für HTTPS
- SSH-Key read-only im Container
- keine Passwörter in `config.yml`
- `.env`, private SSH-Dateien, produktive `config.yml` und Config-Backups werden von Git ausgeschlossen

### ⚡ SSH- und Ressourcenoptimierung

Der Container verwendet OpenSSH-Verbindungsmultiplexing (`ControlMaster` / `ControlPersist`), sodass wiederkehrende Monitoring-Abfragen bestehende SSH-Verbindungen wiederverwenden können. Dadurch wird insbesondere bei kurzen Polling-Intervallen die CPU-Last durch wiederholte SSH-Handshakes deutlich reduziert.

---

## 🏗️ Architektur

```text
                         ┌─────────────────────────┐
                         │       Web Browser       │
                         └────────────┬────────────┘
                                      │ HTTP / HTTPS
                                      ▼
                         ┌─────────────────────────┐
                         │   Keepalived Monitor    │
                         │   Flask + Gunicorn      │
                         │       in Docker         │
                         └────────────┬────────────┘
                                      │ SSH
                   ┌──────────────────┼──────────────────┐
                   ▼                  ▼                  ▼
             ┌───────────┐      ┌───────────┐      ┌───────────┐
             │  Node 1   │      │  Node 2   │      │  Node 3   │
             │Keepalived │      │Keepalived │      │Keepalived │
             └───────────┘      └───────────┘      └───────────┘
                   └──────────────────┬──────────────────┘
                                      │
                                      ▼
                              Virtuelle IP (VIP)
```

Auf den Ziel-Nodes ist **kein zusätzlicher Agent** erforderlich. Statusinformationen und administrative Aktionen werden per SSH mit Standard-Linux-Werkzeugen ausgeführt.

---

## 📋 Voraussetzungen

### Docker-Host

- Linux
- Git
- Docker Engine
- Docker Compose Plugin (`docker compose`)
- Netzwerkzugriff auf die zu überwachenden Nodes

### Ziel-Nodes

- Linux
- Keepalived
- systemd
- SSH-Zugriff vom Monitor-Container
- `ip`
- `uptime`
- `journalctl` für Live-Logs
- passende Berechtigungen für administrative Keepalived-Aktionen, sofern diese verwendet werden sollen

---

# 🚀 Installation

## 1. Repository klonen

```bash
git clone https://github.com/brainscan1980/Keepalived-Monitor.git
cd Keepalived-Monitor
git switch main
```

Der `main`-Branch enthält den stabilen bzw. aktuell zusammengeführten Projektstand. Entwicklungsbranches können unfertige Funktionen enthalten und sollten nicht für produktive Installationen verwendet werden.

## 2. Konfigurationsdatei erstellen

```bash
cp config/config.example.yml config/config.yml
nano config/config.yml
```

Beispiel:

```yaml
refresh_seconds: 5

ssh:
  connect_timeout: 3
  key_file: /root/.ssh/id_ed25519
  known_hosts_file: /root/.ssh/known_hosts

notifications:
  node_down:
    enabled: true
    failures_before_alert: 3
    recovery_mail: true

nodes:
  - name: Node-01
    host: 192.168.1.10
    user: root

  - name: Node-02
    host: 192.168.1.11
    user: root

  - name: Node-03
    host: 192.168.1.12
    user: root

vrrp:
  - name: DNS
    vip: 192.168.1.100
    nodes: [Node-01, Node-02, Node-03]

  - name: Caddy
    vip: 192.168.1.101
    nodes: [Node-01, Node-02]
```

### Wichtige Optionen

| Option | Beschreibung |
|---|---|
| `refresh_seconds` | Intervall der Statusabfrage |
| `ssh.connect_timeout` | SSH-Verbindungs-Timeout |
| `ssh.key_file` | privater SSH-Key im Container |
| `ssh.known_hosts_file` | Known-Hosts-Datei |
| `nodes[].name` | eindeutiger Anzeigename des Nodes |
| `nodes[].host` | IP-Adresse oder Hostname |
| `nodes[].user` | SSH-Benutzer |
| `vrrp[].name` | Name der VRRP-Instanz |
| `vrrp[].vip` | virtuelle IP-Adresse |
| `vrrp[].nodes` | teilnehmende Nodes |

## 3. SSH-Key einrichten

```bash
mkdir -p ssh
ssh-keygen -t ed25519 -f ssh/id_ed25519
```

Public Key auf den Ziel-Nodes autorisieren, zum Beispiel:

```bash
ssh-copy-id -i ssh/id_ed25519.pub root@192.168.1.10
ssh-copy-id -i ssh/id_ed25519.pub root@192.168.1.11
ssh-copy-id -i ssh/id_ed25519.pub root@192.168.1.12
```

Known Hosts erzeugen:

```bash
ssh-keyscan -H 192.168.1.10 192.168.1.11 192.168.1.12 > ssh/known_hosts
chmod 600 ssh/id_ed25519
chmod 644 ssh/known_hosts
```

SSH anschließend testen:

```bash
ssh -i ssh/id_ed25519 root@192.168.1.10
```

Der Login sollte ohne Passwortabfrage funktionieren.

## 4. Umgebungsvariablen konfigurieren

```bash
cp .env.example .env
openssl rand -hex 32
nano .env
```

Minimal erforderlich:

```dotenv
ADMIN_USERNAME=admin
ADMIN_PASSWORD=BITTE-EIN-SICHERES-PASSWORT-VERWENDEN
SECRET_KEY=HIER-DEN-GENERIERTEN-SECRET-KEY-EINTRAGEN
COOKIE_SECURE=false
```

> 🔒 Die echte `.env` darf niemals in das Git-Repository eingecheckt werden.

Bei ausschließlicher HTTPS-Nutzung:

```dotenv
COOKIE_SECURE=true
```

## 5. Optional: E-Mail-Benachrichtigungen

Beispiel für SMTP mit STARTTLS:

```dotenv
MAIL_ENABLED=true
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_SECURITY=starttls
SMTP_USERNAME=monitor@example.com
SMTP_PASSWORD=DEIN-SMTP-PASSWORT
MAIL_FROM=monitor@example.com
MAIL_TO=admin@example.com
```

Ohne E-Mail-Versand:

```dotenv
MAIL_ENABLED=false
```

## 6. Container bauen und starten

```bash
mkdir -p data
docker compose up -d --build
```

Status und Logs:

```bash
docker compose ps
docker compose logs -f keepalived-monitor
```

## 7. Webinterface öffnen

Standardmäßig wird Port **5001** veröffentlicht:

```text
http://DOCKER-HOST:5001
```

Danach mit den in `.env` hinterlegten Zugangsdaten anmelden.

---

# 🔄 Aktualisierung

Vor einem Update empfiehlt sich ein Backup von `config`, `.env`, `ssh` und `data`.

```bash
git switch main
git pull --ff-only origin main
docker compose up -d --build
```

---

# 🧪 Tests

Für die isolierte HA-/Cluster-Diagnose existieren Unit-Tests:

```bash
python3 -m unittest -v tests/test_cluster_validation.py
```

Ein erfolgreicher Lauf endet mit:

```text
OK
```

---

# 🌐 Reverse Proxy

Keepalived Monitor kann hinter einem Reverse Proxy wie Caddy betrieben werden.

```caddyfile
keepalived.example.com {
    reverse_proxy 127.0.0.1:5001
}
```

Bei ausschließlicher HTTPS-Nutzung sollte `COOKIE_SECURE=true` gesetzt werden. Für öffentlich erreichbare Installationen sind zusätzliche Zugriffsbeschränkungen, VPN oder vorgeschaltete Authentifizierung empfehlenswert.

---

# 🔐 Sicherheitshinweise

Der Monitor kann administrativen Zugriff auf die überwachten Keepalived-Nodes besitzen. Empfohlen werden daher:

1. ein dedizierter SSH-Benutzer für Keepalived Monitor,
2. Root-SSH nach Möglichkeit vermeiden,
3. nur die tatsächlich benötigten `sudo`-Befehle erlauben,
4. SSH ausschließlich per Key verwenden,
5. private SSH-Keys und `.env` niemals veröffentlichen,
6. das Webinterface über HTTPS betreiben,
7. bei Internetzugriff zusätzliche Zugriffskontrollen einsetzen,
8. regelmäßige Backups des `data`-Verzeichnisses erstellen.

---

# 📁 Verzeichnisstruktur

```text
Keepalived-Monitor/
├── app/
│   ├── app.py
│   ├── audit_integration.py
│   ├── audit_log.py
│   ├── cluster_integration.py
│   ├── cluster_validation.py
│   ├── config_transfer.py
│   ├── eventlog.py
│   ├── failover_test.py
│   ├── node_actions.py
│   ├── statistics.py
│   ├── static/
│   └── templates/
├── config/
│   └── config.example.yml
├── data/
├── ssh/
├── tests/
├── .env.example
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── README.md
└── VERSION
```

Produktive Dateien wie `config/config.yml`, `config/config.yml.backup-*`, `.env`, private SSH-Keys und persistente Daten bleiben lokal und gehören nicht ins Repository.

---

# 🐳 Docker-Volumes

| Host | Container | Zweck |
|---|---|---|
| `./config` | `/app/config` | Anwendungskonfiguration |
| `./ssh` | `/root/.ssh` | SSH-Zugang, read-only |
| `./data` | `/app/data` | persistente Daten |

---

# 🩺 Troubleshooting

### Node wird als offline angezeigt

```bash
ssh -i ssh/id_ed25519 root@NODE-IP
systemctl is-active keepalived
ip -j addr show
uptime -p
```

### SSH Host Key Verification failed

```bash
ssh-keyscan -H NODE-IP >> ssh/known_hosts
```

### Keepalived wird nicht als aktiv erkannt

```bash
systemctl status keepalived
```

### VIP wird nicht erkannt

```bash
ip addr
```

Die in `config/config.yml` konfigurierte VIP muss exakt mit der Adresse übereinstimmen, die der MASTER aktuell besitzt.

### Container startet nicht

```bash
docker compose ps
docker compose logs keepalived-monitor
```

Insbesondere prüfen, ob `ADMIN_USERNAME`, `ADMIN_PASSWORD` und `SECRET_KEY` in `.env` gesetzt sind.

---

# 📌 Projektstatus

Der aktuelle `main`-Branch enthält den zusammengeführten Funktionsstand einschließlich Live-Logs, historischer Statistiken, HA-/Cluster-Diagnose, sicherer Node-Aktionen, Konfigurationsverwaltung, automatisiertem Failover-Test, Audit-Log und SSH-Performance-Optimierung.

Die Datei `VERSION` wird unabhängig von diesem README gepflegt. Die Planung der nächsten Entwicklungsstufe erfolgt separat, damit das README den **tatsächlich vorhandenen Funktionsumfang** dokumentiert und keine veraltete Roadmap enthält.

---

# 🤝 Beiträge und Fehlerberichte

Fehlerberichte, Verbesserungsvorschläge und Pull Requests sind willkommen. Hilfreich sind dabei die verwendete Keepalived-Monitor-Version, Docker-/Compose-Version, Betriebssystem und Architektur, relevante Container-Logs sowie reproduzierbare Schritte.

Bitte niemals Passwörter, private SSH-Keys, Session-Secrets oder andere Zugangsdaten in Issues veröffentlichen.

---

<p align="center">
  <strong>Keepalived Monitor</strong><br>
  Monitor your VRRP cluster. See the MASTER. Know your redundancy.
</p>
