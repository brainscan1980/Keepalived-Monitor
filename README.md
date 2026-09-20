# 🛡️ Keepalived Monitor

> Modernes, schlankes Webinterface zur zentralen Überwachung, Diagnose und Verwaltung von **Keepalived-/VRRP-Clustern**.

Keepalived Monitor überwacht Linux-Nodes agentenlos per SSH, erkennt MASTER- und BACKUP-Zustände anhand der konfigurierten virtuellen IPs (VIPs), protokolliert Failover-Ereignisse und stellt Verfügbarkeit, historische Statistiken, Live-Logs und HA-Diagnosen in einer responsiven Weboberfläche bereit.

Das Projekt richtet sich besonders an Homelabs und kleinere HA-Umgebungen, in denen beispielsweise DNS, Reverse Proxies, Vaultwarden, Webserver oder andere Dienste mit Keepalived/VRRP hochverfügbar betrieben werden.

## 🐳 Docker Hub

Das fertige Docker-Image wird automatisch über GitHub Actions auf Docker Hub veröffentlicht:

```text
brainscan1980/keepalived-monitor:latest
```

**Docker Hub:** https://hub.docker.com/r/brainscan1980/keepalived-monitor

Das Image wird als Multi-Architecture-Image für folgende Plattformen gebaut:

- `linux/amd64`
- `linux/arm64`

Docker wählt beim Pull automatisch die passende Architektur. Damit läuft dasselbe Image sowohl auf klassischen x86-64-Docker-Hosts als auch auf ARM64-Systemen wie Raspberry Pis.

---

## ✨ Funktionsumfang

- Dashboard mit Node-, Keepalived-, VRRP- und VIP-Status
- automatische MASTER-/BACKUP-Erkennung
- Split-Brain- und Missing-MASTER-Erkennung
- HA-/Cluster-Diagnose mit OK, WARNING, ERROR und UNKNOWN
- historische Statistiken für 24 Stunden, 7 Tage und 30 Tage
- Verfügbarkeits- und Downtime-Auswertung
- VRRP-/Failover-Ereignishistorie
- automatisierter Failover-Test mit Preflight-Check
- sichere Start-/Stop-/Restart-Aktionen für Keepalived
- Live-Logs aus `journalctl`
- Wartungsmodus
- E-Mail- und Telegram-Benachrichtigungen
- Konfigurations-Export, Import und Backups
- Audit-Log für administrative Aktionen
- geschützter Web-Login und CSRF-Schutz
- SSH-Verbindungsmultiplexing zur Ressourcenoptimierung
- responsive Oberfläche mit Light- und Dark-Mode

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

# 🚀 Installation über Docker Hub

Für eine produktive Installation wird das bereits gebaute Image von Docker Hub empfohlen. Ein lokaler Docker-Build ist nicht erforderlich.

## 1. Repository klonen

Die Konfigurationsbeispiele und Compose-Datei befinden sich im GitHub-Repository:

```bash
git clone https://github.com/brainscan1980/Keepalived-Monitor.git
cd Keepalived-Monitor
git switch main
```

## 2. Konfiguration erstellen

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

nodes:
  - name: Node-01
    host: 192.168.1.10
    user: root

  - name: Node-02
    host: 192.168.1.11
    user: root

vrrp:
  - name: DNS
    vip: 192.168.1.100
    nodes: [Node-01, Node-02]
```

## 3. SSH-Key einrichten

```bash
mkdir -p ssh
ssh-keygen -t ed25519 -f ssh/id_ed25519
```

Public Key auf den Ziel-Nodes autorisieren:

```bash
ssh-copy-id -i ssh/id_ed25519.pub root@192.168.1.10
ssh-copy-id -i ssh/id_ed25519.pub root@192.168.1.11
```

Known Hosts erzeugen:

```bash
ssh-keyscan -H 192.168.1.10 192.168.1.11 > ssh/known_hosts
chmod 600 ssh/id_ed25519
chmod 644 ssh/known_hosts
```

Der SSH-Login sollte anschließend ohne Passwortabfrage funktionieren.

## 4. `.env` erstellen

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

Bei ausschließlicher HTTPS-Nutzung:

```dotenv
COOKIE_SECURE=true
```

> 🔒 `.env`, private SSH-Keys und produktive Konfigurationsdateien niemals veröffentlichen oder in Git committen.

## 5. Container starten

Die mitgelieferte `docker-compose.yml` verwendet das veröffentlichte Docker-Hub-Image:

```yaml
services:
  keepalived-monitor:
    image: brainscan1980/keepalived-monitor:latest
```

Image laden und Container starten:

```bash
mkdir -p data
docker compose pull
docker compose up -d
```

Status und Logs prüfen:

```bash
docker compose ps
docker compose logs -f keepalived-monitor
```

Standardmäßig ist das Webinterface über Port **5001** erreichbar:

```text
http://DOCKER-HOST:5001
```

---

# 🔄 Aktualisierung

Vor einem Update empfiehlt sich ein Backup von `config`, `.env`, `ssh` und `data`.

Bei Verwendung des Docker-Hub-Images reicht anschließend:

```bash
git switch main
git pull --ff-only origin main
docker compose pull
docker compose up -d
```

Nicht mehr benötigte alte Images können optional entfernt werden:

```bash
docker image prune -f
```

Persistente Konfigurationen und Daten bleiben durch die eingebundenen Volumes erhalten.

---

# 🏷️ Docker-Tags und Releases

Der GitHub-Actions-Workflow baut und veröffentlicht die Images automatisch.

Ein Push auf `main` aktualisiert:

```text
brainscan1980/keepalived-monitor:latest
```

Ein Git-Tag wie `v1.2.3` erzeugt zusätzlich:

```text
brainscan1980/keepalived-monitor:1.2.3
brainscan1980/keepalived-monitor:1.2
brainscan1980/keepalived-monitor:1
```

Für produktive Installationen kann statt `latest` bewusst eine feste Version verwendet werden:

```yaml
image: brainscan1980/keepalived-monitor:1.2.3
```

Damit bleibt die Installation auf dieser Version, bis der Tag in `docker-compose.yml` bewusst geändert wird.

---

# 🛠️ Lokaler Build aus dem Quellcode

Für Entwicklung oder eigene Anpassungen kann das Image weiterhin lokal gebaut werden:

```bash
git clone https://github.com/brainscan1980/Keepalived-Monitor.git
cd Keepalived-Monitor
docker build -t keepalived-monitor:local .
```

Der produktive Standardweg ist dagegen das fertige Multi-Arch-Image von Docker Hub.

---

# 🔔 Benachrichtigungen

Keepalived Monitor unterstützt **E-Mail und Telegram**. Die Konfiguration erfolgt nach dem ersten Start über die Seite **Einstellungen** im Webinterface.

Unterstützt werden unter anderem:

- Node-Ausfall und Recovery
- VRRP-MASTER-Wechsel
- kein MASTER vorhanden
- Split-Brain
- Wiederherstellung eines MASTERs
- Auflösung eines Split-Brain-Zustands

SMTP-Zugangsdaten sowie Telegram Bot-Token und Chat-ID werden über die Oberfläche verwaltet. Testfunktionen für beide Benachrichtigungskanäle sind integriert.

---

# 🌐 Reverse Proxy

Keepalived Monitor kann hinter einem Reverse Proxy wie Caddy betrieben werden.

```caddyfile
keepalived.example.com {
    reverse_proxy 127.0.0.1:5001
}
```

Bei ausschließlicher HTTPS-Nutzung sollte `COOKIE_SECURE=true` gesetzt werden.

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

### VIP wird nicht erkannt

```bash
ip addr
```

Die konfigurierte VIP muss exakt mit der Adresse übereinstimmen, die der MASTER aktuell besitzt.

### Container startet nicht

```bash
docker compose ps
docker compose logs keepalived-monitor
```

Insbesondere prüfen, ob `ADMIN_USERNAME`, `ADMIN_PASSWORD` und `SECRET_KEY` in `.env` gesetzt sind.

---

# 🔒 Sicherheitshinweise

1. einen dedizierten SSH-Benutzer für Keepalived Monitor verwenden,
2. Root-SSH nach Möglichkeit vermeiden,
3. nur tatsächlich benötigte `sudo`-Befehle erlauben,
4. SSH ausschließlich per Key verwenden,
5. private SSH-Keys und `.env` niemals veröffentlichen,
6. das Webinterface über HTTPS betreiben,
7. bei Internetzugriff zusätzliche Zugriffskontrollen einsetzen,
8. regelmäßige Backups des `data`-Verzeichnisses erstellen.

---

# 📁 Verzeichnisstruktur

```text
Keepalived-Monitor/
├── .github/
│   └── workflows/
│       └── docker-publish.yml
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
├── .dockerignore
├── .env.example
├── .gitignore
├── Dockerfile
├── docker-compose.yml
├── README.md
└── VERSION
```

Produktive Dateien wie `config/config.yml`, `config/config.yml.backup-*`, `.env`, private SSH-Keys und persistente Daten bleiben lokal und gehören nicht ins Repository.

---

# 🤝 Beiträge und Fehlerberichte

Fehlerberichte, Verbesserungsvorschläge und Pull Requests sind willkommen. Hilfreich sind dabei die verwendete Keepalived-Monitor-Version, Docker-/Compose-Version, Betriebssystem und Architektur, relevante Container-Logs sowie reproduzierbare Schritte.

Bitte niemals Passwörter, private SSH-Keys, Session-Secrets oder andere Zugangsdaten in Issues veröffentlichen.

---

<p align="center">
  <strong>Keepalived Monitor</strong><br>
  Monitor your VRRP cluster. See the MASTER. Know your redundancy.
</p>

---

## 📄 Lizenz

Keepalived Monitor wird unter der **MIT License** veröffentlicht.

Die Software darf frei verwendet, kopiert, verändert und weitergegeben werden – auch für kommerzielle Zwecke. Der Copyright- und Lizenzhinweis muss dabei erhalten bleiben.

Weitere Informationen findest du in der Datei [LICENSE](LICENSE).
