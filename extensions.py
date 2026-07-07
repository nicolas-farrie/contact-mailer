"""Extensions Flask partagées, instanciées sans app (pattern factory).

Séparé de app.py pour éviter les imports circulaires : les blueprints importent
`login_manager` d'ici, et app.py appelle `login_manager.init_app(app)`.
La base de données `db` reste dans models.py (déjà découplée).
"""
from flask_login import LoginManager

login_manager = LoginManager()
# login_view est mis à jour en 'public.login' lors de la migration du blueprint public.
login_manager.login_view = 'public.login'
login_manager.login_message = 'Veuillez vous connecter.'


@login_manager.user_loader
def load_user(user_id):
    from models import User
    user = User.query.get(int(user_id))
    if user and not user.is_active:
        return None
    return user
