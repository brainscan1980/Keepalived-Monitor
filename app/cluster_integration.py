"""Runtime integration for the pure HA/VRRP cluster validation engine.

The existing dashboard/API contract keeps using HEALTHY/DEGRADED/CRITICAL/UNKNOWN.
Detailed validation data is exposed as cluster.validation without changing the
existing frontend yet.
"""

from cluster_validation import validate_cluster


STATUS_MAP = {
    "OK": "HEALTHY",
    "WARNING": "DEGRADED",
    "ERROR": "CRITICAL",
    "UNKNOWN": "UNKNOWN",
}


def build_cluster_status(nodes, vrrp):
    """Build the backwards-compatible cluster status plus detailed diagnosis."""
    validation = validate_cluster(nodes, vrrp)
    status = STATUS_MAP.get(validation.get("status"), "UNKNOWN")

    issues = []
    for instance in validation.get("instances", []):
        for check in instance.get("checks", []):
            if check.get("level") in {"WARNING", "ERROR"}:
                issues.append(f"{instance.get('name')}: {check.get('message')}")

    if status == "HEALTHY":
        message = "Cluster vollständig funktions- und failoverbereit"
    elif status == "DEGRADED":
        message = "Redundanz eingeschränkt: " + (" · ".join(issues) if issues else validation.get("message", "Prüfung erforderlich"))
    elif status == "CRITICAL":
        message = " · ".join(issues) if issues else validation.get("message", "Kritischer Clusterzustand")
    else:
        message = validation.get("message", "Clusterzustand kann nicht bestimmt werden")

    return {
        "status": status,
        "message": message,
        "issues": issues,
        "validation": validation,
    }


def init_cluster_validation(core):
    """Attach detailed cluster validation to the existing polling pipeline."""
    core.cluster_health = build_cluster_status
