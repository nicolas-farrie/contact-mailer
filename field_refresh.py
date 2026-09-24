"""Rafraîchissement des champs de contact alimentés par un connecteur (NOÉ).

Les réponses au formulaire d'inscription — compétences, formation, régime — descendaient
uniquement sur un geste humain. C'était prudent, mais insuffisant : « NOÉ fait foi » ne
vaut que si quelqu'un pense à cliquer, et personne n'y pense entre deux festivals.

Deux déclencheurs automatiques, plus le bouton qui existe déjà :
- **à l'ouverture d'une session**, en tâche de fond : interroger le service prend
  plusieurs secondes, et personne n'attendra devant une page de connexion ;
- **à chaque synchronisation** des listes, qui tourne déjà sur les instances.

Trois garde-fous, parce que le service tiers n'est pas à nous :
- **un intervalle minimum** (2 h) : dix connexions dans la matinée ne font pas dix
  appels ; l'horodatage vit dans les réglages, pas en mémoire, pour survivre au
  redémarrage et être partagé par les deux workers ;
- **un seul rafraîchissement à la fois**, sans quoi deux connexions simultanées
  lanceraient deux passes concurrentes sur les mêmes fiches ;
- **aucune création de contact** : seuls les bénévoles DÉJÀ appariés sont mis à jour.
  Faire entrer quelqu'un reste une décision humaine (cf. l'en-tête de `list_sync.py`) —
  un rafraîchissement silencieux n'a pas à peupler la base.

Une seule passe suffit pour toutes les listes : les réponses appartiennent à la
personne, pas au groupe. On lit donc « Tous les inscrits » une fois, plutôt qu'une fois
par catégorie rattachée.
"""

import logging
import threading
from datetime import timedelta

from models import db, Contact, ExternalIdentity, utcnow

log = logging.getLogger(__name__)

#: Horodatage du dernier rafraîchissement réussi (réglage, donc partagé et persistant).
LAST_SYNC_SETTING = 'noe.fields_synced_at'

#: Intervalle minimum entre deux rafraîchissements automatiques.
MIN_INTERVAL = timedelta(hours=2)

#: Un seul rafraîchissement à la fois dans ce processus ; le verrou n'est pas relâché
#: entre deux appels rapprochés, c'est l'intervalle qui s'en charge.
_running = threading.Lock()


def _last_sync():
    from helpers import get_setting
    from datetime import datetime
    raw = get_setting(LAST_SYNC_SETTING, '') or ''
    try:
        return datetime.fromisoformat(raw) if raw else None
    except ValueError:
        return None


def is_due(now=None):
    """Le rafraîchissement automatique est-il attendu ? (vrai s'il n'a jamais eu lieu)."""
    last = _last_sync()
    if last is None:
        return True
    return (now or utcnow()) - last >= MIN_INTERVAL


def refresh(provider='noe', force=False):
    """Reprend les réponses du service pour les contacts déjà appariés.

    Retourne un compte-rendu {'updated', 'seen', 'skipped', 'error'}. `skipped` porte la
    raison quand rien n'a été fait — pas de correspondance définie, trop tôt, ou une
    passe déjà en cours : autant de cas normaux, pas des échecs.
    """
    from connectors import get_connector
    from helpers import set_setting

    res = {'updated': 0, 'seen': 0, 'skipped': None, 'error': None}
    cfg = get_connector(provider)
    if cfg is None or not cfg.is_configured():
        res['skipped'] = 'connecteur indisponible'
        return res
    fmap = cfg.field_map() if hasattr(cfg, 'field_map') else {}
    if not fmap:
        res['skipped'] = 'aucune question mise en correspondance'
        return res
    if not force and not is_due():
        res['skipped'] = 'rafraîchi il y a moins de deux heures'
        return res
    if not _running.acquire(blocking=False):
        res['skipped'] = 'rafraîchissement déjà en cours'
        return res

    try:
        from noe import GROUP_ALL
        from blueprints.imports import _key_sets, _custom_types, _run_import

        # « Tous les inscrits » : les réponses appartiennent à la personne, pas au
        # groupe — une seule lecture du projet suffit pour toutes les listes.
        members = cfg.fetch_members(f'{cfg.DEFAULT_LEVEL}:{GROUP_ALL}')
        res['seen'] = len(members)
        connus = _apparies(cfg, members)
        if not connus:
            res['skipped'] = 'aucun bénévole apparié'
            set_setting(LAST_SYNC_SETTING, utcnow().isoformat())
            return res

        col_keys, custom_keys = _key_sets()
        mapping = {k: k for k in ('email', 'prenom', 'nom', 'telephone')}
        mapping.update({k: k for k in fmap.values()})
        rows = [{k: m.get(k, '') for k in mapping} for m in connus]
        # Mode « compléter les vides » : l'identité reste la nôtre, tandis que les champs
        # pilotés sont remplacés de toute façon — le régime du champ prime sur le mode.
        counts = _run_import(rows, mapping, col_keys, custom_keys, _custom_types(),
                             'fill', [], None, synced_provider=cfg.name)
        res['updated'] = counts.get('updated', 0)
        set_setting(LAST_SYNC_SETTING, utcnow().isoformat())
        log.info('Réponses %s rafraîchies : %s fiche(s) sur %s bénévole(s) appariés',
                 cfg.label, res['updated'], len(connus))
    except Exception as e:
        res['error'] = str(e)
        log.warning('Rafraîchissement des réponses %s en échec : %s', provider, e)
    finally:
        _running.release()
    return res


def _apparies(connector, members):
    """Les membres qui ont DÉJÀ une fiche chez nous — les seuls à mettre à jour.

    Un nouveau venu reste à importer par un humain : c'est le sens de l'écran « Mise à
    jour », et ce n'est pas à un rafraîchissement de fond d'en décider.
    """
    instance = connector.instance_key()
    ext_ids = [(m.get('ext_id') or '').strip() for m in members if m.get('ext_id')]
    if not ext_ids:
        return []
    connus = {ei.external_id for ei in ExternalIdentity.query.filter(
        ExternalIdentity.provider == connector.name,
        ExternalIdentity.instance == instance,
        ExternalIdentity.external_id.in_(ext_ids)).all()}
    return [m for m in members if (m.get('ext_id') or '').strip() in connus]


def refresh_async(app, provider='noe', force=False):
    """Lance le rafraîchissement en tâche de fond, sans jamais faire attendre personne.

    Sort immédiatement si ce n'est pas l'heure : inutile de créer un fil pour qu'il
    constate qu'il n'a rien à faire, et une page de connexion ne doit rien démarrer de
    coûteux.
    """
    if not force and not is_due():
        return None
    thread = threading.Thread(target=_run_in_context, args=(app, provider, force),
                              name='field-refresh', daemon=True)
    thread.start()
    return thread


def _run_in_context(app, provider, force):
    try:
        with app.app_context():
            try:
                refresh(provider, force=force)
            finally:
                # DANS le contexte : une session rendue après sa sortie lève « working
                # outside of application context » et salit les journaux d'une trace qui
                # n'a rien à voir avec le travail fait.
                db.session.remove()
    except Exception:
        log.exception('Rafraîchissement des réponses : échec du fil de fond')
