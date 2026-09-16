import app as core
from eventlog import init_eventlog
from cluster_integration import init_cluster_validation
from statistics import init_statistics
from node_actions import init_node_actions
from config_transfer import init_config_transfer

init_eventlog(core)
init_cluster_validation(core)
init_statistics(core)
init_node_actions(core)
init_config_transfer(core)
app=core.app
