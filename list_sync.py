"""Synchronisation des listes alimentées par une source externe.

Le « régime automatique » du connecteur : il ne touche qu'à l'appartenance des contacts
(`contact_liste`), jamais à leur contenu. C'est ce qui le rend inoffensif, donc lançable
sans surveillance — et c'est exactement ce qui bouge pendant un festival, où les gens
changent de créneau tous les jours.

Générique par construction : le provider n'est qu'une valeur, la source est interrogée
via le registre des connecteurs (cf. connectors.py). Une liste alimentée depuis Seafile
ou BookStack se synchroniserait par le même chemin.

Ce que la synchronisation NE fait PAS, volontairement :
  - créer un contact : un nouveau bénévole demande des décisions (doublon probable,
    désabonné, corbeille) que seul un humain peut prendre → il est compté, pas importé ;
  - modifier un champ : nom, email et téléphone appartiennent à contact-mailer ;
  - toucher `is_unsubscribed` ou `has_bounced` : un désabonnement est un droit exercé
    par la personne, qu'aucune synchronisation ne révoque ;
  - retirer un contact de la base : sortir d'un pôle, c'est quitter la liste, pas
    disparaître.
"""

from models import db, Contact, ExternalIdentity, ListSource, utcnow
from connectors import get_connector


def sync_source(source, connector=None):
    """Aligne une liste sur son groupe d'origine. Retourne un compte-rendu.

    Le miroir ne porte que sur les contacts **appariés à cette source** : une fiche
    ajoutée à la liste avant son rattachement n'est pas expulsée par une synchro qu'elle
    n'a pas demandée. Sortir du groupe NOÉ fait sortir de la liste ; être arrivé
    autrement ne regarde pas la source.
    """
    result = {'liste': source.liste.nom, 'ref': source.ref,
              'added': 0, 'removed': 0, 'pending': 0, 'error': None}

    connector = connector or get_connector(source.provider)
    if connector is None or not connector.is_configured():
        result['error'] = f'connecteur « {source.provider} » indisponible ou non configuré'
        return result
    # Une source venue d'une autre installation (autre projet NOÉ) n'est pas la nôtre :
    # la synchroniser avec les données courantes mélangerait deux événements.
    if connector.instance_key() != source.instance:
        result['error'] = 'la source vient d\'une autre instance du service'
        return result

    try:
        members = connector.fetch_members(source.ref)
    except RuntimeError as e:
        result['error'] = str(e)
        return result

    instance = source.instance
    ext_ids = [(m.get('ext_id') or '').strip() for m in members if m.get('ext_id')]

    # Les contacts que la source désigne aujourd'hui, retrouvés par leur identité
    # externe — jamais par l'email, qui change.
    voulus = {}
    if ext_ids:
        rows = (db.session.query(ExternalIdentity, Contact)
                .join(Contact, Contact.id == ExternalIdentity.contact_id)
                .filter(ExternalIdentity.provider == connector.name,
                        ExternalIdentity.instance == instance,
                        ExternalIdentity.external_id.in_(ext_ids),
                        Contact.is_deleted == False)
                .all())
        voulus = {c.id: c for _ei, c in rows}
    # Un membre sans contact apparié est un nouveau venu : compté ici, importé nulle part.
    result['pending'] = len(ext_ids) - len(voulus)

    liste = source.liste
    presents = {c.id: c for c in liste.contacts if not c.is_deleted}

    for cid, contact in voulus.items():
        if cid not in presents:
            liste.contacts.append(contact)
            result['added'] += 1

    # Ne retirer que ce que la source avait amené : les identités de CE provider et de
    # CETTE instance. Le reste a une autre histoire.
    if presents:
        rattaches = {ei.contact_id for ei in ExternalIdentity.query.filter(
            ExternalIdentity.provider == connector.name,
            ExternalIdentity.instance == instance,
            ExternalIdentity.contact_id.in_(list(presents))).all()}
        for cid in rattaches - set(voulus):
            liste.contacts.remove(presents[cid])
            result['removed'] += 1

    source.last_sync_at = utcnow()
    source.last_error = None
    return result


def sync_all(provider=None):
    """Synchronise toutes les listes alimentées. Retourne la liste des comptes-rendus.

    Les listes archivées sont ignorées : archiver signifie « je ne m'en sers plus », et
    continuer à les alimenter consommerait des appels tout en faussant la fraîcheur
    affichée. Les désarchiver les remet dans le cycle au passage suivant.

    Une source en échec n'interrompt pas les autres : son erreur est consignée dans
    `last_error` pour être montrée à l'écran, et la boucle continue.
    """
    q = ListSource.query.join(ListSource.liste).filter_by(is_archived=False)
    if provider:
        q = q.filter(ListSource.provider == provider)

    connectors = {}
    results = []
    for source in q.all():
        if source.provider not in connectors:
            connectors[source.provider] = get_connector(source.provider)
        res = sync_source(source, connectors[source.provider])
        if res['error']:
            source.last_error = res['error'][:500]
        results.append(res)

    db.session.commit()
    return results
