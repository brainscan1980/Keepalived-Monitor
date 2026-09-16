"""Controlled automated VRRP failover tests with preflight and failsafe recovery."""
import threading
import time
from flask import Blueprint, jsonify, request

bp=Blueprint('failover_test',__name__)
_core=None
_test_lock=threading.Lock()
FAILOVER_TIMEOUT=20
RECOVERY_TIMEOUT=25
POLL_INTERVAL=1


def _auth():
    return bool(_core.session.get('authenticated'))


def _snapshot():
    with _core.lock:
        nodes={k:dict(v) for k,v in (_core.cache.get('nodes') or {}).items()}
        vrrp=[dict(v) for v in (_core.cache.get('vrrp') or [])]
    return nodes,vrrp


def _maintenance(node):
    return bool((node.get('maintenance') or {}).get('active'))


def _ready(node):
    return bool(node.get('online') and node.get('keepalived')=='active' and not _maintenance(node))


def _instance_preflight(instance,nodes):
    name=instance.get('name');master=instance.get('master');members=list(instance.get('nodes') or [])
    result={'name':name,'vip':instance.get('vip'),'master':master,'members':members,'ready_backups':[],'blocked_reasons':[],'allowed':False}
    if not members:
        result['blocked_reasons'].append('Keine Nodes für diese VRRP-Instanz konfiguriert.');return result
    if master in {None,'NONE','MULTIPLE'}:
        result['blocked_reasons'].append('Es gibt aktuell keinen eindeutig ermittelten MASTER.');return result
    if master not in members:
        result['blocked_reasons'].append('Der aktuelle MASTER gehört nicht zur konfigurierten VRRP-Instanz.');return result
    master_node=nodes.get(master) or {}
    if not master_node.get('online'):result['blocked_reasons'].append(f'MASTER {master} ist nicht erreichbar.')
    elif master_node.get('keepalived')!='active':result['blocked_reasons'].append(f'Keepalived auf MASTER {master} ist nicht aktiv.')
    elif _maintenance(master_node):result['blocked_reasons'].append(f'MASTER {master} befindet sich im Wartungsmodus.')
    for candidate in members:
        if candidate!=master and _ready(nodes.get(candidate) or {}):result['ready_backups'].append(candidate)
    if not result['ready_backups']:result['blocked_reasons'].append('Kein betriebsbereiter Backup-Node verfügbar.')
    result['allowed']=not result['blocked_reasons'];return result


def failover_preflight():
    nodes,vrrp=_snapshot();instances=[_instance_preflight(v,nodes) for v in vrrp];allowed=[x for x in instances if x['allowed']];blocked=[x for x in instances if not x['allowed']];masters={x['master'] for x in allowed if x.get('master') not in {None,'NONE','MULTIPLE'}}
    return {'safe_to_test':bool(allowed),'instances':instances,'summary':{'total':len(instances),'testable':len(allowed),'blocked':len(blocked),'masters':sorted(masters)},'note':'Diese Prüfung ist rein diagnostisch. Es wurde keine Keepalived-Aktion ausgeführt.'}


def _node_config(name):
    for node in (_core.cfg().get('nodes') or []):
        if node.get('name')==name:return node
    return None


def _service(name,action):
    node=_node_config(name)
    if not node:return False,'Node nicht gefunden.'
    rc,out,err=_core.ssh(node,f'systemctl {action} keepalived',12)
    if rc!=0:return False,(err or out or f'Keepalived {action} fehlgeschlagen.').strip()
    return True,''


def _poll():
    try:_core.poll();return True
    except Exception:return False


def _wait_failover(master,affected):
    started=time.monotonic();latest=[]
    while time.monotonic()-started<FAILOVER_TIMEOUT:
        _poll();nodes,vrrp=_snapshot();by_name={v.get('name'):v for v in vrrp};latest=[];ok=True
        for expected in affected:
            current=by_name.get(expected['name']) or {};new_master=current.get('master');healthy=bool(current.get('healthy'));moved=healthy and new_master not in {None,'NONE','MULTIPLE',master} and new_master in expected['ready_backups']
            latest.append({'name':expected['name'],'vip':expected.get('vip'),'old_master':master,'new_master':new_master,'healthy':healthy,'moved':moved})
            if not moved:ok=False
        if ok:return True,round(time.monotonic()-started,1),latest
        time.sleep(POLL_INTERVAL)
    return False,round(time.monotonic()-started,1),latest


def _wait_service_active(master):
    started=time.monotonic()
    while time.monotonic()-started<RECOVERY_TIMEOUT:
        _poll();nodes,_=_snapshot();node=nodes.get(master) or {}
        if node.get('online') and node.get('keepalived')=='active':return True,round(time.monotonic()-started,1)
        time.sleep(POLL_INTERVAL)
    return False,round(time.monotonic()-started,1)


def _wait_cluster_recovery(affected):
    started=time.monotonic();latest=[]
    while time.monotonic()-started<RECOVERY_TIMEOUT:
        _poll();_,vrrp=_snapshot();by_name={v.get('name'):v for v in vrrp};latest=[];ok=True
        for expected in affected:
            current=by_name.get(expected['name']) or {};master=current.get('master');healthy=bool(current.get('healthy'));valid=healthy and master not in {None,'NONE','MULTIPLE'}
            latest.append({'name':expected['name'],'vip':expected.get('vip'),'master':master,'healthy':healthy,'ok':valid})
            if not valid:ok=False
        if ok:return True,round(time.monotonic()-started,1),latest
        time.sleep(POLL_INTERVAL)
    return False,round(time.monotonic()-started,1),latest


def _execute(master,affected):
    result={'ok':False,'master':master,'affected_count':len(affected),'instances':[{'name':x['name'],'vip':x.get('vip'),'old_master':master,'ready_backups':x['ready_backups']} for x in affected],'steps':[],'recovery':{'attempted':False,'service_active':False,'cluster_healthy':False}}
    stopped=False
    try:
        ok,error=_service(master,'stop')
        if not ok:
            result['steps'].append({'step':'stop_master','ok':False,'message':error});result['error']='Keepalived auf dem MASTER konnte nicht gestoppt werden.';return result
        stopped=True;result['steps'].append({'step':'stop_master','ok':True,'message':f'Keepalived auf {master} gestoppt.'})
        moved,seconds,instances=_wait_failover(master,affected);result['failover']={'ok':moved,'seconds':seconds,'instances':instances};result['steps'].append({'step':'verify_failover','ok':moved,'message':f'Failover nach {seconds} s verifiziert.' if moved else f'Failover konnte innerhalb von {FAILOVER_TIMEOUT} s nicht vollständig verifiziert werden.'})
        if not moved:result['error']='Nicht alle betroffenen VRRP-Instanzen wurden erfolgreich von einem Backup übernommen.'
    except Exception as e:
        result['error']=f'Unerwarteter Fehler während des Failover-Tests: {e}'
    finally:
        if stopped:
            result['recovery']['attempted']=True
            started_ok,start_error=_service(master,'start');result['steps'].append({'step':'start_master','ok':started_ok,'message':f'Keepalived auf {master} wieder gestartet.' if started_ok else start_error})
            if started_ok:
                active,service_seconds=_wait_service_active(master);result['recovery']['service_active']=active;result['recovery']['service_seconds']=service_seconds;result['steps'].append({'step':'verify_service','ok':active,'message':f'Keepalived auf {master} ist wieder aktiv.' if active else f'Keepalived auf {master} wurde innerhalb von {RECOVERY_TIMEOUT} s nicht wieder als aktiv erkannt.'})
                cluster_ok,recovery_seconds,recovery_instances=_wait_cluster_recovery(affected);result['recovery']['cluster_healthy']=cluster_ok;result['recovery']['seconds']=recovery_seconds;result['recovery']['instances']=recovery_instances;result['steps'].append({'step':'verify_cluster','ok':cluster_ok,'message':f'Cluster nach {recovery_seconds} s wieder gesund.' if cluster_ok else f'Cluster-Erholung innerhalb von {RECOVERY_TIMEOUT} s nicht vollständig verifiziert.'})
            else:
                result['recovery']['error']='Failsafe konnte Keepalived auf dem ursprünglichen MASTER nicht wieder starten.'
        _poll()
    failover_ok=bool((result.get('failover') or {}).get('ok'));recovery=result['recovery'];result['ok']=failover_ok and recovery.get('service_active') and recovery.get('cluster_healthy')
    if result['ok']:result['message']='Automatischer Failover-Test erfolgreich abgeschlossen.'
    elif recovery.get('attempted') and not recovery.get('service_active'):result['message']='Failover-Test fehlgeschlagen; die Wiederherstellung von Keepalived benötigt Aufmerksamkeit.'
    else:result['message']='Failover-Test nicht vollständig erfolgreich; die Failsafe-Wiederherstellung wurde ausgeführt.'
    return result


@bp.get('/api/failover-test/preflight')
def api_preflight():
    if not _auth():return jsonify({'ok':False,'error':'Nicht angemeldet'}),401
    _poll();return jsonify({'ok':True,**failover_preflight()})


@bp.get('/api/failover-test/preflight/<instance_name>')
def api_instance_preflight(instance_name):
    if not _auth():return jsonify({'ok':False,'error':'Nicht angemeldet'}),401
    _poll();nodes,vrrp=_snapshot();instance=next((v for v in vrrp if v.get('name')==instance_name),None)
    if not instance:return jsonify({'ok':False,'error':'VRRP-Instanz nicht gefunden'}),404
    result=_instance_preflight(instance,nodes);return jsonify({'ok':True,**result,'note':'Diese Prüfung ist rein diagnostisch. Es wurde keine Keepalived-Aktion ausgeführt.'})


@bp.post('/api/failover-test/run')
def api_run():
    if not _auth():return jsonify({'ok':False,'error':'Nicht angemeldet'}),401
    if not _core.csrf_ok():return jsonify({'ok':False,'error':'Ungültiges CSRF-Token'}),403
    if request.headers.get('X-Confirm-Failover-Test')!='yes':return jsonify({'ok':False,'error':'Failover-Test muss ausdrücklich bestätigt werden.'}),409
    if not _test_lock.acquire(blocking=False):return jsonify({'ok':False,'error':'Es läuft bereits ein Failover-Test.'}),409
    try:
        _poll();pre=failover_preflight();allowed=[x for x in pre['instances'] if x['allowed']]
        if not allowed:return jsonify({'ok':False,'error':'Aktuell ist keine VRRP-Instanz sicher testbar.','preflight':pre}),409
        if pre['summary']['blocked']:
            return jsonify({'ok':False,'error':'Failover-Test blockiert: Nicht alle VRRP-Instanzen erfüllen den Sicherheits-Preflight.','preflight':pre}),409
        masters=pre['summary']['masters']
        if len(masters)!=1:return jsonify({'ok':False,'error':'Automatischer Test erfordert aktuell genau einen gemeinsamen MASTER für alle testbaren VRRP-Instanzen.','preflight':pre}),409
        master=masters[0];affected=[x for x in allowed if x['master']==master]
        expected=request.headers.get('X-Confirm-Failover-Master','')
        if expected!=master:return jsonify({'ok':False,'error':f'Bestätigung des betroffenen MASTER {master} fehlt oder ist nicht mehr aktuell.','preflight':pre}),409
        return jsonify(_execute(master,affected)),200
    finally:_test_lock.release()


def init_failover_test(core):
    global _core
    _core=core;core.app.register_blueprint(bp)
