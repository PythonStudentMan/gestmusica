import uuid
from datetime import datetime, timedelta, timezone

from flask import (
    Blueprint, render_template, redirect, url_for,
    session, flash, request, g
)
from app import db
from app.core.auth.forms import LoginForm, AceptarInvitacionForm
from app.models.user import Identity, TenantMember, Session as UserSession, Invitacion
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
        if member and member.identity.activo:
            g.user = member
            set_tenant(member.tenant)

@auth_bp.before_app_request
def before_request():
    load_logged_in_user()

def _crear_sesion_bd(identity, tenant, remember):
    """ Persiste la sesión en BD y guarda los datos en la sesión Flask. """
    token = str(uuid.uuid4())
    expires = datetime.now(timezone.utc) + timedelta(days=7 if remember else 1)

    user_session = UserSession(
        identity_id=identity.id,
        tenant_id=tenant.id,
        session_token=token,
        expired_at=expires,
        ip_address=request.remote_addr,
        user_agent=request.user_agent.string[:255],
    )
    db.session.add(user_session)

    # Obtener el TenantMember concreto para este tenant
    member = TenantMember.query.filter_by(
        identity_id=identity.id,
        tenant_id=tenant.id,
        activo=True,
    ).first()

    db.session.commit()

    session.clear()
    session['member_id'] = str(member.id)
    session['tenant_id'] = str(tenant.id)
    session['tenant_slug'] = tenant.slug
    session['tenant_nombre'] = tenant.nombre
    session.pemanent = remember


@auth_bp.route('/login/', methods=['GET', 'POST'])
def login():
    # Si ya está autenticado, redirigimos al dashboard
    if session.get('member_id'):
        return redirect(url_for('auth.dashboard'))

    form = LoginForm()

    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        password = form.password.data

        # Verificar credenciales
        identity = Identity.query.filter_by(email=email, activo=True).first()
        if not identity or not identity.check_password(password):
            flash('Email o contraseña incorrectos.', 'danger')
            return render_template('auth/login.html', form=form)

        # Obtenere membresías activas
        member = TenantMember.query.filter_by(
            identity_id=identity.id,
            activo=True,
        ).all()

        if not member:
            flash('No tienes acceso a ninguna agrupación. Contacta con un administrador', 'danger')
            return render_template('auth/login.html', form=form)

        # Si sólo hay una agrupación en las membresías, se accede directamente a ella
        if len(member) == 1:
            _crear_sesion_bd(identity, member[0].tenant, form.remember.data)
            return redirect(url_for('auth.dashboard'))

        # Si hay varias agrupaciones, guardamos el estado temporal y mostramos selector
        session['_pending_identity_id'] = str(identity.id)
        session['_pendint_remember'] = form.remember.data
        return redirect(url_for('auth.seleccionar_agrupacion'))

    return render_template('auth/login.html', form=form)


@auth_bp.route('/seleccionar/', methods=['GET', 'POST'])
def seleccionar_agrupacion():
    """
    Paso intermedio del login cuando el usuario pertenece a varias agrupaciones.
    Solo accesible si existe _pending_identity_id en sesión.
    """
    identity_id = session.get('_pending_identity_id')
    if not identity_id:
        return redirect(url_for('auth.login'))

    identity = Identity.query.filter_by(id=identity_id, activo=True).first()
    if not identity:
        session.pop('_pending_identity_id', None)
        session.pop('_pending_remember', None)
        flash('Sesión expirada. Vuelve a iniciar sesión.', 'warning')
        return redirect(url_for('auth.login'))

    memberships = TenantMember.query.filter_by(identity_id=identity.id, activo=True).all()

    if request.method == 'POST':
        tenant_id = request.form.get('tenant_id')
        remember = session.get('_pending_remember', False)

        # Verificar que la agrupación elegida pertenece realmente a este usuario
        member = next(
            (m for m in memberships if str(m.tenant_id) == tenant_id),
            None
        )
        if not member:
            flash('Agrupación no válida.', 'danger')
            return render_template('auth/seleccionar_agrupacion.html',
                                   identity=identity, memberships=memberships)

        session.pop('_pending_identity_id', None)
        session.pop('_pending_remember', None)

        _crear_sesion_bd(identity, member.tenant, remember)
        return redirect(url_for('auth.dashboard'))

    return render_template('auth/seleccionar_agrupacion.html',
                           identity=identity, memberships=memberships)


@auth_bp.route('/logout/')
def logout():
    session.clear()
    flash('Has cerrado sesión correctamente', 'success')
    return redirect(url_for('auth.login'))

@auth_bp.route('/dashboard/')
@login_required
def dashboard():
    return render_template('auth/dashboard.html')

@auth_bp.route('/invitacion/<string:token>/', methods=['GET', 'POST'])
def aceptar_invitacion(token):
    """
    Ruta pública a la que llega el usuario desde el email de invitación.
    GET -> muestra el formulario para establecer nombre y contraseña
    POST -> crea/recupera la Identity, crea el TenantMember y hace login
    """
    inv = Invitacion.query.filter_by(token=token).first_or_404()

    if not inv.es_valida:
        if inv.estado == 'aceptada':
            flash('Esta invitación ya fue aceptada. Puede iniciar sesión directamente.', 'info')
        else:
            flash('Esta invitación ha caducado. Solicita una nueva al administrador.', 'warning')
        return redirect(url_for('auth.login'))

    form = AceptarInvitacionForm()

    # Pre-rellenar nombre si viene en la invitación
    if request.method == 'GET' and inv.nombre:
        form.nombre.data = inv.nombre

    if form.validate_on_submit():
        # Buscaar o crear la Identity
        identity = Identity.query.filter_by(email=inv.email).first()

        if identity:
            # La persona ya existe (quizá en otra agrupación):
            # Actualizamos nombre si no lo tenía y establecemos la contraseña
            if not identity.activo:
                identity.activo = True
            if form.nombre.data.strip():
                identity.nombre = form.nombre.data.strip()
            if form.apellidos.data and form.apellidos.data.strip():
                identity.apellidos = form.apellidos.data.strip()
            identity.set_password(form.password.data)
        else:
            identity = Identity(
                email=inv.email,
                nombre=form.nombre.data.strip(),
                apellidos=form.apellidos.data.strip() if form.apellidos.data else None,
                activo=True,
            )
            identity.set_password(form.password.data)
            db.session.add(identity)
            db.session.flush()

        # Crear la membresía si no existe ya
        member = TenantMember.query.filter_by(
            identity_id=identity.id, tenant_id=inv.tenant_id,
        ).first()
        if not member:
            member = TenantMember(
                identity_id=identity.id,
                tenant_id=inv.tenant_id,
                activo=True,
            )
            db.session.add(member)
            db.session.flush()
        else:
            member.activo = True

        # Marcar invitación como aceptada
        inv.marcar_aceptada(identity.id)

        db.session.commit()

        # Login automático
        _crear_sesion_bd(identity, inv.tenant, remember=False)
        flash(f'¡Bienvenido a {inv.tenant.nombre}! Tu cuenta ha sido activada.', 'success')
        return redirect(url_for('auth.dashboard'))

    return render_template('auth/aceptar_invitacion.html', form=form, invitacion=inv)