"""Moteur de filtres avancés Contacts — P1 : champs STANDARD (colonnes typées) + pseudo-champs.

Une recherche avancée = liste de conditions {field, op, value} combinées en ET.
Métadata (types → opérateurs) dérivée du registre `fields.py`. Les champs perso (JSON)
et l'UI arrivent en phases ultérieures — cf. doc-travail/2026-08-22-filtres-avances-plan.md.

Portage Postgres : le SQL spécifique SQLite est marqué `# [PG-PORT]`. En P1 il n'y en a
aucun (filtres ORM 100% portables) ; ils apparaîtront en P2 (accès JSON des champs perso).
Moteur actif détectable via `db.engine.dialect.name` ('sqlite' | 'postgresql').
"""
from datetime import datetime, timedelta

from sqlalchemy import func, cast, Float

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

# Types pseudo-champs (filtrage dédié, cf. build_predicate).
OPERATORS_BY_TYPE['liste'] = ('is_member', 'is_not_member')
OPERATORS_BY_TYPE['statut'] = ('is',)

# Libellés FR des opérateurs (pour l'UI du constructeur de filtres, P3).
OP_LABELS = {
    'contains': 'contient', 'equals': 'égal à', 'starts_with': 'commence par',
    'is_empty': 'est vide', 'is_not_empty': 'non vide',
    'is': 'est', 'is_not': "n'est pas",
    'eq': '=', 'ne': '≠', 'lt': '<', 'gt': '>', 'between': 'entre',
    'before': 'avant le', 'after': 'à partir du',
    'is_true': 'oui', 'is_false': 'non',
    'is_member': 'membre de', 'is_not_member': 'pas membre de',
}


def filter_ui_metadata():
    """Métadata pour le constructeur de filtres (P3) : champs filtrables (clé, libellé,
    type, groupe, options pour les select) + opérateurs par type avec libellés.
    Consommé tel quel par le JS de l'UI (sérialisé en JSON)."""
    from helpers import listes_sorted
    fmeta = []
    for f in fields.contact_fields(include_custom=True):   # inclut les champs perso (P2)
        e = {'key': f.key, 'label': f.label, 'type': f.type, 'group': f.group}
        if f.type == 'select':
            e['options'] = list(fields.field_options(f))
        fmeta.append(e)
    # Pseudo-champs (groupe « Ciblage »)
    fmeta.append({'key': 'liste', 'label': 'Liste (appartenance)', 'type': 'liste',
                  'group': 'Ciblage', 'options': [{'value': l.id, 'label': l.nom} for l in listes_sorted()]})
    fmeta.append({'key': 'statut', 'label': 'Statut', 'type': 'statut', 'group': 'Ciblage',
                  'options': [{'value': 'abonne', 'label': 'Abonné'},
                              {'value': 'desabonne', 'label': 'Désabonné'},
                              {'value': 'bounce', 'label': 'Bounce'}]})
    fmeta.append({'key': 'created_at', 'label': "Date d'ajout", 'type': 'date', 'group': 'Ciblage'})

    operators = {t: [{'op': o, 'label': OP_LABELS.get(o, o)} for o in ops]
                 for t, ops in OPERATORS_BY_TYPE.items()}
    return {'fields': fmeta, 'operators': operators}


def conditions_for_ui(args):
    """Conditions courantes (depuis l'URL) au format plat {field, op, val, val2} pour
    ré-hydrater l'UI au chargement."""
    out = []
    for c in parse_conditions(args):
        v = c['value']
        if isinstance(v, (list, tuple)):
            out.append({'field': c['field'], 'op': c['op'], 'val': v[0], 'val2': v[1]})
        else:
            out.append({'field': c['field'], 'op': c['op'], 'val': v})
    return out


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


# ============ Champs perso (P2) — stockés en JSON dans Contact.custom_fields ============
# Valeurs stockées EN TEXTE même pour number/checkbox (ex. {"circo":"5"}, {"nouvel_elu":"1"}).
# Le « vide » est souvent le JSON null → json_extract renvoie NULL.

# Valeurs considérées « vraies » pour un checkbox (tolérant aux origines d'import).
_TRUTHY = ('1', 'true', 'True', 'TRUE', 'oui', 'Oui', 'OUI', 'on', 'x', 'X', 'vrai', 'Vrai', 'yes')


def _json_value(key):
    """Accès à une valeur de champ perso.
    # [PG-PORT] SQLite `json_extract(custom_fields,'$.key')` → Postgres JSONB
    #           `custom_fields ->> 'key'` (via Contact.custom_fields[key].astext)."""
    return func.json_extract(Contact.custom_fields, '$.' + key)


def _date_text_predicate(jv, op, value):
    """Champ perso date stocké en texte ISO ('YYYY-MM-DD…') → comparaison lexicale valide."""
    if op == 'before':
        return jv < value if value else None
    if op == 'after':
        return jv >= value if value else None
    if op == 'between':
        lo, hi = value if isinstance(value, (list, tuple)) else (None, None)
        conds = []
        if lo:
            conds.append(jv >= lo)
        if hi:
            conds.append(jv <= hi)
        return db.and_(*conds) if conds else None
    return None


def custom_field_predicate(key, ftype, op, value):
    """Prédicat sur un champ perso (JSON). SEUL point qui touche au stockage JSON →
    si migration EAV/Postgres, on ne réécrit QUE cette fonction (cf. décision archi)."""
    jv = _json_value(key)
    if op == 'is_empty':
        return db.or_(jv.is_(None), jv == '')
    if op == 'is_not_empty':
        return db.and_(jv.isnot(None), jv != '')

    if ftype == 'checkbox':
        if op == 'is_true':
            return jv.in_(_TRUTHY)
        if op == 'is_false':
            return db.or_(jv.is_(None), jv.notin_(_TRUTHY))
        return None

    if ftype == 'number':
        num = cast(jv, Float)   # texte → numérique (sinon comparaison lexicale fausse). [PG-PORT] CAST identique.
        if op in ('eq', 'ne', 'lt', 'gt'):
            try:
                v = float(value)
            except (TypeError, ValueError):
                return None
            return {'eq': num == v, 'ne': num != v, 'lt': num < v, 'gt': num > v}[op]
        if op == 'between':
            lo, hi = value if isinstance(value, (list, tuple)) else (None, None)
            conds = []
            try:
                if lo not in (None, ''):
                    conds.append(num >= float(lo))
                if hi not in (None, ''):
                    conds.append(num <= float(hi))
            except (TypeError, ValueError):
                return None
            return db.and_(*conds) if conds else None
        return None

    if ftype == 'date':
        return _date_text_predicate(jv, op, value)

    # text / select / autres : opérateurs texte sur json_extract
    if value in (None, ''):
        return None
    pat = _like_escape(str(value))
    if op == 'contains':
        return jv.ilike(f'%{pat}%', escape='\\')
    if op == 'equals':
        return jv.ilike(pat, escape='\\')
    if op == 'starts_with':
        return jv.ilike(f'{pat}%', escape='\\')
    if op == 'is':
        return jv == value
    if op == 'is_not':
        return db.or_(jv != value, jv.is_(None))
    return None


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
        # --- champ perso (P2) : JSON, derrière l'abstraction custom_field_predicate ---
        fdef = fields.field_map().get(field_key)   # include_custom=True
        if fdef is not None and fdef.source == 'custom':
            return custom_field_predicate(field_key, fdef.type, op, value)
        return None   # champ inconnu

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


def apply_conditions(query, conditions, join='and'):
    """Applique les conditions à une query Contact, combinées en ET (défaut) ou en OU
    (`join='or'`). Les conditions invalides (prédicat None) sont ignorées.
    Note : le bloc avancé reste ANDé avec les filtres simples de la page ; `join` ne
    joue qu'ENTRE les conditions avancées → (filtres simples) ET (adv1 OU adv2 …)."""
    preds = [p for p in (build_predicate(c['field'], c['op'], c.get('value')) for c in conditions)
             if p is not None]
    if not preds:
        return query
    return query.filter(db.or_(*preds) if join == 'or' else db.and_(*preds))
