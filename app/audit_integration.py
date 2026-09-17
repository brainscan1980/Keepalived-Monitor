"""Audit wrappers for core administrator actions that live in app.py."""
from flask import request

_core=None
_original_maintenance=None
_original_settings=None

def _audit(action,target,result,details=None):
    try:_core.write_audit(action,target,result,details)
    except Exception:pass

def _response_data(response):
    flask_response,status=response if isinstance(response,tuple) else (response,200)
    try:data=flask_response.get_json() or {}
    except Exception:data={}
    return status,data

def audited_maintenance(name):
    requested=None
    try:requested=bool((request.get_json(silent=True) or {}).get('active'))
    except Exception:pass
    response=_original_maintenance(name);status,data=_response_data(response)
    if status<400 and data.get('ok'):
        info=data.get('maintenance') or {};active=bool(info.get('active',requested));_audit('maintenance.enable' if active else 'maintenance.disable',name,'success',{'active':active})
    else:_audit('maintenance.enable' if requested else 'maintenance.disable',name,'failed',{'error':data.get('error') or f'HTTP {status}'})
    return response

def audited_settings():
    # Nur nicht-sensitive Feldnamen und ausgewählte ungefährliche
    # Werte werden im Audit-Log gespeichert.
    #
    # SMTP-Passwort, Telegram Bot-Token sowie Zielinformationen
    # werden niemals in Audit-Details geschrieben.
    try:
        payload = request.get_json(silent=True) or {}
    except Exception:
        payload = {}

    secret_keys = {
        'smtp_password',
        'telegram_bot_token',
    }

    sensitive_keys = {
        'smtp_host',
        'smtp_username',
        'mail_from',
        'mail_to',
        'telegram_chat_id',
    }

    safe_keys = {
        'mail_enabled',
        'node_down',
        'recovery_mail',
        'failures_before_alert',
        'smtp_port',
        'smtp_security',
        'telegram_enabled',
    }

    changed_fields = sorted(
        k
        for k in payload
        if k not in secret_keys | sensitive_keys
    )

    safe_values = {
        k: payload.get(k)
        for k in safe_keys
        if k in payload
    }

    smtp_password_changed = bool(
        str(payload.get('smtp_password', ''))
    )

    telegram_bot_token_changed = bool(
        str(payload.get('telegram_bot_token', ''))
    )

    response = _original_settings()
    status, data = _response_data(response)

    details = {
        'changed_fields': changed_fields,
        'safe_values': safe_values,
        'smtp_password_changed': smtp_password_changed,
        'telegram_bot_token_changed': telegram_bot_token_changed,
    }

    if status < 400 and data.get('ok'):
        _audit(
            'settings.update',
            'notifications',
            'success',
            details,
        )
    else:
        _audit(
            'settings.update',
            'notifications',
            'failed',
            {
                **details,
                'error': data.get('error') or f'HTTP {status}',
            },
        )

    return response

def init_audit_integration(core):
    global _core,_original_maintenance,_original_settings
    _core=core
    _original_maintenance=core.app.view_functions.get('node_maintenance')
    if _original_maintenance:core.app.view_functions['node_maintenance']=audited_maintenance
    _original_settings=core.app.view_functions.get('update_settings')
    if _original_settings:core.app.view_functions['update_settings']=audited_settings
