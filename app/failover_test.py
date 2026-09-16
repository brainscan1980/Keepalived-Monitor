"""Preflight layer for controlled automated VRRP failover tests.

Stage 1 is deliberately diagnostic only: it never changes Keepalived state.
"""
from flask import Blueprint, jsonify

bp=Blueprint('failover_test',__name__)
_core=None


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
    name=instance.get('name')
    master=instance.get('master')
    members=list(instance.get('nodes') or [])
    result={
        'name':name,
        'vip':instance.get('vip'),
        'master':master,
        'members':members,
        'ready_backups':[],
        'blocked_reasons':[],
        'allowed':False,
    }

    if not members:
        result['blocked_reasons'].append('Keine Nodes für diese VRRP-Instanz konfiguriert.')
        return result
    if master in {None,'NONE','MULTIPLE'}:
        result['blocked_reasons'].append('Es gibt aktuell keinen eindeutig ermittelten MASTER.')
        return result
    if master not in members:
        result['blocked_reasons'].append('Der aktuelle MASTER gehört nicht zur konfigurierten VRRP-Instanz.')
        return result

    master_node=nodes.get(master) or {}
    if not master_node.get('online'):
        result['blocked_reasons'].append(f'MASTER {master} ist nicht erreichbar.')
    elif master_node.get('keepalived')!='active':
        result['blocked_reasons'].append(f'Keepalived auf MASTER {master} ist nicht aktiv.')
    elif _maintenance(master_node):
        result['blocked_reasons'].append(f'MASTER {master} befindet sich im Wartungsmodus.')

    for candidate in members:
        if candidate==master:
            continue
        node=nodes.get(candidate) or {}
        if _ready(node):
            result['ready_backups'].append(candidate)

    if not result['ready_backups']:
        result['blocked_reasons'].append('Kein betriebsbereiter Backup-Node verfügbar.')

    result['allowed']=not result['blocked_reasons']
    return result


def failover_preflight():
    nodes,vrrp=_snapshot()
    instances=[_instance_preflight(v,nodes) for v in vrrp]
    allowed=[x for x in instances if x['allowed']]
    blocked=[x for x in instances if not x['allowed']]
    masters={x['master'] for x in allowed if x.get('master') not in {None,'NONE','MULTIPLE'}}
    return {
        'safe_to_test':bool(allowed),
        'instances':instances,
        'summary':{
            'total':len(instances),
            'testable':len(allowed),
            'blocked':len(blocked),
            'masters':sorted(masters),
        },
        'note':'Diese Prüfung ist rein diagnostisch. Es wurde keine Keepalived-Aktion ausgeführt.',
    }


@bp.get('/api/failover-test/preflight')
def api_preflight():
    if not _auth():
        return jsonify({'ok':False,'error':'Nicht angemeldet'}),401
    try:
        _core.poll()
    except Exception:
        pass
    return jsonify({'ok':True,**failover_preflight()})


@bp.get('/api/failover-test/preflight/<instance_name>')
def api_instance_preflight(instance_name):
    if not _auth():
        return jsonify({'ok':False,'error':'Nicht angemeldet'}),401
    try:
        _core.poll()
    except Exception:
        pass
    nodes,vrrp=_snapshot()
    instance=next((v for v in vrrp if v.get('name')==instance_name),None)
    if not instance:
        return jsonify({'ok':False,'error':'VRRP-Instanz nicht gefunden'}),404
    result=_instance_preflight(instance,nodes)
    return jsonify({'ok':True,**result,'note':'Diese Prüfung ist rein diagnostisch. Es wurde keine Keepalived-Aktion ausgeführt.'})


def init_failover_test(core):
    global _core
    _core=core
    core.app.register_blueprint(bp)
