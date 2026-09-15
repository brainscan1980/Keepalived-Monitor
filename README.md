# Keepalived Monitor

Schlankes Docker-Webinterface zur Überwachung mehrerer Keepalived/VRRP-Nodes per SSH.

## 1. SSH-Key bereitstellen

Lege einen privaten Key als `ssh/id_ed25519` ab. Der zugehörige Public Key muss auf allen Ziel-Nodes autorisiert sein.

Known Hosts erzeugen (auf dem Docker-Host):

```bash
ssh-keyscan -H 192.168.1.10 192.168.1.11 192.168.1.12 > ssh/known_hosts
chmod 600 ssh/id_ed25519
chmod 644 ssh/known_hosts
```

Teste vorher vom Docker-Host, dass der Key funktioniert.

## 2. Konfiguration

`config/config.yml` enthält Nodes und VIPs. Vorkonfiguriert sind DNS (`192.168.1.100`), Caddy (`192.168.1.101`) und Vaultwarden (`192.168.1.102`).

## 3. Start

```bash
mkdir -p data
docker compose build
docker compose up -d
```

Danach: `http://DOCKER-HOST:5001`

## Sicherheit

Der SSH-Key wird read-only gemountet. Für eine noch strengere Installation empfiehlt sich auf den Zielhosts ein dedizierter Benutzer mit sudo-Rechten ausschließlich für `systemctl is-active keepalived`, `ip -j addr show` und `uptime -p`, statt root-SSH.

## Reverse Proxy

Das Backend lauscht containerintern auf Port 5001 und kann problemlos hinter Caddy veröffentlicht werden.
