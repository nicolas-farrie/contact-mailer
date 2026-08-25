"""Moteur de filtres avancés Contacts — P1 : champs STANDARD (colonnes typées) + pseudo-champs.

Une recherche avancée = liste de conditions {field, op, value} combinées en ET.
Métadata (types → opérateurs) dérivée du registre `fields.py`. Les champs perso (JSON)
et l'UI arrivent en phases ultérieures — cf. doc-travail/2026-08-22-filtres-avances-plan.md.

Portage Postgres : le SQL spécifique SQLite est marqué `# [PG-PORT]`. En P1 il n'y en a
aucun (filtres ORM 100% portables) ; ils apparaîtront en P2 (accès JSON des champs perso).
Moteur actif détectable via `db.engine.dialect.name` ('sqlite' | 'postgresql').
"""
from datetime import datetime, timedelta

from models import db, Contact, Liste
import fields

# --- Opérateurs autorisés par type (métadata, sert aussi à l'UI en P3) ---
_TEXT_OPS = ('contains', 'equals', 'starts_with', 'is_empty', 'is_not_empty')
OPERATORS_BY_TYPE = {
    'text': _TEXT_OPS, 'email': _TEXT_OPS, 'tel': _TEXT_OPS, 'textarea': _TEXT_OPS,
    'select': ('is', 'is_not', 'is_empty', 'is_not_empty'),
    'number': ('eq', 'ne', 'lt', 'gt', 'between', 'is_empty', 'is_not_empty'),
    'date': ('before', 'after', 'between', 'is_empty', 'is_not_empty'),
    'checkbox': ('is_true', 'is_false'),
}

# --- Pseudo-champs : pas une simple colonne, filtrage dédié ---
PSEUDO_FIELDS = {
    'liste':      {'label': 'Liste (appartenance)', 'type': 'liste',
                   'operators': ('is_member', 'is_not_member')},
    'statut':     {'label': 'Statut', 'type': 'statut', 'operators': ('is',)},
    'created_at': {'label': "Date d'ajout", 'type': 'date',
                   'operators': OPERATORS_BY_TYPE['date']},
}


def _like_escape(s):
    """Échappe les jokers LIKE (%/_) dans une saisie utilisateur."""
    return s.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')


def _empty(col):
    return db.or_(col.is_(None), col == '')


def _parse_date(s):
    if not s:
        return None
    for fmt in ('%Y-%m-%d', '%d/%m/%Y'):
        try:
            return datetime.strptime(s.strip(), fmt)
        except (ValueError, AttributeError):
            pass
    return None


def _date_predicate(col, op, value):
    if op == 'is_empty':
        return col.is_(None)
    if op == 'is_not_empty':
        return col.isnot(None)
    if op == 'before':
        d = _parse_date(value)
        return col < d if d else None
    if op == 'after':
        d = _parse_date(value)
        return col >= d if d else None       # >= début de la journée choisie
    if op == 'between':
        lo, hi = value if isinstance(value, (list, tuple)) else (None, None)
        lo, hi = _parse_date(lo), _parse_date(hi)
        conds = []
        if lo:
            conds.append(col >= lo)
        if hi:
            conds.append(col < hi + timedelta(days=1))   # fin de journée incluse
        return db.and_(*conds) if conds else None
    return None


def _number_predicate(col, op, value):
    # P1 : aucune colonne standard n'est numérique ; utile surtout en P2 (champs perso).
    if op == 'is_empty':
        return _empty(col)
    if op == 'is_not_empty':
        return db.not_(_empty(col))
    try:
        if op == 'between':
            lo, hi = value if isinstance(value, (list, tuple)) else (None, None)
            conds = []
            if lo not in (None, ''):
                conds.append(col >= float(lo))
            if hi not in (None, ''):
                conds.append(col <= float(hi))
            return db.and_(*conds) if conds else None
        v = float(value)
    except (TypeError, ValueError):
        return None
    return {'eq': col == v, 'ne': col != v, 'lt': col < v, 'gt': col > v}.get(op)


def _standard_type(field_key):
    f = fields.field_map(include_custom=False).get(field_key)
    return f.type if f else None


def build_predicate(field_key, op, value):
    """Condition → expression SQLAlchemy (champs STANDARD + pseudo-champs).
    Renvoie None si champ inconnu (→ champ perso, P2), opérateur non géré, ou valeur
    invalide (la condition est alors ignorée par apply_conditions)."""
    # --- pseudo-champs ---
    if field_key == 'liste':
        try:
            lid = int(value)
        except (TypeError, ValueError):
            return None
        member = Contact.listes.any(Liste.id == lid)
        return member if op == 'is_member' else db.not_(member)
    if field_key == 'statut':
        if value == 'abonne':
            return db.and_(Contact.is_unsubscribed == False, Contact.has_bounced == False)
        if value == 'desabonne':
            return Contact.is_unsubscribed == True
        if value == 'bounce':
            return Contact.has_bounced == True
        return None
    if field_key == 'created_at':
        return _date_predicate(Contact.created_at, op, value)

    # --- colonnes standard ---
    col = getattr(Contact, field_key, None)
    ftype = _standard_type(field_key)
    if col is None or ftype is None:
        return None   # champ perso / inconnu → P2

    if op == 'is_empty':
        return _empty(col)
    if op == 'is_not_empty':
        return db.not_(_empty(col))

    if ftype in ('text', 'email', 'tel', 'textarea'):
        if value in (None, ''):
            return None
        pat = _like_escape(value)
        if op == 'contains':
            return col.ilike(f'%{pat}%', escape='\\')
        if op == 'equals':
            return col.ilike(pat, escape='\\')
        if op == 'starts_with':
            return col.ilike(f'{pat}%', escape='\\')
    elif ftype == 'select':
        if op == 'is':
            return col == value
        if op == 'is_not':
            return db.or_(col != value, col.is_(None))
    elif ftype == 'checkbox':
        if op == 'is_true':
            return col == True
        if op == 'is_false':
            return db.or_(col == False, col.is_(None))
    elif ftype == 'date':
        return _date_predicate(col, op, value)
    elif ftype == 'number':
        return _number_predicate(col, op, value)
    return None


def parse_conditions(args):
    """Extrait les conditions des paramètres `af<i>.field/op/val/val2` (GET ou POST).
    Format URL rejouable (fondation des segments nommés). Ignore les entrées incomplètes."""
    groups = {}
    for key in args.keys():
        if not key.startswith('af') or '.' not in key:
            continue
        idx, _, part = key[2:].partition('.')
        if idx.isdigit():
            groups.setdefault(idx, {})[part] = args.get(key)
    out = []
    for idx in sorted(groups, key=int):
        g = groups[idx]
        field = (g.get('field') or '').strip()
        op = (g.get('op') or '').strip()
        if not field or not op:
            continue
        value = (g.get('val2') and (g.get('val'), g.get('val2'))) if op == 'between' else g.get('val')
        out.append({'field': field, 'op': op, 'value': value})
    return out


def apply_conditions(query, conditions):
    """Applique les conditions (ET) à une query Contact. Les conditions invalides
    (prédicat None) sont ignorées silencieusement."""
    for c in conditions:
        pred = build_predicate(c['field'], c['op'], c.get('value'))
        if pred is not None:
            query = query.filter(pred)
    return query
