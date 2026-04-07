from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
from flask_mail import Mail

from config import config

db = SQLAlchemy()
migrate = Migrate()
csrf = CSRFProtect()
mail = Mail()

def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # Inicializar extensiones
    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    mail.init_app(app)

    # Importar modelos para que Alembic los detecte
    with app.app_context():
        from app.models import (
            Tenant, TenantConfig, Module, TenantModule, Subagrupacion,
            Identity, TenantMember, Session, Role, MemberRole, MemberPermiso,
            Invitacion,
        )

    # Registrar middleware
    from app.middleware.tenant import TenantMiddleware
    TenantMiddleware(app)

    # Registrar blueprints
    from app.core.auth import auth_bp
    app.register_blueprint(auth_bp)

    from app.core.admin import admin_bp
    app.register_blueprint(admin_bp)

    from app.modules.socios import socios_bp
    app.register_blueprint(socios_bp)

    return app