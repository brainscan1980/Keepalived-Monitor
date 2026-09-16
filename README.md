# 🛡️ Keepalived Monitor

> Ein modernes, schlankes Webinterface zur zentralen Überwachung und Verwaltung von **Keepalived-/VRRP-Clustern**.

Keepalived Monitor überwacht mehrere Linux-Nodes per SSH, erkennt den aktuellen Besitzer einer virtuellen IP (VIP), protokolliert Failover-Ereignisse und stellt Verfügbarkeit, Wartungszustände und Keepalived-Logs übersichtlich in einer responsiven Weboberfläche dar.

Das Projekt eignet sich besonders für Homelabs und kleinere HA-Umgebungen, in denen Dienste wie DNS, Reverse Proxy oder Vaultwarden über Keepalived/VRRP hochverfügbar bereitgestellt werden.

---

## ✨ Funktionen

### 🖥️ Zentrales Dashboard

- Übersicht aller konfigurierten Nodes
- Erreichbarkeitsstatus jedes Nodes
- Status des Keepalived-Dienstes
- Uptime der Nodes
- Übersicht aller VRRP-Instanzen und VIPs
- Automatische Erkennung des aktuellen MASTER-Nodes
- Erkennung von fehlendem MASTER und mehreren gleichzeitigen MASTERs
- Responsive Oberfläche für Desktop, Tablet und Smartphone
- Light- und Dark-Mode

### ❤️ Verfügbarkeitsüberwachung

Für jeden Node werden dauerhaft Verfügbarkeitsdaten erfasst:

- überwachte Gesamtzeit
- gesamte Downtime
- Verfügbarkeit in Prozent
- Anzahl erkannter Ausfälle
- aktueller Ausfallzustand

Die Daten bleiben über Container-Neustarts hinweg erhalten. Die Verfügbarkeitsstatistik kann bei Bedarf über die Einstellungen gezielt zurückgesetzt werden.

### 🔄 VRRP- und Failover-Monitoring

Keepalived Monitor prüft, auf welchem Node sich die konfigurierte VIP befindet und erkennt dadurch automatisch MASTER-Wechsel.

Damit lassen sich beispielsweise folgende HA-Dienste überwachen:

- DNS-Cluster
- Reverse Proxies
- Vaultwarden
- Webserver
- Load Balancer
- beliebige weitere Dienste mit Keepalived/VRRP

MASTER-Wechsel werden in der Ereignis-Historie protokolliert.

### 🧪 HA-/Cluster-Diagnose (v1.6 Entwicklung)

Die neue Diagnose-Engine von v1.6 überprüft VRRP-Instanzen zusätzlich auf typische HA-Probleme, unter anderem:

- genau ein MASTER vorhanden
- kein MASTER vorhanden
- mehrere MASTER / Split-Brain
- Erreichbarkeit aller beteiligten Nodes
- aktiver Keepalived-Dienst
- verfügbare BACKUP-Nodes
- fehlende Redundanz
- unbekannte konfigurierte Nodes
- Wartungsmodus eines Cluster-Mitglieds

Die Diagnose führt **keine automatischen Failover- oder Service-Aktionen** aus. Sie dient ausschließlich der Überwachung und Fehlerdiagnose.

### 📜 Live-Logs

Die Node-Detailansicht kann die aktuellen Keepalived-Journal-Logs direkt anzeigen.

Enthalten sind:

- automatische Aktualisierung
- Aktualisierung alle 2 Sekunden
- Pause / Fortsetzen
- manuelle Aktualisierung
- 50 / 100 / 250 / 500 Logzeilen
- Auto-Scroll
- Kopieren in die Zwischenablage
- saubere Fehleranzeige

Die Logs werden per `journalctl` direkt vom jeweiligen Node abgefragt.

### 🛠️ Keepalived-Steuerung

Keepalived kann aus der Node-Ansicht heraus verwaltet werden. Je nach Konfiguration und SSH-Berechtigungen stehen Aktionen wie Start, Stop und Neustart zur Verfügung.

> ⚠️ Das Stoppen oder Neustarten von Keepalived kann unmittelbar einen VRRP-Failover auslösen. Diese Funktionen sollten daher nur von autorisierten Administratoren verwendet werden.

### 🔧 Wartungsmodus

Nodes können in einen Wartungsmodus versetzt werden. Geplante Wartungsarbeiten werden dadurch von der normalen Verfügbarkeitsberechnung getrennt behandelt und erzeugen keine regulären Node-Down-/Recovery-Benachrichtigungen.

### 🔔 E-Mail-Benachrichtigungen

Optional können Benachrichtigungen per SMTP versendet werden, beispielsweise bei:

- Node-Ausfall
- Wiederherstellung eines Nodes

Die Anzahl fehlgeschlagener Prüfungen vor einer Benachrichtigung ist konfigurierbar. Zusätzlich besitzt die Anwendung eine Benachrichtigungs-Historie.

### 🕓 Ereignis-Historie

Keepalived Monitor protokolliert relevante Cluster-Ereignisse. Das Dashboard zeigt die neuesten Ereignisse; eine eigene Ereignisseite bietet eine paginierte Historie mit 10, 20, 50 oder 100 Einträgen pro Seite.

Einträge können gezielt gelöscht werden, ohne interne Failover-Zähler zu zerstören.

### 🔐 Anmeldung und Sicherheit

- geschützter Web-Login
- Benutzername und Passwort über `.env`
- eigener Flask Session Secret Key
- Secure-Cookie-Unterstützung für HTTPS
- SSH-Key read-only im Container
- keine Passwörter in `config.yml`
- `.env` und private SSH-Dateien gehören nicht ins Git-Repository

---

## 🏗️ Architektur

```text
                         ┌─────────────────────────┐
                         │     Web Browser         │
                         └────────────┬────────────┘
                                      │ HTTP / HTTPS
                                      ▼
                         ┌─────────────────────────┐
                         │   Keepalived Monitor    │
                         │   Flask + Docker        │
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

Der Monitor benötigt keinen Agenten auf den Ziel-Nodes. Statusinformationen werden per SSH mit Standard-Linux-Werkzeugen abgefragt.

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
- SSH-Zugriff vom Docker-Host bzw. Monitor-Container
- `ip`
- `uptime`
- `journalctl` für die Live-Logs

---

# 🚀 Installation

## 1. Repository klonen

```bash
git clone https://github.com/brainscan1980/Keepalived-Monitor.git
cd Keepalived-Monitor
```

Für die stabile Version sollte normalerweise der `main`-Branch verwendet werden.

```bash
git switch main
```

Die Entwicklung von v1.6 findet auf `develop-v1.6.0` statt:

```bash
git switch develop-v1.6.0
```

> ⚠️ Entwicklungsbranches können unfertige oder noch nicht vollständig integrierte Funktionen enthalten.

---

## 2. Konfigurationsdatei erstellen

Die Beispielkonfiguration kopieren:

```bash
cp config/config.example.yml config/config.yml
```

Anschließend bearbeiten:

```bash
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
| `vrrp[].name` | Name der VRRP-Instanz im Monitor |
| `vrrp[].vip` | virtuelle IP-Adresse |
| `vrrp[].nodes` | Nodes, die an dieser VRRP-Instanz teilnehmen |

---

## 3. SSH-Key einrichten

Im Projektverzeichnis:

```bash
mkdir -p ssh
```

Einen vorhandenen privaten SSH-Key nach `ssh/id_ed25519` kopieren oder einen eigenen Key für den Monitor erzeugen.

Beispiel:

```bash
ssh-keygen -t ed25519 -f ssh/id_ed25519
```

Den Public Key auf jedem Ziel-Node autorisieren, beispielsweise:

```bash
ssh-copy-id -i ssh/id_ed25519.pub root@192.168.1.10
ssh-copy-id -i ssh/id_ed25519.pub root@192.168.1.11
ssh-copy-id -i ssh/id_ed25519.pub root@192.168.1.12
```

Known Hosts erzeugen:

```bash
ssh-keyscan -H 192.168.1.10 192.168.1.11 192.168.1.12 > ssh/known_hosts
```

Dateirechte setzen:

```bash
chmod 600 ssh/id_ed25519
chmod 644 ssh/known_hosts
```

SSH anschließend testen:

```bash
ssh -i ssh/id_ed25519 root@192.168.1.10
```

Der Login sollte ohne Passwortabfrage funktionieren.

---

## 4. Umgebungsvariablen konfigurieren

Beispieldatei kopieren:

```bash
cp .env.example .env
```

Secret Key erzeugen:

```bash
openssl rand -hex 32
```

Danach `.env` bearbeiten:

```bash
nano .env
```

Minimal erforderlich:

```dotenv
ADMIN_USERNAME=admin
ADMIN_PASSWORD=BITTE-EIN-SICHERES-PASSWORT-VERWENDEN
SECRET_KEY=HIER-DEN-GENERIERTEN-SECRET-KEY-EINTRAGEN
COOKIE_SECURE=false
```

> 🔒 Die echte `.env` darf niemals in ein öffentliches Git-Repository eingecheckt werden.

Wenn die Anwendung ausschließlich über HTTPS aufgerufen wird, sollte gesetzt werden:

```dotenv
COOKIE_SECURE=true
```

---

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

---

## 6. Container bauen und starten

```bash
mkdir -p data
docker compose build
docker compose up -d
```

Oder kompakt:

```bash
docker compose up -d --build
```

Status prüfen:

```bash
docker compose ps
```

Logs anzeigen:

```bash
docker compose logs -f keepalived-monitor
```

---

## 7. Webinterface öffnen

Standardmäßig wird Port **5001** veröffentlicht:

```text
http://DOCKER-HOST:5001
```

Danach mit den in `.env` hinterlegten Zugangsdaten anmelden.

---

# 🔄 Aktualisierung

Vor einem Update empfiehlt sich ein Backup von `config`, `.env`, `ssh` und `data`.

Anschließend:

```bash
git pull
docker compose up -d --build
```

Containerstatus prüfen:

```bash
docker compose ps
```

---

# 🧪 Tests

Die isolierte HA-/Cluster-Diagnose von v1.6 besitzt Unit-Tests. Auf dem Entwicklungsbranch können sie mit folgendem Befehl ausgeführt werden:

```bash
python3 -m unittest -v tests/test_cluster_validation.py
```

Ein erfolgreicher Lauf endet mit:

```text
OK
```

---

# 🌐 Reverse Proxy

Keepalived Monitor kann problemlos hinter einem Reverse Proxy wie Caddy betrieben werden.

Ein einfaches Caddy-Beispiel:

```caddyfile
keepalived.example.com {
    reverse_proxy 127.0.0.1:5001
}
```

Bei ausschließlicher HTTPS-Nutzung sollte in `.env` zusätzlich gesetzt werden:

```dotenv
COOKIE_SECURE=true
```

Für öffentlich erreichbare Installationen sind zusätzliche Schutzmaßnahmen wie Zugriffsbeschränkungen, VPN oder vorgeschaltete Authentifizierung empfehlenswert.

---

# 🔐 Sicherheitshinweise

Der Monitor besitzt administrativen Zugriff auf die überwachten Keepalived-Nodes. Entsprechend wichtig ist eine saubere Absicherung.

Empfohlen:

1. Einen **dedizierten SSH-Benutzer** für Keepalived Monitor verwenden.
2. Root-SSH nach Möglichkeit vermeiden.
3. Nur die tatsächlich benötigten `sudo`-Befehle erlauben.
4. SSH ausschließlich per Key erlauben.
5. Den privaten SSH-Key niemals ins Repository committen.
6. `.env` niemals veröffentlichen.
7. Das Webinterface über HTTPS betreiben.
8. Bei Zugriff aus dem Internet zusätzliche Zugriffskontrollen verwenden.
9. Regelmäßige Backups des `data`-Verzeichnisses erstellen.

Der SSH-Key wird durch Docker read-only nach `/root/.ssh` in den Container eingebunden.

---

# 📁 Verzeichnisstruktur

```text
Keepalived-Monitor/
├── app/                    # Flask-Anwendung
│   ├── static/             # CSS / JavaScript
│   ├── templates/          # HTML-Templates
│   └── cluster_validation.py
├── config/
│   └── config.example.yml
├── data/                   # persistente Laufzeitdaten
├── ssh/                    # SSH-Key und known_hosts
├── tests/                  # Unit-Tests
├── .env.example
├── Dockerfile
├── docker-compose.yml
├── README.md
└── VERSION
```

Die produktiven Dateien `config/config.yml`, `.env`, private SSH-Keys und persistente Daten sollten lokal bleiben und nicht versehentlich veröffentlicht werden.

---

# 🐳 Docker-Volumes

Der Compose-Stack bindet folgende Verzeichnisse ein:

| Host | Container | Zweck |
|---|---|---|
| `./config` | `/app/config` | Anwendungskonfiguration |
| `./ssh` | `/root/.ssh` | SSH-Zugang, read-only |
| `./data` | `/app/data` | persistente Daten |

---

# 🩺 Troubleshooting

### Node wird als offline angezeigt

SSH-Verbindung vom Docker-Host testen:

```bash
ssh -i ssh/id_ed25519 root@NODE-IP
```

Danach prüfen:

```bash
systemctl is-active keepalived
ip -j addr show
uptime -p
```

### SSH Host Key Verification failed

`known_hosts` neu erzeugen bzw. den betroffenen Host aktualisieren:

```bash
ssh-keyscan -H NODE-IP >> ssh/known_hosts
```

### Keepalived wird nicht als aktiv erkannt

Auf dem Ziel-Node:

```bash
systemctl status keepalived
```

Der Dienst sollte als `active` gemeldet werden.

### VIP wird nicht erkannt

Auf dem betreffenden Node prüfen:

```bash
ip addr
```

Die in `config/config.yml` konfigurierte VIP muss exakt mit der vom MASTER gehaltenen Adresse übereinstimmen.

### Container startet nicht

```bash
docker compose ps
docker compose logs keepalived-monitor
```

Insbesondere prüfen, ob `ADMIN_USERNAME`, `ADMIN_PASSWORD` und `SECRET_KEY` in `.env` gesetzt sind.

---

# 🗺️ Entwicklung / Roadmap

Die aktuelle Entwicklung von **v1.6** konzentriert sich auf erweiterte Cluster-Diagnose und HA-Funktionen.

Bereits umgesetzt bzw. in Entwicklung:

- ✅ Live-Logs
- 🚧 erweiterte HA-/Cluster-Prüfung
- 📊 grafische Verfügbarkeitsstatistiken für 24 Stunden / 7 Tage / 30 Tage

Für spätere Versionen vorgesehen:

- sicherere bzw. erweiterte Node-Aktionen
- Konfigurations-Export/-Import
- automatisierter Failover-Test
- erweitertes Audit-Logging

---

# 🤝 Beiträge und Fehlerberichte

Fehlerberichte, Verbesserungsvorschläge und Pull Requests sind willkommen.

Bei einem Bug-Report sind folgende Informationen hilfreich:

- verwendete Keepalived-Monitor-Version
- Docker-/Compose-Version
- Betriebssystem und Architektur
- relevante Container-Logs
- Schritte zum Reproduzieren des Problems

Bitte niemals Passwörter, private SSH-Keys, Session-Secrets oder andere Zugangsdaten in Issues veröffentlichen.

---

# 📌 Projektstatus

Keepalived Monitor ist ein eigenständiges Homelab-/Administrationsprojekt und befindet sich in aktiver Entwicklung.

Die Anwendung soll Keepalived-/VRRP-Umgebungen transparenter machen und Administratoren dabei unterstützen, MASTER-Zustände, Redundanz, Ausfälle und Failover-Ereignisse schnell zu erkennen – ohne auf jedem Node einzeln arbeiten zu müssen.

---

<p align="center">
  <strong>Keepalived Monitor</strong><br>
  Monitor your VRRP cluster. See the MASTER. Know your redundancy.
</p>
