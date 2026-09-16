"""Pure HA/VRRP cluster validation helpers.

This module intentionally has no Flask, SSH, database or systemd side effects.
It consumes the node and VRRP snapshots produced by app.py and returns a
JSON-serialisable diagnosis. Integration into the dashboard is a separate step.
"""

SEVERITY = {"OK": 0, "WARNING": 1, "ERROR": 2, "UNKNOWN": 3}


def _check(level, code, message, node=None):
    item = {"level": level, "code": code, "message": message}
    if node is not None:
        item["node"] = node
    return item


def _instance_status(checks):
    levels = {item["level"] for item in checks}
    if "ERROR" in levels:
        return "ERROR"
    if "WARNING" in levels:
        return "WARNING"
    if "UNKNOWN" in levels:
        return "UNKNOWN"
    return "OK"


def validate_instance(nodes, instance):
    """Validate one VRRP instance against a node status snapshot."""
    name = str(instance.get("name") or "Unbenannte VRRP-Instanz")
    vip = str(instance.get("vip") or "")
    members = list(instance.get("nodes") or [])
    owners = [member for member in members if vip and vip in (nodes.get(member, {}).get("addresses") or [])]
    checks = []

    if not vip:
        checks.append(_check("ERROR", "VIP_MISSING", "Für diese VRRP-Instanz ist keine VIP konfiguriert."))
    elif len(owners) == 1:
        checks.append(_check("OK", "SINGLE_MASTER", f"Genau ein MASTER besitzt die VIP {vip}: {owners[0]}.", owners[0]))
    elif len(owners) == 0:
        checks.append(_check("ERROR", "NO_MASTER", f"Kein Node besitzt die VIP {vip}."))
    else:
        checks.append(_check("ERROR", "MULTIPLE_MASTERS", f"Mehrere Nodes besitzen gleichzeitig die VIP {vip}: {', '.join(owners)}."))

    available_backups = 0
    maintenance_members = 0
    for member in members:
        node = nodes.get(member)
        if node is None:
            checks.append(_check("ERROR", "NODE_UNKNOWN", f"Der konfigurierte Node {member} ist im Status-Snapshot nicht vorhanden.", member))
            continue

        maintenance = bool((node.get("maintenance") or {}).get("active"))
        if maintenance:
            maintenance_members += 1
            checks.append(_check("WARNING", "NODE_MAINTENANCE", f"{member} befindet sich im Wartungsmodus.", member))
            continue

        if not node.get("online"):
            checks.append(_check("WARNING", "NODE_OFFLINE", f"{member} ist nicht erreichbar; die Redundanz ist eingeschränkt.", member))
            continue

        keepalived = str(node.get("keepalived") or "unknown")
        if keepalived != "active":
            checks.append(_check("WARNING", "KEEPALIVED_INACTIVE", f"Keepalived auf {member} ist {keepalived}.", member))
            continue

        if member in owners:
            checks.append(_check("OK", "MASTER_READY", f"{member} ist erreichbar und Keepalived ist aktiv.", member))
        else:
            available_backups += 1
            checks.append(_check("OK", "BACKUP_READY", f"{member} ist als verfügbarer BACKUP-Node bereit.", member))

    if len(members) > 1:
        if available_backups:
            checks.append(_check("OK", "BACKUP_CAPACITY", f"{available_backups} verfügbarer BACKUP-Node{'s' if available_backups != 1 else ''} erkannt."))
        elif len(owners) == 1:
            checks.append(_check("WARNING", "NO_BACKUP_CAPACITY", "Der MASTER ist aktiv, aber aktuell steht kein betriebsbereiter BACKUP-Node zur Verfügung."))
    elif len(members) == 1:
        checks.append(_check("WARNING", "NO_REDUNDANCY", "Für diese VRRP-Instanz ist nur ein Node konfiguriert; es besteht keine Redundanz."))
    else:
        checks.append(_check("ERROR", "NO_MEMBERS", "Für diese VRRP-Instanz sind keine Nodes konfiguriert."))

    status = _instance_status(checks)
    return {
        "name": name,
        "vip": vip or None,
        "status": status,
        "master": owners[0] if len(owners) == 1 else ("MULTIPLE" if len(owners) > 1 else None),
        "masters": owners,
        "members": members,
        "available_backups": available_backups,
        "maintenance_members": maintenance_members,
        "checks": checks,
    }


def validate_cluster(nodes, vrrp_instances):
    """Return an overall diagnosis plus details for every VRRP instance."""
    instances = [validate_instance(nodes, instance) for instance in (vrrp_instances or [])]
    if not instances:
        return {
            "status": "UNKNOWN",
            "message": "Keine VRRP-Instanzen zur Cluster-Prüfung vorhanden.",
            "summary": {"ok": 0, "warning": 0, "error": 0, "unknown": 0},
            "instances": [],
        }

    summary = {
        "ok": sum(item["status"] == "OK" for item in instances),
        "warning": sum(item["status"] == "WARNING" for item in instances),
        "error": sum(item["status"] == "ERROR" for item in instances),
        "unknown": sum(item["status"] == "UNKNOWN" for item in instances),
    }

    if summary["error"]:
        status = "ERROR"
        message = f"{summary['error']} VRRP-Instanz(en) mit kritischem HA-Fehler."
    elif summary["warning"]:
        status = "WARNING"
        message = f"Cluster funktionsfähig, aber Redundanz bei {summary['warning']} VRRP-Instanz(en) eingeschränkt."
    elif summary["unknown"]:
        status = "UNKNOWN"
        message = "Clusterzustand kann nicht vollständig bestimmt werden."
    else:
        status = "OK"
        message = "Alle VRRP-Instanzen sind konsistent und redundant verfügbar."

    return {"status": status, "message": message, "summary": summary, "instances": instances}
