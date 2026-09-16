import app as core
from eventlog import init_eventlog
from cluster_integration import init_cluster_validation
from statistics import init_statistics

init_eventlog(core)
init_cluster_validation(core)
init_statistics(core)
app=core.app
