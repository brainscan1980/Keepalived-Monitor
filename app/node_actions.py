"""Safety and verification layer for Keepalived node actions."""
import time
from flask import Blueprint, jsonify, request

bp=Blueprint('node_actions',__name__)
_core=None
_original_action=None
VERIFY_TIMEOUT=18
VERIFY_INTERVAL=2


def _auth():return bool(_core.session.get('authenticated'))

def _audit(action,target,result,details=None):
    try:_core.write_audit(action,target,result,details)
    except Exception:pass


def _snapshot():
    with _core.lock:
        return ({k:dict(v) for k,v in (_core.cache.get('nodes') or {}).items()},[dict(v) for v in (_core.cache.get('vrrp') or [])])


def _ready_backup(node_name,instance,nodes):
    ready=[]
    for candidate in instance.get('nodes') or []:
        if candidate==node_name:continue
        n=nodes.get(candidate) or {}
        if n.get('online') and n.get('keepalived')=='active' and not (n.get('maintenance') or {}).get('active'):ready.append(candidate)
    return ready


def action_risk(name,action):
    nodes,vrrp=_snapshot();node=nodes.get(name)
    if not node:return {'allowed':False,'level':'error','reason':'Node nicht gefunden','master_instances':[],'affected':[]}
    if not node.get('online'):return {'allowed':False,'level':'error','reason':'Node ist nicht erreichbar','master_instances':[],'affected':[]}
    if action=='start':return {'allowed':node.get('keepalived')!='active','level':'normal','reason':'Keepalived kann gestartet werden.' if node.get('keepalived')!='active' else 'Keepalived ist bereits aktiv.','master_instances':[],'affected':[]}
    if node.get('keepalived')!='active':return {'allowed':False,'level':'error','reason':'Keepalived ist nicht aktiv.','master_instances':[],'affected':[]}
    affected=[]
    for instance in vrrp:
        if instance.get('master')!=name:continue
        affected.append({'name':instance.get('name'),'vip':instance.get('vip'),'old_master':name,'ready_backups':_ready_backup(name,instance,nodes)})
    if not affected:return {'allowed':True,'level':'normal','reason':'Der Node ist aktuell für keine VRRP-Instanz MASTER.','master_instances':[],'affected':[]}
    unsafe=[x for x in affected if not x['ready_backups']];names=[x['name'] for x in affected]
    if unsafe:return {'allowed':False,'level':'blocked','reason':'Aktion blockiert: Für mindestens eine MASTER-Instanz ist kein betriebsbereiter Backup-Node verfügbar.','master_instances':names,'affected':affected}
    return {'allowed':True,'level':'master','reason':'Die Aktion löst voraussichtlich einen VRRP-Failover aus. Betriebsbereite Backups wurden erkannt.','master_instances':names,'affected':affected}


def _verify_failover(name,action,affected):
    if not affected:return {'required':False,'ok':True,'timed_out':False,'seconds':0,'instances':[],'service_recovered':None}
    started=time.monotonic();deadline=started+VERIFY_TIMEOUT;latest=[];service_recovered=None
    while True:
        try:_core.poll()
        except Exception:pass
        nodes,vrrp=_snapshot();by_name={v.get('name'):v for v in vrrp};latest=[];all_moved=True
        for expected in affected:
            current=by_name.get(expected.get('name')) or {};master=current.get('master');healthy=bool(current.get('healthy'));moved=healthy and master not in {None,'NONE','MULTIPLE',name}
            latest.append({'name':expected.get('name'),'vip':expected.get('vip'),'old_master':name,'new_master':master,'healthy':healthy,'moved':moved})
            if not moved:all_moved=False
        node=nodes.get(name) or {};service_recovered=node.get('online') and node.get('keepalived')=='active'
        if action=='restart' and not all_moved:
            try:
                import sqlite3
                since_iso=__import__('datetime').datetime.now()-__import__('datetime').timedelta(seconds=VERIFY_TIMEOUT+5)
                with sqlite3.connect(_core.DB) as c:rows=c.execute('SELECT name,old_master,new_master FROM events WHERE ts>=?',(since_iso.isoformat(timespec='seconds'),)).fetchall()
                moved_names={r[0] for r in rows if r[1]==name and r[2] not in {None,'NONE',name,'MULTIPLE'}}
                for item in latest:
                    if item['name'] in moved_names:item['moved']=True
                all_moved=all(x['moved'] for x in latest)
            except Exception:pass
        if all_moved and (action!='restart' or service_recovered):break
        if time.monotonic()>=deadline:break
        time.sleep(VERIFY_INTERVAL)
    elapsed=round(time.monotonic()-started,1);ok=all(x['moved'] for x in latest) and (action!='restart' or bool(service_recovered))
    return {'required':True,'ok':ok,'timed_out':not ok and elapsed>=VERIFY_TIMEOUT,'seconds':elapsed,'instances':latest,'service_recovered':bool(service_recovered) if action=='restart' else None}


@bp.get('/api/nodes/<name>/keepalived/preflight/<action>')
def preflight(name,action):
    if not _auth():return jsonify({'ok':False,'error':'Nicht angemeldet'}),401
    if action not in {'start','stop','restart'}:return jsonify({'ok':False,'error':'Aktion nicht erlaubt'}),400
    return jsonify({'ok':True,'node':name,'action':action,**action_risk(name,action)})


def guarded_action(name,action):
    risk=None
    if action in {'stop','restart'}:
        risk=action_risk(name,action)
        if not risk['allowed']:
            _audit(f'keepalived.{action}',name,'blocked',{'reason':risk['reason'],'risk':risk.get('level'),'instances':risk.get('master_instances',[])})
            return jsonify({'ok':False,'status':'blocked','error':risk['reason'],'risk':risk}),409
        if risk['level']=='master' and request.headers.get('X-Confirm-Master-Action')!='yes':return jsonify({'ok':False,'status':'confirmation_required','error':'MASTER-Aktion muss ausdrücklich bestätigt werden.','risk':risk}),409
    response=_original_action(name,action)
    flask_response,status=response if isinstance(response,tuple) else (response,200)
    try:data=flask_response.get_json() or {}
    except Exception:data={}
    if not risk or risk.get('level')!='master':
        _audit(f'keepalived.{action}',name,'success' if status<400 and data.get('ok') else 'failed',{'status':data.get('status'),'error':data.get('error') or ''})
        return response
    if status>=400 or not data.get('ok'):
        _audit(f'keepalived.{action}',name,'failed',{'status':data.get('status'),'error':data.get('error') or 'Keepalived-Aktion fehlgeschlagen.','instances':risk.get('master_instances',[])})
        return response
    verification=_verify_failover(name,action,risk.get('affected') or [])
    data['verification']=verification
    if verification['ok']:data['message']='Failover erfolgreich verifiziert.'
    else:data['message']='Keepalived-Aktion wurde ausgeführt, die Failover-Nachkontrolle war jedoch nicht vollständig erfolgreich.'
    _audit(f'keepalived.{action}',name,'success' if verification['ok'] else 'warning',{'status':data.get('status'),'master_action':True,'instances':risk.get('master_instances',[]),'verification':verification})
    return jsonify(data),200


def init_node_actions(core):
    global _core,_original_action
    _core=core;core.app.register_blueprint(bp);_original_action=core.app.view_functions.get('keepalived_action')
    if _original_action:core.app.view_functions['keepalived_action']=guarded_action
