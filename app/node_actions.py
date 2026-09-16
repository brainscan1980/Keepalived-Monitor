"""Safety layer for Keepalived start/stop/restart actions.

Keeps the existing action implementation intact, but adds a preflight endpoint
and a server-side guard for actions that can move a VRRP MASTER.
"""
from flask import Blueprint, jsonify, request

bp=Blueprint('node_actions',__name__)
_core=None
_original_action=None


def _auth():return bool(_core.session.get('authenticated'))


def _snapshot():
    with _core.lock:
        return ({k:dict(v) for k,v in (_core.cache.get('nodes') or {}).items()},
                [dict(v) for v in (_core.cache.get('vrrp') or [])])


def _ready_backup(node_name,instance,nodes):
    ready=[]
    for candidate in instance.get('nodes') or []:
        if candidate==node_name:continue
        n=nodes.get(candidate) or {}
        if n.get('online') and n.get('keepalived')=='active' and not (n.get('maintenance') or {}).get('active'):
            ready.append(candidate)
    return ready


def action_risk(name,action):
    nodes,vrrp=_snapshot();node=nodes.get(name)
    if not node:return {'allowed':False,'level':'error','reason':'Node nicht gefunden','master_instances':[],'affected':[]}
    if not node.get('online'):return {'allowed':False,'level':'error','reason':'Node ist nicht erreichbar','master_instances':[],'affected':[]}
    if action=='start':
        return {'allowed':node.get('keepalived')!='active','level':'normal','reason':'Keepalived kann gestartet werden.' if node.get('keepalived')!='active' else 'Keepalived ist bereits aktiv.','master_instances':[],'affected':[]}
    if node.get('keepalived')!='active':return {'allowed':False,'level':'error','reason':'Keepalived ist nicht aktiv.','master_instances':[],'affected':[]}
    affected=[]
    for instance in vrrp:
        if instance.get('master')!=name:continue
        backups=_ready_backup(name,instance,nodes)
        affected.append({'name':instance.get('name'),'vip':instance.get('vip'),'ready_backups':backups})
    if not affected:return {'allowed':True,'level':'normal','reason':'Der Node ist aktuell für keine VRRP-Instanz MASTER.','master_instances':[],'affected':[]}
    unsafe=[x for x in affected if not x['ready_backups']]
    names=[x['name'] for x in affected]
    if unsafe:
        return {'allowed':False,'level':'blocked','reason':'Aktion blockiert: Für mindestens eine MASTER-Instanz ist kein betriebsbereiter Backup-Node verfügbar.','master_instances':names,'affected':affected}
    return {'allowed':True,'level':'master','reason':'Die Aktion löst voraussichtlich einen VRRP-Failover aus. Betriebsbereite Backups wurden erkannt.','master_instances':names,'affected':affected}


@bp.get('/api/nodes/<name>/keepalived/preflight/<action>')
def preflight(name,action):
    if not _auth():return jsonify({'ok':False,'error':'Nicht angemeldet'}),401
    if action not in {'start','stop','restart'}:return jsonify({'ok':False,'error':'Aktion nicht erlaubt'}),400
    risk=action_risk(name,action)
    return jsonify({'ok':True,'node':name,'action':action,**risk})


def guarded_action(name,action):
    if action in {'stop','restart'}:
        risk=action_risk(name,action)
        if not risk['allowed']:
            return jsonify({'ok':False,'status':'blocked','error':risk['reason'],'risk':risk}),409
        if risk['level']=='master' and request.headers.get('X-Confirm-Master-Action')!='yes':
            return jsonify({'ok':False,'status':'confirmation_required','error':'MASTER-Aktion muss ausdrücklich bestätigt werden.','risk':risk}),409
    return _original_action(name,action)


def init_node_actions(core):
    global _core,_original_action
    _core=core
    core.app.register_blueprint(bp)
    _original_action=core.app.view_functions.get('keepalived_action')
    if _original_action:core.app.view_functions['keepalived_action']=guarded_action
