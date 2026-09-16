import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "app"))

from cluster_validation import validate_cluster, validate_instance


VIP = "192.168.178.11"
INSTANCE = {"name": "DNS", "vip": VIP, "nodes": ["Pi-01-6", "Pi-02-8", "Pi-03-5"]}


def node(master=False, online=True, keepalived="active", maintenance=False):
    return {
        "online": online,
        "keepalived": keepalived,
        "addresses": [VIP] if master else [],
        "maintenance": {"active": maintenance},
    }


class ClusterValidationTests(unittest.TestCase):
    def test_healthy_cluster(self):
        nodes = {
            "Pi-01-6": node(master=True),
            "Pi-02-8": node(),
            "Pi-03-5": node(),
        }
        result = validate_instance(nodes, INSTANCE)
        self.assertEqual(result["status"], "OK")
        self.assertEqual(result["master"], "Pi-01-6")
        self.assertEqual(result["available_backups"], 2)
        self.assertIn("SINGLE_MASTER", [c["code"] for c in result["checks"]])
        self.assertEqual(validate_cluster(nodes, [INSTANCE])["status"], "OK")

    def test_node_outage_is_warning_when_master_survives(self):
        nodes = {
            "Pi-01-6": node(master=True),
            "Pi-02-8": node(online=False),
            "Pi-03-5": node(),
        }
        result = validate_instance(nodes, INSTANCE)
        self.assertEqual(result["status"], "WARNING")
        self.assertEqual(result["master"], "Pi-01-6")
        self.assertEqual(result["available_backups"], 1)
        self.assertIn("NODE_OFFLINE", [c["code"] for c in result["checks"]])

    def test_keepalived_outage_is_warning_when_master_survives(self):
        nodes = {
            "Pi-01-6": node(master=True),
            "Pi-02-8": node(keepalived="inactive"),
            "Pi-03-5": node(),
        }
        result = validate_instance(nodes, INSTANCE)
        self.assertEqual(result["status"], "WARNING")
        self.assertIn("KEEPALIVED_INACTIVE", [c["code"] for c in result["checks"]])

    def test_no_master_is_error(self):
        nodes = {
            "Pi-01-6": node(),
            "Pi-02-8": node(),
            "Pi-03-5": node(),
        }
        result = validate_instance(nodes, INSTANCE)
        self.assertEqual(result["status"], "ERROR")
        self.assertIsNone(result["master"])
        self.assertIn("NO_MASTER", [c["code"] for c in result["checks"]])
        self.assertEqual(validate_cluster(nodes, [INSTANCE])["status"], "ERROR")

    def test_split_brain_is_error(self):
        nodes = {
            "Pi-01-6": node(master=True),
            "Pi-02-8": node(master=True),
            "Pi-03-5": node(),
        }
        result = validate_instance(nodes, INSTANCE)
        self.assertEqual(result["status"], "ERROR")
        self.assertEqual(result["master"], "MULTIPLE")
        self.assertEqual(set(result["masters"]), {"Pi-01-6", "Pi-02-8"})
        self.assertIn("MULTIPLE_MASTERS", [c["code"] for c in result["checks"]])

    def test_maintenance_is_warning_not_error(self):
        nodes = {
            "Pi-01-6": node(master=True),
            "Pi-02-8": node(maintenance=True),
            "Pi-03-5": node(),
        }
        result = validate_instance(nodes, INSTANCE)
        self.assertEqual(result["status"], "WARNING")
        self.assertEqual(result["maintenance_members"], 1)
        self.assertIn("NODE_MAINTENANCE", [c["code"] for c in result["checks"]])

    def test_missing_member_is_error(self):
        nodes = {
            "Pi-01-6": node(master=True),
            "Pi-02-8": node(),
        }
        result = validate_instance(nodes, INSTANCE)
        self.assertEqual(result["status"], "ERROR")
        self.assertIn("NODE_UNKNOWN", [c["code"] for c in result["checks"]])

    def test_empty_cluster_is_unknown(self):
        result = validate_cluster({}, [])
        self.assertEqual(result["status"], "UNKNOWN")
        self.assertEqual(result["instances"], [])


if __name__ == "__main__":
    unittest.main()
