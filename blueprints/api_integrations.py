"""Blueprint api_integrations : intégrations externes BookStack et Seafile
(synchronisation des rôles/groupes, push des contacts, mots de passe, invitations).

Endpoints : api_integrations.bookstack / bookstack_sync_roles / bookstack_push,
api_integrations.seafile / seafile_sync_groups / seafile_push /
seafile_liste_contacts / seafile_reset_passwords / seafile_send_invitations.
"""
from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, jsonify)
from flask_login import current_user

from models import db, Contact, Liste, BookstackRole
from config import Config
from helpers import admin_required

bp = Blueprint('api_integrations', __name__)


# === BOOKSTACK ===

@bp.route('/bookstack')
@admin_required
def bookstack():
    roles = BookstackRole.query.order_by(BookstackRole.display_name).all()
    listes = Liste.query.order_by(Liste.nom).all()
    bs_configured = bool(Config.BOOKSTACK_URL and Config.BOOKSTACK_TOKEN_ID and Config.BOOKSTACK_TOKEN_SECRET)
    return render_template('bookstack.html', roles=roles, listes=listes, bs_configured=bs_configured, active_tab='bookstack')


@bp.route('/bookstack/sync-roles', methods=['POST'])
@admin_required
def bookstack_sync_roles():
    from bookstack import BookstackClient
    from datetime import datetime

    if not Config.BOOKSTACK_URL:
        flash('BookStack non configuré', 'error')
        return redirect(url_for('api_integrations.bookstack'))

    try:
        client = BookstackClient(Config.BOOKSTACK_URL, Config.BOOKSTACK_TOKEN_ID, Config.BOOKSTACK_TOKEN_SECRET)
        data = client.list_roles()
        bs_roles = data.get('data', [])

        now = datetime.utcnow()
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
    listes = Liste.query.order_by(Liste.nom).all()
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
                               listes=Liste.query.order_by(Liste.nom).all(),
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
