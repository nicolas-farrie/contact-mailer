"""Registre des champs de contact — couche présentation / IO.

Source de vérité unique : « quels champs existent, leur clé machine stable
(fieldName), leur libellé affiché (display_name), leur type et leur groupe ».
Pilote le rendu des formulaires, l'affichage de la fiche, et les variables de
fusion des mailings — PAS la logique métier (qui accède aux colonnes en direct :
`contact.email` reste `contact.email`).

Deux origines de champs :
- source='column' : mappé sur une colonne typée de Contact (email, nom…).
- source='custom' : champ défini par l'admin, stocké dans Contact.custom_fields
  (JSON). Chargé dynamiquement depuis la table CustomFieldDefinition (à venir ;
  le chargement est tolérant tant que le modèle/la table n'existent pas).

Convention : `key` = fieldName stable (code, variable de fusion {key}, clé JSON) ;
`label` = display_name affiché (le getter `label()` est le point d'entrée de la
future couche i18n — aujourd'hui il renvoie le libellé français littéral).

Note : les `key` des champs colonne == noms de colonnes actuels de Contact, pour
une intégration en drop-in (le code et to_dict continuent de fonctionner).
"""
from dataclasses import dataclass


# --- Groupes d'affichage (sections du formulaire / de la fiche) ---
GROUP_IDENTITE = 'identite'
GROUP_CONTACT = 'contact'
GROUP_ADRESSE = 'adresse'
GROUP_AUTRES = 'autres'
GROUP_PERSO = 'perso'

GROUP_LABELS = {
    GROUP_IDENTITE: 'Identité',
    GROUP_CONTACT: 'Coordonnées',
    GROUP_ADRESSE: 'Adresse',
    GROUP_AUTRES: 'Autres',
    GROUP_PERSO: 'Champs personnalisés',
}

_GROUP_ORDER = (GROUP_IDENTITE, GROUP_CONTACT, GROUP_ADRESSE, GROUP_AUTRES, GROUP_PERSO)


@dataclass(frozen=True)
class FieldDef:
    key: str                 # fieldName : clé machine stable (code, {merge}, JSON)
    label: str               # display_name : libellé affiché (i18n plus tard)
    type: str = 'text'       # text|email|tel|number|date|select|checkbox|textarea
    group: str = GROUP_AUTRES
    order: int = 0
    source: str = 'column'   # 'column' (colonne Contact) | 'custom' (custom_fields JSON)
    required: bool = False
    unique: bool = False
    options: tuple = ()       # options statiques / fallback (type 'select')
    options_source: str = ''  # clé Setting JSON pour des options éditables (sinon `options`)
    help: str = ''
    width: str = 'full'       # hint layout : 'full' | 'half' | 'third'
    mailing_var: bool = True  # exposé comme variable de fusion {key} ?
    editable: bool = True     # saisi via le formulaire ? (False = champ système, lecture seule)
    default: str = ''         # valeur par défaut (ex: select sans option vide)


# --- Champs « colonne » (miroir des colonnes actuelles de Contact) ---
CONTACT_COLUMN_FIELDS = (
    FieldDef('nom',                'Nom',          group=GROUP_IDENTITE, order=10, required=True, width='half'),
    FieldDef('prenom',             'Prénom',       group=GROUP_IDENTITE, order=20, width='half'),
    FieldDef('civilite',           'Civilité',     type='select', group=GROUP_IDENTITE, order=30, width='half',
             options=('', 'Madame', 'Monsieur', 'Mx', 'Autre'), options_source='choices.civilite',
             help="Formule d'appel affichée dans les mailings (Madame, Monsieur…)."),
    FieldDef('genre',              'Accord de genre', type='select', group=GROUP_IDENTITE, order=40, width='half',
             options=('Féminin', 'Masculin', 'Inclusif'), default='Inclusif',
             help="Sert aux accords dans les mailings — ex. {genre==Féminin:accueillie:accueilli}. « Inclusif » par défaut (évite un masculin implicite). Distinct de la civilité."),
    FieldDef('titre',              'Titre',        group=GROUP_IDENTITE, order=50, width='half'),
    FieldDef('email',              'E-mail',       type='email', group=GROUP_CONTACT, order=10, unique=True, width='half'),
    FieldDef('telephone',          'Téléphone',    type='tel',   group=GROUP_CONTACT, order=20, width='half'),
    FieldDef('organisation',       'Organisation', group=GROUP_CONTACT, order=30),
    FieldDef('adresse_rue',        'Rue',          group=GROUP_ADRESSE, order=10),
    FieldDef('adresse_complement', 'Complément',   group=GROUP_ADRESSE, order=20),
    FieldDef('adresse_cp',         'Code postal',  group=GROUP_ADRESSE, order=30, width='third'),
    FieldDef('adresse_ville',      'Ville',        group=GROUP_ADRESSE, order=40, width='third'),
    FieldDef('adresse_region',     'Région',       group=GROUP_ADRESSE, order=50, width='third'),
    FieldDef('adresse_pays',       'Pays',         group=GROUP_ADRESSE, order=60, width='half'),
    FieldDef('source',             'Source',       group=GROUP_AUTRES, order=10, mailing_var=False, editable=False),
    FieldDef('notes',              'Notes',        type='textarea', group=GROUP_AUTRES, order=20, mailing_var=False),
)

# Clés réservées : interdites pour un champ personnalisé (collisions merge-vars / logique)
RESERVED_KEYS = frozenset(
    {f.key for f in CONTACT_COLUMN_FIELDS}
    | {'id', 'uid', 'listes', 'seafile_password', 'seafile_temp_pwd'}
)


def _custom_field_defs():
    """Définitions de champs personnalisés (admin), depuis la DB si disponible.
    Tolérant : renvoie () tant que le modèle/la table CustomFieldDefinition
    n'existent pas encore, ou hors contexte d'application."""
    try:
        from models import CustomFieldDefinition  # n'existe pas encore → ImportError
        defs = (CustomFieldDefinition.query
                .filter_by(is_active=True)
                .order_by(CustomFieldDefinition.ordre).all())
    except Exception:
        return ()
    return tuple(
        FieldDef(key=d.key, label=d.display_name, type=d.type, group=GROUP_PERSO,
                 order=d.ordre or 0, source='custom', options=tuple(d.options or ()))
        for d in defs
    )


def contact_fields(include_custom: bool = True):
    """Tous les champs de contact (colonnes + perso), triés par (groupe, ordre, clé)."""
    fields = list(CONTACT_COLUMN_FIELDS)
    if include_custom:
        fields += list(_custom_field_defs())
    gpos = {g: i for i, g in enumerate(_GROUP_ORDER)}
    return sorted(fields, key=lambda f: (gpos.get(f.group, 99), f.order, f.key))


def fields_by_group(include_custom: bool = True):
    """{ (group_key, group_label) : [FieldDef ordonnés] } — pour le rendu par sections."""
    grouped = {}
    for f in contact_fields(include_custom):
        grouped.setdefault(f.group, []).append(f)
    return {
        (g, GROUP_LABELS.get(g, g)): grouped[g]
        for g in _GROUP_ORDER if g in grouped
    }


def field_map(include_custom: bool = True):
    """{ key: FieldDef }."""
    return {f.key: f for f in contact_fields(include_custom)}


def group(gkey: str, include_custom: bool = True):
    """Champs d'un groupe donné (pour le rendu ciblé d'une section)."""
    return [f for f in contact_fields(include_custom) if f.group == gkey]


def label(key: str, default: str = None) -> str:
    """Getter du display_name (point d'entrée de la future i18n)."""
    f = field_map().get(key)
    if f:
        return f.label
    return default if default is not None else key


def field_options(f):
    """Options effectives d'un champ 'select'.

    Résolution : override `Setting[options_source]` (JSON éditable en Paramètres)
    s'il existe et n'est pas vide, SINON les `options` statiques/fallback du registre.
    → sur une installation « from scratch », Setting est vide donc on lit le fallback
    du registre (source de vérité canonique des défauts). Tolérant hors app-context."""
    if getattr(f, 'options_source', ''):
        try:
            import json
            from helpers import get_setting
            raw = get_setting(f.options_source, None)
            if raw:
                vals = json.loads(raw) if isinstance(raw, str) else raw
                if vals:
                    return tuple(vals)
        except Exception:
            pass
    return tuple(f.options or ())


def mailing_variables(include_custom: bool = True):
    """Liste (key, label) des champs exposés comme variables de fusion {key}."""
    return [(f.key, f.label) for f in contact_fields(include_custom) if f.mailing_var]
