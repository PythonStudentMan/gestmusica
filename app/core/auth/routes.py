import uuid
from datetime import datetime, timedelta, timezone

from flask import (
    Blueprint, render_template, redirect, url_for, session, flash, request, g
)
from app import db
from app.core.auth.forms import LoginForm
from app.models.tenant import Tenant
from app.models.user import Identity, TenantMember, Session as UserSession
from app.middleware.tenant import set_tenant

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


def login_required(f):
    """ Decorador que protege rutas que reguieren autenticación """
    from functools import wraps

    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('member_id'):
            flash('Debes iniciar sesión para acceder.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)

    return decorated


def load_logged_in_user():
    """
    Carga el usuario y tenant activo desde la sesión Flask.
    Se llama antes de cada request desde el blueprint.
    """
    member_id = session.get('member_id')
    tenant_id = session.get('tenant_id')

    g.user = None

    if member_id and tenant_id:
        member = TenantMember.query.filter_by(
            id=member_id,
            tenant_id=tenant_id,
            activo=True
        ).first()
        if member:
            identity_activo = member.identity.activo
            if identity_activo:
                g.user = member
                set_tenant(member.tenant)

@auth_bp.before_app_request
def before_request():
    load_logged_in_user()

@auth_bp.route('/login/', methods=['GET', 'POST'])
def login():
    # Si ya está autenticado, redirigimos al dashboard
    if session.get('member_id'):
        return redirect(url_for('auth.dashboard'))

    form = LoginForm()

    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        password = form.password.data

        # Buscamos el usuario dentro del tenant
        identity = Identity.query.filter_by(
            email=email,
            activo=True
        ).first()

        if not identity or not identity.check_password(password):
            flash('Email o contraseña incorrectos.', 'danger')
            return render_template('auth/login.html', form=form)

        # Comprobar que la identidad pertenece a este tenant
        member = TenantMember.query.filter_by(
            identity_id=identity.id,
            activo=True,
        ).count()
        if member < 1:
            flash('No tienes acceso a esta plataforma.', 'danger')
            return render_template('auth/login.html', form=form)

        # Si tiene más de una membresía, debe elegir con qué agrupación quiere abrir sesión
        if member > 1:
            # elegir agrupación


        # 4. Registramos sessión en BD
        token = str(uuid.uuid4())
        expires = datetime.now(timezone.utc) + timedelta(days=7)

        user_session = UserSession(
            identity_id=identity.id,
            tenant_id=tenant.id,
            session_token=token,
            expired_at=expires,
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string[:255],
        )
        db.session.add(user_session)
        db.session.commit()

        # 5. Guardar en sesión Flask
        session.clear()
        session['member_id'] = str(member.id)
        session['tenant_id'] = str(tenant.id)
        session['tenant_slug'] = tenant.slug
        session['tenant_nombre'] = tenant.nombre
        session.permanent = form.remember.data

        return redirect(url_for('auth.dashboard'))

    return render_template('auth/login.html', form=form)

@auth_bp.route('/logout/')
def logout():
    session.clear()
    flash('Has cerrado sesión correctamente', 'success')
    return redirect(url_for('auth.login'))

@auth_bp.route('/dashboard/', methods=['GET'])
@login_required
def dashboard():
    return render_template('auth/dashboard.html')