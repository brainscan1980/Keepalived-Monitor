"""Audit wrappers for core administrator actions that live in app.py."""
from flask import request

_core=None
_original_maintenance=None


def _audit(action,target,result,details=None):
    try:_core.write_audit(action,target,result,details)
    except Exception:pass


def audited_maintenance(name):
    requested=None
    try:
        payload=request.get_json(silent=True) or {};requested=bool(payload.get('active'))
    except Exception:pass
    response=_original_maintenance(name)
    flask_response,status=response if isinstance(response,tuple) else (response,200)
    try:data=flask_response.get_json() or {}
    except Exception:data={}
    if status<400 and data.get('ok'):
        info=data.get('maintenance') or {};active=bool(info.get('active',requested));_audit('maintenance.enable' if active else 'maintenance.disable',name,'success',{'active':active})
    else:_audit('maintenance.enable' if requested else 'maintenance.disable',name,'failed',{'error':data.get('error') or f'HTTP {status}'})
    return response


def init_audit_integration(core):
    global _core,_original_maintenance
    _core=core
    _original_maintenance=core.app.view_functions.get('node_maintenance')
    if _original_maintenance:core.app.view_functions['node_maintenance']=audited_maintenance
