"""Persistent audit log for administrator-triggered actions."""
import json, sqlite3
from datetime import datetime, timezone
from flask import Blueprint, jsonify, request, render_template
bp=Blueprint('audit_log',__name__);_core=None
def _auth():return bool(_core.session.get('authenticated'))
def _connect():
    con=sqlite3.connect(_core.DB,timeout=10);con.row_factory=sqlite3.Row;return con
def _init_db():
    with _connect() as con:
        con.execute("CREATE TABLE IF NOT EXISTS audit_log (id INTEGER PRIMARY KEY AUTOINCREMENT,ts TEXT NOT NULL,action TEXT NOT NULL,target TEXT NOT NULL DEFAULT '',result TEXT NOT NULL,details TEXT NOT NULL DEFAULT '',remote_addr TEXT NOT NULL DEFAULT '')");con.execute('CREATE INDEX IF NOT EXISTS idx_audit_log_ts ON audit_log(ts DESC)');con.execute('CREATE INDEX IF NOT EXISTS idx_audit_log_action ON audit_log(action)');con.execute('CREATE INDEX IF NOT EXISTS idx_audit_log_result ON audit_log(result)')
def _client_ip():
    try:return str(request.remote_addr or '')
    except RuntimeError:return ''
def write_audit(action,target='',result='success',details=None,remote_addr=None):
    try:
        action=str(action or '').strip()[:80];target=str(target or '').strip()[:160];result=str(result or 'unknown').strip().lower()[:20]
        if result not in {'success','failed','blocked','warning'}:result='warning'
        details=json.dumps(details,ensure_ascii=False,separators=(',',':')) if isinstance(details,(dict,list)) else str(details or '');details=details[:8000];ip=_client_ip() if remote_addr is None else str(remote_addr or '');ts=datetime.now(timezone.utc).isoformat(timespec='seconds')
        with _connect() as con:return con.execute('INSERT INTO audit_log(ts,action,target,result,details,remote_addr) VALUES(?,?,?,?,?,?)',(ts,action,target,result,details,ip[:80])).lastrowid
    except Exception:return None
def _decode_details(value):
    if not value:return ''
    try:return json.loads(value)
    except Exception:return value
def _row(row):return {'id':row['id'],'ts':row['ts'],'action':row['action'],'target':row['target'],'result':row['result'],'details':_decode_details(row['details']),'remote_addr':row['remote_addr']}
@bp.get('/audit')
def audit_page():
    if not _auth():return _core.redirect(_core.url_for('login',next=request.path))
    return render_template('audit.html',nodes=_core.cfg().get('nodes',[]))
@bp.get('/api/audit')
def api_audit():
    if not _auth():return jsonify({'ok':False,'error':'Nicht angemeldet'}),401
    try:page=max(1,int(request.args.get('page','1')))
    except Exception:page=1
    try:per_page=int(request.args.get('per_page','20'))
    except Exception:per_page=20
    if per_page not in {10,20,50,100}:per_page=20
    action=str(request.args.get('action','')).strip()[:80];result=str(request.args.get('result','')).strip().lower()[:20];where=[];params=[]
    if action:where.append('action=?');params.append(action)
    if result:where.append('result=?');params.append(result)
    sql_where=(' WHERE '+' AND '.join(where)) if where else ''
    with _connect() as con:
        total=con.execute('SELECT COUNT(*) FROM audit_log'+sql_where,params).fetchone()[0];pages=max(1,(total+per_page-1)//per_page);page=min(page,pages);rows=con.execute('SELECT id,ts,action,target,result,details,remote_addr FROM audit_log'+sql_where+' ORDER BY id DESC LIMIT ? OFFSET ?',params+[per_page,(page-1)*per_page]).fetchall();actions=[r[0] for r in con.execute('SELECT DISTINCT action FROM audit_log ORDER BY action').fetchall()]
    return jsonify({'ok':True,'entries':[_row(r) for r in rows],'pagination':{'page':page,'per_page':per_page,'total':total,'pages':pages},'filters':{'actions':actions,'results':['success','failed','blocked','warning']}})
def init_audit_log(core):
    global _core
    _core=core;_init_db();core.write_audit=write_audit;core.app.register_blueprint(bp)
