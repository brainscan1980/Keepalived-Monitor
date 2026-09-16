import app as core
from eventlog import init_eventlog
from cluster_integration import init_cluster_validation

init_eventlog(core)
init_cluster_validation(core)
app=core.app
