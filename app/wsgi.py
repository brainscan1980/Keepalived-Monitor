import app as core
from eventlog import init_eventlog
from cluster_integration import init_cluster_validation
from statistics import init_statistics
from node_actions import init_node_actions
from config_transfer import init_config_transfer
from failover_test import init_failover_test
from audit_log import init_audit_log

init_eventlog(core)
init_cluster_validation(core)
init_statistics(core)
init_audit_log(core)
init_node_actions(core)
init_config_transfer(core)
init_failover_test(core)
app=core.app
