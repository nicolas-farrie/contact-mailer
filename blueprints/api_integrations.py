"""Blueprint api_integrations : intégrations externes (NOÉ, BookStack, Seafile).

Page d'accueil `index` : l'état de chaque connecteur, configuré ou non. Elle existe
parce que la sidebar affichait Seafile et BookStack sans vérifier leur configuration —
un clic menait à une impasse sur les instances qui ne les utilisent pas.

Endpoints : api_integrations.index, api_integrations.bookstack /
bookstack_sync_roles / bookstack_push, api_integrations.seafile /
seafile_sync_groups / seafile_push / seafile_liste_contacts /
seafile_reset_passwords / seafile_send_invitations.
"""
from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, jsonify)
from flask_login import current_user, login_required

from models import db, Contact, Liste, BookstackRole, ListSource, ExternalIdentity, utcnow
from config import Config
from connectors import all_status, get_connector
from helpers import admin_required, listes_sorted

bp = Blueprint('api_integrations', __name__)


# === ACCUEIL ===

@bp.route('/integrations')
@admin_required
def index():
    """État de chaque connecteur : relié à quoi, ou quels réglages manquent.

    Aucun appel réseau : la page doit s'ouvrir même service éteint. Vérifier qu'une
    connexion fonctionne vraiment est le travail de chaque page de connecteur.
    """
    return render_template('integrations.html', connectors=all_status(),
                           active_tab='integrations')


# === NOÉ ===

@bp.route('/integrations/noe')
@login_required
def noe():
    """Les groupes de bénévoles du projet NOÉ, avec leurs effectifs.

    `@login_required` et non `@admin_required` : un utilisateur crée et modifie déjà des
    contacts (cf. blueprints/contacts.py), et cette page ne fait que lire une source
    fixe. L'import de fichiers, lui, accepte n'importe quel contenu et reste admin.
    """
    level = request.args.get('level', 'category')
    if level not in ('category', 'activity'):
        level = 'category'

    cfg = get_connector('noe')
    # Pôles déjà rattachés à une liste : proposer « Alimenter » pour eux induirait en
    # erreur, puisqu'une liste n'a qu'une source et qu'un pôle n'alimente qu'une liste.
    fed_refs = {s.ref: s.liste.nom for s in ListSource.query.filter_by(
        provider=cfg.name, instance=cfg.instance_key()).all()}
    ctx = {'level': level, 'configured': cfg.is_configured(), 'missing': cfg.missing_settings(),
           'project_name': '', 'groups': [], 'error': None, 'total': 0,
           'fed_refs': fed_refs, 'active_tab': 'noe'}

    if ctx['configured']:
        try:
            from noe import NoeClient, build_group_index, GROUP_ALL
            client = NoeClient(Config.NOE_URL, Config.NOE_TOKEN, Config.NOE_PROJECT_ID)
            project = client.get_project()
            index = build_group_index(client, level=level, project=project)
            ctx['project_name'] = project.get('name', '')
            ctx['total'] = len(index.get(GROUP_ALL, []))
            # GROUP_ALL en tête (c'est l'ensemble), puis les pôles du plus fourni au moins.
            # « Tous les inscrits » en tête, puis du plus fourni au moins — les pôles
            # sans personne finissent en bas, visibles mais sans encombrer.
            ctx['groups'] = sorted(
                ({'name': n, 'count': len(c)} for n, c in index.items()),
                key=lambda g: (g['name'] != GROUP_ALL, -g['count'], g['name']))
        except RuntimeError as e:
            # Service injoignable ou jeton périmé : la page s'affiche quand même, avec
            # la raison. Elle est le point d'entrée du connecteur, pas un cul-de-sac.
            ctx['error'] = str(e)

    return render_template('noe.html', **ctx)


@bp.route('/integrations/noe/feed', methods=['GET', 'POST'])
@login_required
def noe_feed():
    """Rattache un pôle NOÉ à une liste : analyse d'abord, alimentation ensuite.

    Réutilise l'import existant (_dry_run / _run_import de blueprints.imports) sans le
    modifier : le connecteur renvoie des dicts dont les clés sont déjà des noms de
    champs, donc un mapping identité suffit. Même code, mêmes garde-fous, mêmes modes
    de conflit que pour un fichier — une source d'API n'a pas à être un cas à part.
    """
    from blueprints.imports import _dry_run, _run_import, _key_sets, _custom_types

    cfg = get_connector('noe')
    if not cfg.is_configured():
        flash('NOÉ non configuré.', 'error')
        return redirect(url_for('api_integrations.noe'))

    ref = (request.values.get('ref') or '').strip()
    if not ref:
        return redirect(url_for('api_integrations.noe'))

    mode = request.values.get('mode', 'fill')
    if mode not in ('skip', 'fill', 'overwrite'):
        mode = 'fill'
    action = request.values.get('action', '')

    # Seules les listes SANS source peuvent être rattachées : une liste n'a qu'un maître.
    libres = [l for l in listes_sorted(is_archived=False) if l.source is None]

    try:
        members = cfg.fetch_members(ref)
    except RuntimeError as e:
        flash(f'NOÉ injoignable : {e}', 'error')
        return redirect(url_for('api_integrations.noe'))

    ctx = {'ref': ref, 'members': members, 'listes': libres, 'mode': mode,
           'counts': None, 'conflicts': None, 'unsubscribed': [], 'trashed': [],
           'target_kind': request.values.get('target_kind', 'new'),
           'new_list_name': request.values.get('new_list_name', ref),
           'liste_id': request.values.get('liste_id', ''),
           'active_tab': 'noe'}

    # Ce que l'utilisateur doit savoir avant d'écrire : les désabonnés ne recevront rien
    # malgré leur présence dans la liste, et un contact en corbeille serait recréé en
    # double par l'import (qui ne cherche que parmi les vivants).
    emails = [m['email'].strip().lower() for m in members if m.get('email')]
    if emails:
        rows = Contact.query.filter(db.func.lower(Contact.email).in_(emails)).all()
        ctx['unsubscribed'] = [c for c in rows if not c.is_deleted and c.is_unsubscribed]
        ctx['trashed'] = [c for c in rows if c.is_deleted]

    if action in ('preview', 'run'):
        col_keys, custom_keys = _key_sets()
        custom_types = _custom_types()
        # Mapping identité : les clés du connecteur SONT des clés de champs.
        # `source` s'y ajoute pour tracer l'origine des fiches créées : _import_mapped
        # l'honore à la création (imports.py) et écrirait « Import » sinon, ce qui ferait
        # perdre de quel service elles viennent.
        mapping = {k: k for k in ('email', 'prenom', 'nom', 'telephone', 'source')}
        rows_in = [dict({k: m.get(k, '') for k in mapping}, source=cfg.label)
                   for m in members]

        if action == 'preview':
            counts, _s, conflicts = _dry_run(rows_in, mapping, col_keys, custom_keys,
                                             custom_types, mode, [])
            ctx['counts'], ctx['conflicts'] = counts, conflicts
            return render_template('noe_feed.html', **ctx)

        # === Alimentation réelle ===
        liste = None
        if ctx['target_kind'] == 'existing':
            liste = Liste.query.get(int(ctx['liste_id'])) if ctx['liste_id'] else None
            if liste is None or liste.source is not None:
                flash('Choisissez une liste sans source.', 'error')
                return render_template('noe_feed.html', **ctx)
        else:
            nom = (ctx['new_list_name'] or ref).strip()
            if Liste.query.filter_by(nom=nom).first():
                flash(f'Une liste « {nom} » existe déjà — choisissez-la ou changez de nom.', 'error')
                return render_template('noe_feed.html', **ctx)
            liste = Liste(nom=nom, created_by_id=current_user.id)
            db.session.add(liste)
            db.session.flush()

        # _run_import attend des NOMS de listes (cf. _get_or_create_listes), pas des
        # objets : la liste vient d'être créée, elle sera retrouvée par son nom.
        counts = _run_import(rows_in, mapping, col_keys, custom_keys, custom_types,
                             mode, [liste.nom], current_user.id)

        # La source : à partir d'ici la liste est un reflet, non modifiable à la main.
        liste.source = ListSource(provider=cfg.name, instance=cfg.instance_key(),
                                  ref=ref, label=ref, last_sync_at=utcnow())
        _link_identities(cfg, members)
        db.session.commit()

        flash(f"« {liste.nom} » est alimentée depuis {cfg.label} : "
              f"{counts['created']} créés, {counts['updated']} mis à jour, "
              f"{counts['skipped']} inchangés.", 'success')
        if ctx['unsubscribed']:
            flash(f"{len(ctx['unsubscribed'])} contact(s) de cette liste sont désabonnés : "
                  f"ils n'y recevront aucun envoi.", 'warning')
        return redirect(url_for('contacts.index', liste=liste.id))

    return render_template('noe_feed.html', **ctx)


def _link_identities(connector, members):
    """Apparie durablement chaque membre à son contact, par email puis par identité.

    C'est ce qui rend les synchronisations suivantes indépendantes de l'email : si une
    personne change d'adresse chez elle ou chez nous, l'identité externe garde le lien.
    N'écrase jamais un appariement existant.
    """
    instance = connector.instance_key()
    for m in members:
        ext_id, email = (m.get('ext_id') or '').strip(), (m.get('email') or '').strip().lower()
        if not ext_id or not email:
            continue
        known = ExternalIdentity.query.filter_by(provider=connector.name,
                                                 instance=instance,
                                                 external_id=ext_id).first()
        if known:
            continue
        contact = Contact.query.filter(db.func.lower(Contact.email) == email,
                                       Contact.is_deleted == False).first()
        if contact:
            db.session.add(ExternalIdentity(contact_id=contact.id, provider=connector.name,
                                            instance=instance, external_id=ext_id))


# === BOOKSTACK ===

@bp.route('/bookstack')
@admin_required
def bookstack():
    roles = BookstackRole.query.order_by(BookstackRole.display_name).all()
    listes = listes_sorted(is_archived=None)
    bs_configured = bool(Config.BOOKSTACK_URL and Config.BOOKSTACK_TOKEN_ID and Config.BOOKSTACK_TOKEN_SECRET)
    return render_template('bookstack.html', roles=roles, listes=listes, bs_configured=bs_configured, active_tab='bookstack')


@bp.route('/bookstack/sync-roles', methods=['POST'])
@admin_required
def bookstack_sync_roles():
    from bookstack import BookstackClient

    if not Config.BOOKSTACK_URL:
        flash('BookStack non configuré', 'error')
        return redirect(url_for('api_integrations.bookstack'))

    try:
        client = BookstackClient(Config.BOOKSTACK_URL, Config.BOOKSTACK_TOKEN_ID, Config.BOOKSTACK_TOKEN_SECRET)
        data = client.list_roles()
        bs_roles = data.get('data', [])

        now = utcnow()
        bs_ids = set()

        for r in bs_roles:
            bs_ids.add(r['id'])
            existing = BookstackRole.query.get(r['id'])
            if existing:
                existing.display_name = r['display_name']
                existing.synced_at = now
            else:
                db.session.add(BookstackRole(id=r['id'], display_name=r['display_name'], synced_at=now))

        # Supprimer les rôles qui n'existent plus dans BS
        BookstackRole.query.filter(~BookstackRole.id.in_(bs_ids)).delete(synchronize_session=False)

        db.session.commit()
        flash(f'{len(bs_roles)} rôles synchronisés depuis BookStack', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Erreur BookStack : {e}', 'error')

    return redirect(url_for('api_integrations.bookstack'))


@bp.route('/bookstack/push', methods=['POST'])
@admin_required
def bookstack_push():
    from bookstack import BookstackClient, push_contacts_to_bookstack

    if not Config.BOOKSTACK_URL:
        flash('BookStack non configuré', 'error')
        return redirect(url_for('api_integrations.bookstack'))

    liste_id = request.form.get('liste_id', type=int)
    role_id = request.form.get('role_id', type=int)

    if not liste_id or not role_id:
        flash('Sélectionnez une liste et un rôle', 'error')
        return redirect(url_for('api_integrations.bookstack'))

    liste = Liste.query.get_or_404(liste_id)
    if not liste.active_contacts:
        flash('Liste vide', 'error')
        return redirect(url_for('api_integrations.bookstack'))

    try:
        send_invite = request.form.get('send_invite') == 'on'
        client = BookstackClient(Config.BOOKSTACK_URL, Config.BOOKSTACK_TOKEN_ID, Config.BOOKSTACK_TOKEN_SECRET)
        result = push_contacts_to_bookstack(client, liste.active_contacts, role_id, send_invite=send_invite)

        parts = []
        if result['created']:
            parts.append(f'{result["created"]} créés')
        if result['updated']:
            parts.append(f'{result["updated"]} mis à jour')
        if result['skipped']:
            parts.append(f'{result["skipped"]} inchangés')
        if result['errors']:
            parts.append(f'{len(result["errors"])} erreurs')

        msg = f'Push vers BookStack : {", ".join(parts)}'
        category = 'success' if not result['errors'] else 'warning'
        flash(msg, category)

        for err in result['errors']:
            flash(f'Erreur : {err}', 'error')

    except Exception as e:
        flash(f'Erreur BookStack : {e}', 'error')

    return redirect(url_for('api_integrations.bookstack'))


# === SEAFILE ===

@bp.route('/seafile')
@admin_required
def seafile():
    listes = listes_sorted(is_archived=None)
    sf_configured = bool(Config.SEAFILE_URL and Config.SEAFILE_TOKEN)
    groups = []
    if sf_configured:
        try:
            from seafile import SeafileClient
            client = SeafileClient(Config.SEAFILE_URL, Config.SEAFILE_TOKEN)
            groups = client.list_groups()
        except Exception:
            pass
    pending_invitations = Contact.query.filter(Contact.seafile_temp_pwd.isnot(None), Contact.is_deleted == False).all()
    return render_template('seafile.html', listes=listes, groups=groups,
                           sf_configured=sf_configured, new_passwords={},
                           pending_invitations=pending_invitations, active_tab='seafile')


@bp.route('/seafile/sync-groups', methods=['POST'])
@admin_required
def seafile_sync_groups():
    """Crée dans Seafile un groupe pour chaque liste contact-mailer (si absent)."""
    from seafile import SeafileClient

    if not Config.SEAFILE_URL:
        flash('Seafile non configuré', 'error')
        return redirect(url_for('api_integrations.seafile'))

    liste_ids = request.form.getlist('liste_ids', type=int)
    if not liste_ids:
        flash('Aucune liste sélectionnée', 'error')
        return redirect(url_for('api_integrations.seafile'))

    try:
        client = SeafileClient(Config.SEAFILE_URL, Config.SEAFILE_TOKEN)
        existing = {g['name'] for g in client.list_groups()}
        listes = Liste.query.filter(Liste.id.in_(liste_ids)).all()
        created = 0
        skipped = 0
        for liste in listes:
            if liste.nom not in existing:
                client.create_group(liste.nom)
                created += 1
            else:
                skipped += 1
        flash(f'Groupes Seafile : {created} créés, {skipped} déjà existants', 'success')
    except Exception as e:
        flash(f'Erreur Seafile : {e}', 'error')

    return redirect(url_for('api_integrations.seafile'))


@bp.route('/seafile/push', methods=['POST'])
@admin_required
def seafile_push():
    """Pousse les contacts d'une liste vers Seafile et les ajoute à un groupe."""
    from seafile import SeafileClient, push_contacts_to_seafile

    if not Config.SEAFILE_URL:
        flash('Seafile non configuré', 'error')
        return redirect(url_for('api_integrations.seafile'))

    liste_id = request.form.get('liste_id', type=int)
    group_id = request.form.get('group_id', type=int)

    if not liste_id:
        flash('Sélectionnez une liste', 'error')
        return redirect(url_for('api_integrations.seafile'))

    liste = Liste.query.get_or_404(liste_id)
    if not liste.active_contacts:
        flash('Liste vide', 'error')
        return redirect(url_for('api_integrations.seafile'))

    try:
        client = SeafileClient(Config.SEAFILE_URL, Config.SEAFILE_TOKEN)
        result = push_contacts_to_seafile(client, liste.active_contacts, group_id or None)

        # Stocker les mots de passe temporaires en base
        if result['passwords']:
            email_to_contact = {c.email.strip().lower(): c for c in liste.active_contacts}
            for email, pwd in result['passwords'].items():
                contact = email_to_contact.get(email)
                if contact:
                    contact.seafile_temp_pwd = pwd
            db.session.commit()

        parts = []
        if result['created']:
            parts.append(f'{result["created"]} créés')
        if result['updated']:
            parts.append(f'{result["updated"]} mis à jour')
        if result['errors']:
            parts.append(f'{len(result["errors"])} erreurs')

        flash(f'Push Seafile : {", ".join(parts) or "aucun changement"}',
              'success' if not result['errors'] else 'warning')
        for err in result['errors']:
            flash(f'Erreur : {err}', 'error')

        groups = client.list_groups()
        pending_invitations = Contact.query.filter(Contact.seafile_temp_pwd.isnot(None), Contact.is_deleted == False).all()
        return render_template('seafile.html',
                               listes=listes_sorted(is_archived=None),
                               groups=groups,
                               sf_configured=True,
                               new_passwords=result.get('passwords', {}),
                               pending_invitations=pending_invitations,
                               active_tab='seafile')

    except Exception as e:
        flash(f'Erreur Seafile : {e}', 'error')
        return redirect(url_for('api_integrations.seafile'))


@bp.route('/seafile/contacts/<int:liste_id>')
@admin_required
def seafile_liste_contacts(liste_id):
    """Retourne les contacts d'une liste en JSON (pour la sélection AJAX)."""
    liste = Liste.query.get_or_404(liste_id)
    return jsonify([{
        'id': c.id,
        'prenom': c.prenom,
        'nom': c.nom,
        'email': c.email,
        'has_pending_pwd': bool(c.seafile_temp_pwd),
    } for c in liste.active_contacts])


@bp.route('/seafile/reset-passwords', methods=['POST'])
@admin_required
def seafile_reset_passwords():
    """Régénère les mots de passe Seafile pour les contacts sélectionnés d'une liste."""
    from seafile import SeafileClient, generate_password

    if not Config.SEAFILE_URL:
        flash('Seafile non configuré', 'error')
        return redirect(url_for('api_integrations.seafile'))

    liste_id = request.form.get('liste_id', type=int)
    contact_ids = set(request.form.getlist('contact_ids', type=int))

    if not liste_id:
        flash('Sélectionnez une liste', 'error')
        return redirect(url_for('api_integrations.seafile'))

    liste = Liste.query.get_or_404(liste_id)
    contacts = [c for c in liste.active_contacts if not contact_ids or c.id in contact_ids]
    if not contacts:
        flash('Aucun contact sélectionné', 'error')
        return redirect(url_for('api_integrations.seafile'))

    try:
        client = SeafileClient(Config.SEAFILE_URL, Config.SEAFILE_TOKEN)
        sf_users = client.list_users()
        contact_to_internal = {
            (u.get('contact_email') or u['email']).lower(): u['email']
            for u in sf_users
        }

        updated = 0
        not_found = 0
        for contact in contacts:
            internal_email = contact_to_internal.get(contact.email.strip().lower())
            if internal_email:
                pwd = generate_password()
                client.update_user(internal_email, password=pwd)
                contact.seafile_temp_pwd = pwd
                updated += 1
            else:
                not_found += 1

        db.session.commit()
        msg = f'{updated} mots de passe régénérés'
        if not_found:
            msg += f', {not_found} contacts non trouvés dans Seafile (pas encore poussés ?)'
        flash(msg, 'success' if not not_found else 'warning')

    except Exception as e:
        flash(f'Erreur Seafile : {e}', 'error')

    return redirect(url_for('api_integrations.seafile'))


@bp.route('/seafile/send-invitations', methods=['POST'])
@admin_required
def seafile_send_invitations():
    """Crée un mailing d'invitation pour les contacts avec un mot de passe Seafile en attente."""
    import uuid as _uuid
    from mailer import MailQueue

    subject = request.form.get('subject', '').strip()
    body = request.form.get('body', '').strip()
    message_personnalise = request.form.get('message_personnalise', '').strip()

    if not subject or not body:
        flash('Sujet et corps du mail requis', 'error')
        return redirect(url_for('api_integrations.seafile'))

    contacts = Contact.query.filter(Contact.seafile_temp_pwd.isnot(None), Contact.is_deleted == False).all()
    if not contacts:
        flash('Aucune invitation en attente', 'error')
        return redirect(url_for('api_integrations.seafile'))

    campaign_id = f'seafile-inv-{_uuid.uuid4().hex[:8]}'
    queue = MailQueue()
    queue.set_campaign_template(campaign_id, subject, body, format='html',
                                sent_by=current_user.display_name,
                                include_unsubscribe=False)

    for contact in contacts:
        contact_dict = contact.to_dict()
        contact_dict['seafile_url'] = Config.SEAFILE_URL
        contact_dict['message_personnalise'] = message_personnalise
        queue.add(contact_dict, campaign_id)

    # Vider les mots de passe après mise en queue
    for contact in contacts:
        contact.seafile_temp_pwd = None
    db.session.commit()

    flash(f'Campagne d\'invitation créée : {len(contacts)} contacts en attente d\'envoi.', 'success')
    return redirect(url_for('mailing.queue', campaign=campaign_id))
