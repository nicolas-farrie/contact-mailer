"""Journal d'audit (Tier 2) — helper d'écriture + purge de rétention.

Traçabilité sécurité & données personnelles (« qui a fait quoi »), PAS un suivi
d'activité. Best-effort : une écriture d'audit qui échoue ne doit JAMAIS casser
l'action métier (login, etc.) → try/except + rollback.

IP : loggée seulement si le toggle admin `audit_log_ip_enabled` est actif (l'IP est
une donnée perso). Derrière nginx, on lit X-Forwarded-For.
"""
import logging
from datetime import timedelta

from flask import request, has_request_context
from flask_login import current_user

from models import db, AuditLog, utcnow
from helpers import get_setting


def _client_ip():
    if not has_request_context():
        return None
    xff = request.headers.get('X-Forwarded-For', '')
    if xff:
        return xff.split(',')[0].strip()[:64]
    return (request.remote_addr or '')[:64] or None


def audit(action, *, user=None, username=None, target_type=None, target_id=None, **details):
    """Enregistre une entrée d'audit. `user`/`username` explicites priment ; sinon on
    prend `current_user` s'il est authentifié (utile hors login). Best-effort."""
    try:
        if user is None:
            try:
                if getattr(current_user, 'is_authenticated', False):
                    user = current_user
            except Exception:
                user = None
        uid = user.id if user is not None else None
        uname = username or (user.username if user is not None else None)
        ip = _client_ip() if get_setting('audit_log_ip_enabled', '1') != '0' else None
        entry = AuditLog(
            user_id=uid, username=uname, action=action,
            target_type=target_type,
            target_id=(str(target_id) if target_id is not None else None),
            details=(details or None), ip=ip,
        )
        db.session.add(entry)
        db.session.commit()
    except Exception:
        db.session.rollback()
        logging.exception('audit(%s) échoué', action)


def purge_old(months=12):
    """Supprime les entrées plus vieilles que `months` mois (rétention RGPD)."""
    cutoff = utcnow() - timedelta(days=int(months) * 30)
    n = AuditLog.query.filter(AuditLog.ts < cutoff).delete(synchronize_session=False)
    db.session.commit()
    return n


def last_logins():
    """{user_id: dernière connexion réussie} — pour l'affichage dans la liste users."""
    rows = (db.session.query(AuditLog.user_id, db.func.max(AuditLog.ts))
            .filter(AuditLog.action == 'login', AuditLog.user_id.isnot(None))
            .group_by(AuditLog.user_id).all())
    return {uid: ts for uid, ts in rows}
