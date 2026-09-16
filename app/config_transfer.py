"""Safe configuration export/import with validation and preview."""
import copy, io, os, tempfile
from datetime import datetime
from flask import Blueprint, jsonify, request, send_file
import yaml

bp=Blueprint('config_transfer',__name__)
_core=None


def _auth():return bool(_core.session.get('authenticated'))
def _csrf():return _core.csrf_ok()
def _current():return _core.cfg()

def _validate(data):
    errors=[];warnings=[]
    if not isinstance(data,dict):return ['Die Konfiguration muss ein YAML/JSON-Objekt sein.'],[]
    nodes=data.get('nodes');vrrp=data.get('vrrp')
    if not isinstance(nodes,list) or not nodes:errors.append('Mindestens ein Node ist erforderlich.');nodes=[]
    if not isinstance(vrrp,list) or not vrrp:errors.append('Mindestens eine VRRP-Instanz ist erforderlich.');vrrp=[]
    names=[]
    for i,n in enumerate(nodes,1):
        if not isinstance(n,dict):errors.append(f'Node {i}: ungültiger Eintrag.');continue
        name=str(n.get('name','')).strip();host=str(n.get('host','')).strip();user=str(n.get('user','')).strip()
        if not name:errors.append(f'Node {i}: Name fehlt.')
        if not host:errors.append(f'Node {i}: Host fehlt.')
        if not user:errors.append(f'Node {i}: SSH-Benutzer fehlt.')
        if name in names:errors.append(f'Doppelter Node-Name: {name}')
        names.append(name)
    vnames=[]
    for i,v in enumerate(vrrp,1):
        if not isinstance(v,dict):errors.append(f'VRRP {i}: ungültiger Eintrag.');continue
        name=str(v.get('name','')).strip();vip=str(v.get('vip','')).strip();members=v.get('nodes')
        if not name:errors.append(f'VRRP {i}: Name fehlt.')
        if not vip:errors.append(f'VRRP {i}: VIP fehlt.')
        if name in vnames:errors.append(f'Doppelte VRRP-Instanz: {name}')
        vnames.append(name)
        if not isinstance(members,list) or not members:errors.append(f'{name or "VRRP"}: keine Nodes zugeordnet.')
        else:
            unknown=[x for x in members if x not in names]
            if unknown:errors.append(f'{name}: unbekannte Nodes: {", ".join(map(str,unknown))}')
            if len(members)<2:warnings.append(f'{name}: nur ein Node konfiguriert – keine Redundanz.')
    try:
        refresh=int(data.get('refresh_seconds',5))
        if refresh<2 or refresh>300:errors.append('refresh_seconds muss zwischen 2 und 300 liegen.')
    except Exception:errors.append('refresh_seconds ist ungültig.')
    ssh=data.get('ssh',{})
    if ssh is not None and not isinstance(ssh,dict):errors.append('ssh muss ein Objekt sein.')
    return errors,warnings

def _summary(data):return {'nodes':len(data.get('nodes') or []),'vrrp':len(data.get('vrrp') or []),'refresh_seconds':data.get('refresh_seconds',5)}
def _diff(old,new):
    old_nodes={x.get('name'):x for x in old.get('nodes',[]) if isinstance(x,dict)};new_nodes={x.get('name'):x for x in new.get('nodes',[]) if isinstance(x,dict)}
    old_v={x.get('name'):x for x in old.get('vrrp',[]) if isinstance(x,dict)};new_v={x.get('name'):x for x in new.get('vrrp',[]) if isinstance(x,dict)}
    return {'nodes':{'added':sorted(set(new_nodes)-set(old_nodes)),'removed':sorted(set(old_nodes)-set(new_nodes)),'changed':sorted(k for k in set(old_nodes)&set(new_nodes) if old_nodes[k]!=new_nodes[k])},'vrrp':{'added':sorted(set(new_v)-set(old_v)),'removed':sorted(set(old_v)-set(new_v)),'changed':sorted(k for k in set(old_v)&set(new_v) if old_v[k]!=new_v[k])},'refresh_changed':old.get('refresh_seconds',5)!=new.get('refresh_seconds',5)}

def _parse_upload():
    f=request.files.get('file')
    if not f:raise ValueError('Keine Konfigurationsdatei ausgewählt.')
    raw=f.read(1024*1024+1)
    if len(raw)>1024*1024:raise ValueError('Datei ist größer als 1 MB.')
    try:text=raw.decode('utf-8')
    except UnicodeDecodeError:raise ValueError('Datei muss UTF-8-kodiert sein.')
    try:data=yaml.safe_load(text)
    except Exception as e:raise ValueError(f'YAML/JSON konnte nicht gelesen werden: {e}')
    return data

@bp.get('/api/config/export')
def export_config():
    if not _auth():return jsonify({'ok':False,'error':'Nicht angemeldet'}),401
    data=copy.deepcopy(_current());payload=yaml.safe_dump(data,allow_unicode=True,sort_keys=False).encode('utf-8');name=f'keepalived-monitor-config-{datetime.now().strftime("%Y%m%d-%H%M%S")}.yml'
    return send_file(io.BytesIO(payload),mimetype='application/x-yaml',as_attachment=True,download_name=name)

@bp.post('/api/config/import/preview')
def preview_import():
    if not _auth():return jsonify({'ok':False,'error':'Nicht angemeldet'}),401
    if not _csrf():return jsonify({'ok':False,'error':'Ungültiges CSRF-Token'}),403
    try:data=_parse_upload();errors,warnings=_validate(data);return jsonify({'ok':not errors,'valid':not errors,'errors':errors,'warnings':warnings,'summary':_summary(data) if isinstance(data,dict) else {},'changes':_diff(_current(),data) if not errors else {}}),200 if not errors else 400
    except ValueError as e:return jsonify({'ok':False,'valid':False,'errors':[str(e)],'warnings':[]}),400

@bp.post('/api/config/import/apply')
def apply_import():
    if not _auth():return jsonify({'ok':False,'error':'Nicht angemeldet'}),401
    if not _csrf():return jsonify({'ok':False,'error':'Ungültiges CSRF-Token'}),403
    if request.headers.get('X-Confirm-Config-Import')!='yes':return jsonify({'ok':False,'error':'Import muss ausdrücklich bestätigt werden.'}),409
    try:
        data=_parse_upload();errors,warnings=_validate(data)
        if errors:return jsonify({'ok':False,'error':'Konfiguration ist ungültig.','errors':errors,'warnings':warnings}),400
        path=_core.CONFIG_FILE;directory=os.path.dirname(path);os.makedirs(directory,exist_ok=True);backup=None
        if os.path.exists(path):
            backup=f'{path}.backup-{datetime.now().strftime("%Y%m%d-%H%M%S")}'
            with open(path,'rb') as src,open(backup,'wb') as dst:dst.write(src.read())
        fd,tmp=tempfile.mkstemp(prefix='.config-import-',suffix='.yml',dir=directory)
        try:
            with os.fdopen(fd,'w',encoding='utf-8') as f:yaml.safe_dump(data,f,allow_unicode=True,sort_keys=False)
            os.chmod(tmp,0o600);os.replace(tmp,path)
        finally:
            if os.path.exists(tmp):os.unlink(tmp)
        try:_core.poll()
        except Exception as e:return jsonify({'ok':True,'warning':f'Konfiguration gespeichert, Status-Aktualisierung fehlgeschlagen: {e}','backup':backup,'summary':_summary(data),'warnings':warnings})
        return jsonify({'ok':True,'message':'Konfiguration erfolgreich importiert und neu geladen.','backup':backup,'summary':_summary(data),'warnings':warnings})
    except ValueError as e:return jsonify({'ok':False,'error':str(e)}),400
    except Exception as e:return jsonify({'ok':False,'error':f'Import fehlgeschlagen: {e}'}),500

def init_config_transfer(core):
    global _core
    _core=core;core.app.register_blueprint(bp)
