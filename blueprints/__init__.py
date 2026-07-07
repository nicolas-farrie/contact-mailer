"""Blueprints Flask, un module par domaine métier.

Chaque module expose un objet `bp = Blueprint(...)` enregistré par create_app()
(voir app.py). Les endpoints sont donc namespacés : url_for('contacts.index'), etc.
"""
