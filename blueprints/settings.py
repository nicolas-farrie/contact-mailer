"""Blueprint settings : paramètres applicatifs (nom, apparence login) et
corbeille des contacts (restauration / purge).

Endpoints : settings.index, settings.clear_login_bg, settings.trash,
settings.trash_restore, settings.trash_purge.
"""
import os
import re
import uuid
import unicodedata

from flask import Blueprint, render_template, request, redirect, url_for, flash
from werkzeug.utils import secure_filename

from models import db, Contact, CustomFieldDefinition
from helpers import (admin_required, set_setting, _upload_dir,
                     _delete_current_login_bg, ALLOWED_IMAGE_EXT, MAX_IMAGE_BYTES)
import fields

bp = Blueprint('settings', __name__)


@bp.route('/settings', methods=['GET', 'POST'])
@admin_required
def index():
    if request.method == 'POST':
        section = request.form.get('section')

        if section == 'general':
            name = (request.form.get('app_name') or '').strip()
            if name:
                set_setting('app_name', name[:60])
                flash('Paramètres généraux enregistrés.', 'success')
            else:
                flash("Le nom de l'application ne peut pas être vide.", 'error')

        elif section == 'login_appearance':
            raw = request.form.get('login_overlay')
            if raw is not None and raw != '':
                try:
                    pct = max(0, min(70, int(float(raw))))
                    set_setting('login_overlay', str(pct / 100))
                except ValueError:
                    pass

            file = request.files.get('login_bg')
            if file and file.filename:
                ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
                if ext not in ALLOWED_IMAGE_EXT:
                    flash('Format non supporté (JPG, PNG ou WebP).', 'error')
                    return redirect(url_for('settings.index'))
                file.seek(0, os.SEEK_END)
                size = file.tell()
                file.seek(0)
                if size > MAX_IMAGE_BYTES:
                    flash('Image trop volumineuse (5 Mo maximum).', 'error')
                    return redirect(url_for('settings.index'))
                fname = f'login_bg_{uuid.uuid4().hex}.{ext}'
                dest = os.path.join(_upload_dir(), secure_filename(fname))
                try:
                    from PIL import Image
                    img = Image.open(file.stream)
                    img.verify()
                    file.seek(0)
                    img = Image.open(file.stream)
                    img.save(dest)
                except Exception:
                    file.seek(0)
                    file.save(dest)
                _delete_current_login_bg()
                set_setting('login_bg_filename', os.path.basename(dest))
            flash('Apparence de la connexion enregistrée.', 'success')

        return redirect(url_for('settings.index'))

    deleted_contacts = Contact.query.filter(Contact.is_deleted == True).order_by(Contact.deleted_at.desc()).all()
    return render_template('settings.html', active_tab='general', deleted_contacts=deleted_contacts)


@bp.route('/settings/clear-login-bg', methods=['POST'])
@admin_required
def clear_login_bg():
    _delete_current_login_bg()
    set_setting('login_bg_filename', '')
    flash('Image de fond supprimée.', 'success')
    return redirect(url_for('settings.index'))


@bp.route('/settings/trash')
@admin_required
def trash():
    deleted_contacts = Contact.query.filter(Contact.is_deleted == True).order_by(Contact.deleted_at.desc()).all()
    return render_template('settings.html', active_tab='settings', deleted_contacts=deleted_contacts)


@bp.route('/settings/trash/restore', methods=['POST'])
@admin_required
def trash_restore():
    ids = request.form.getlist('contact_ids', type=int)
    if not ids:
        flash('Aucun contact sélectionné', 'error')
        return redirect(url_for('settings.index'))
    contacts = Contact.query.filter(Contact.id.in_(ids), Contact.is_deleted == True).all()
    for c in contacts:
        c.is_deleted = False
        c.deleted_at = None
        c.deleted_by_id = None
    db.session.commit()
    flash(f'{len(contacts)} contact(s) restauré(s)', 'success')
    return redirect(url_for('settings.index'))


@bp.route('/settings/trash/purge', methods=['POST'])
@admin_required
def trash_purge():
    ids = request.form.getlist('contact_ids', type=int)
    if not ids:
        flash('Aucun contact sélectionné', 'error')
        return redirect(url_for('settings.index'))
    contacts = Contact.query.filter(Contact.id.in_(ids), Contact.is_deleted == True).all()
    count = len(contacts)
    for c in contacts:
        db.session.delete(c)
    db.session.commit()
    flash(f'{count} contact(s) supprimé(s) définitivement', 'success')
    return redirect(url_for('settings.index'))


# --- Champs personnalisés (définitions) ---

def _slugify_key(label):
    """Dérive une clé machine stable (fieldName) depuis un libellé."""
    s = unicodedata.normalize('NFKD', label.strip().lower())
    s = ''.join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r'[^a-z0-9]+', '_', s).strip('_')
    if s and s[0].isdigit():
        s = 'f_' + s
    return s


def _parse_options(form, ftype):
    """Options (une par ligne) pour un select, sinon None.

    Préserve une 1re ligne vide (→ option « — non précisé — » par défaut) et ne
    retire que les lignes vides EN FIN de liste. La 1re option est la valeur par
    défaut dans la fiche (comportement HTML respecté)."""
    if ftype != 'select':
        return None
    lines = [ln.strip() for ln in (form.get('options') or '').splitlines()]
    while lines and lines[-1] == '':
        lines.pop()
    return lines or None


@bp.route('/settings/custom-fields')
@admin_required
def custom_fields():
    defs = CustomFieldDefinition.query.order_by(
        CustomFieldDefinition.ordre, CustomFieldDefinition.id).all()
    return render_template('settings_custom_fields.html', active_tab='custom_fields',
                           defs=defs, reserved=sorted(fields.RESERVED_KEYS))


@bp.route('/settings/custom-fields/new', methods=['POST'])
@admin_required
def custom_field_new():
    label = (request.form.get('display_name') or '').strip()
    ftype = request.form.get('type') or 'text'
    if not label:
        flash('Le libellé est requis.', 'error')
        return redirect(url_for('settings.custom_fields'))
    key = _slugify_key(label)
    if not key:
        flash("Libellé invalide : impossible d'en dériver une clé.", 'error')
        return redirect(url_for('settings.custom_fields'))
    if key in fields.RESERVED_KEYS:
        flash(f'La clé « {key} » est réservée (champ standard). Choisissez un autre libellé.', 'error')
        return redirect(url_for('settings.custom_fields'))
    if CustomFieldDefinition.query.filter_by(key=key).first():
        flash(f'Un champ avec la clé « {key} » existe déjà.', 'error')
        return redirect(url_for('settings.custom_fields'))
    max_ordre = db.session.query(db.func.max(CustomFieldDefinition.ordre)).scalar() or 0
    db.session.add(CustomFieldDefinition(
        key=key, display_name=label, type=ftype,
        options=_parse_options(request.form, ftype),
        help_text=(request.form.get('help_text') or '').strip() or None,
        required=(request.form.get('required') == 'on'),
        ordre=max_ordre + 1))
    db.session.commit()
    flash(f'Champ « {label} » créé (clé : {key}).', 'success')
    return redirect(url_for('settings.custom_fields'))


@bp.route('/settings/custom-fields/<int:id>/edit', methods=['POST'])
@admin_required
def custom_field_edit(id):
    # La clé n'est PAS modifiable (stabilité des valeurs déjà saisies).
    cf = CustomFieldDefinition.query.get_or_404(id)
    label = (request.form.get('display_name') or '').strip()
    if label:
        cf.display_name = label
    cf.type = request.form.get('type') or cf.type
    cf.options = _parse_options(request.form, cf.type)
    cf.help_text = (request.form.get('help_text') or '').strip() or None
    cf.required = request.form.get('required') == 'on'
    db.session.commit()
    flash('Champ mis à jour.', 'success')
    return redirect(url_for('settings.custom_fields'))


@bp.route('/settings/custom-fields/<int:id>/toggle', methods=['POST'])
@admin_required
def custom_field_toggle(id):
    cf = CustomFieldDefinition.query.get_or_404(id)
    cf.is_active = not cf.is_active
    db.session.commit()
    flash(f"Champ « {cf.display_name} » {'activé' if cf.is_active else 'désactivé'}.", 'success')
    return redirect(url_for('settings.custom_fields'))


@bp.route('/settings/custom-fields/<int:id>/move', methods=['POST'])
@admin_required
def custom_field_move(id):
    direction = request.form.get('dir')
    defs = CustomFieldDefinition.query.order_by(
        CustomFieldDefinition.ordre, CustomFieldDefinition.id).all()
    idx = next((i for i, d in enumerate(defs) if d.id == id), None)
    swap = None
    if idx is not None:
        if direction == 'up' and idx > 0:
            swap = defs[idx - 1]
        elif direction == 'down' and idx < len(defs) - 1:
            swap = defs[idx + 1]
    if swap:
        defs[idx].ordre, swap.ordre = swap.ordre, defs[idx].ordre
        db.session.commit()
    return redirect(url_for('settings.custom_fields'))


@bp.route('/settings/custom-fields/<int:id>/delete', methods=['POST'])
@admin_required
def custom_field_delete(id):
    cf = CustomFieldDefinition.query.get_or_404(id)
    nom = cf.display_name
    db.session.delete(cf)
    db.session.commit()
    flash(f'Champ « {nom} » supprimé. Les valeurs déjà saisies dans les contacts sont '
          f'conservées mais masquées.', 'info')
    return redirect(url_for('settings.custom_fields'))
