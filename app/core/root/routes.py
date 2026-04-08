from flask import Blueprint, render_template, redirect, url_for, flash, request, g, session, abort
from functools import wraps
from app import db
from app.models.tenant import Tenant
from app.models.user import Identity, TenantMember
from app.core.root.forms import TenantForm
from app.middleware.tenant import set_tenant

root_bp = Blueprint('root', __name__, url_prefix='/root')

def root_required(f):
    """ Decorador para vistas que requieren usuario root """
    @wraps(f)
    def decorated(*args, **kwargs):
        if not g.get('user'):
            flash('Debes iniciar sesión para acceder.', 'warning')
            return redirect(url_for('auth.login'))

        if not g.user.identity.is_root:
            abort(403, description='Acceso restringido a adminsitradores globales.')

        return f(*args, **kwargs)
    return decorated


@root_bp.route('/')
@root_required
def dashboard():
    """ Panel principal del superadministrador """
    total_tenants = Tenant.query.count()
    tenants_activos = Tenant.query.filter_by(activo=True).count()
    total_usuarios = Identity.query.count()

    tenants = Tenant.query.order_by(Tenant.created_at.desc()).limit(5).all()

    return render_template('root/dashboard.html',
                           total_tenants=total_tenants,
                           tenants_activos=tenants_activos,
                           total_usuarios=total_usuarios,
                           tenants=tenants)


@root_bp.route('/tenants/')
@root_required
def tenants():
    """ Listado de todas las agrupaciones """
    tenants = Tenant.query.order_by(Tenant.nombre).all()
    return render_template('root/tenants.html', tenants=tenants)


@root_bp.route('/tenants/nuevo/', methods=['GET', 'POST'])
@root_required
def tenant_nuevo():
    """ Crear una nueva agrupación """
    form = TenantForm()

    if form.validate_on_submit():
        # Verificar slug único
        existente = Tenant.query.filter_by(slug=form.slug.data.strip().lower()).first()
        if existente:
            flash('Ya existe una agrupación con ese slug.', 'danger')
            return render_template('root/tenant_form.html', form=form, titulo='Nueva Agrupación')

        tenant = Tenant(
            slug=form.slug.data.strip().lower(),
            nombre=form.nombre.data.strip(),
            modo=form.modo.data,
            activo=form.activo.data,
        )
        db.session.add(tenant)
        db.session.commit()

        flash(f'Agrupación "{tenant.nombre}" creada correctamente.', 'success')
        return redirect(url_for('root.tenants'))

    return render_template('root/tenant_form.html', form=form, titulo='Nueva Agrupación')


@root_bp.route('/tenants/<uuid:tenant_id>/editar/', methods=['GET', 'POST'])
@root_required
def tenant_editar(tenant_id):
    """ Editar una agrupación existente """
    tenant = Tenant.query.get_or_404(tenant_id)
    form = TenantForm(obj=tenant)

    if form.validate_on_submit():
        # Verificar slug único (excluyento el tenant actual)
        existente = Tenant.query.filter(
            Tenant.slug == form.slug.data.strip().lower(),
            Tenant.id != tenant.id
        ).first()
        if existente:
            flash('Ya existe otra agrupación con ese mismo slug', 'danger')
            return render_template('root/tenant_form.html', form=form, titulo='Edigar Agrupación', tenant=tenant)

        tenant.slug = form.slug.data.strip().lower()
        tenant.nombre = form.nombre.data.strip()
        tenant.modo = form.modo.data
        tenant.activo = form.activo.data

        db.session.commit()
        flash(f'Agrupación "{tenant.nombre}" actualizada correctamente.', 'success')
        return redirect(url_for('root.tenants'))

    return render_template('root/tenant_form.html', form=form, titulo='Editar Agrupación', tenant=tenant)


@root_bp.route('/tenants/<uuid:tenant_id>/toggle/', methods=['GET', 'POST'])
@root_required
def tenant_toggle(tenant_id):
    """ Activar/Desactivar una agrupación """
    tenant = Tenant.query.get_or_404(tenant_id)
    tenant.activo = not tenant.activo
    db.session.commit()

    estado = 'activada' if tenant.activo else 'desactivada'
    flash(f'Agrupación "{tenant.nombre}" {estado}.', 'success')
    return redirect(url_for('root.tenants'))


@root_bp.route('/tenants/<uuid:tenant_id>/entrar/')
@root_required
def tenant_entrar(tenant_id):
    """ Suplantar: entrar como administrador en una agrupación """
    tenant = Tenant.query.get_or_404(tenant_id)

    if not tenant.activo:
        flash('No puedes entrar en una agrupación desactivada.', 'warning')
        return redirect(url_for('root.tenants'))

    # Buscar o crear membresía del root en este tenant
    member = TenantMember.query.filter_by(
        identity_id=g.user.identity.id,
        tenant_id=tenant.id
    ).first()

    if not member:
        member = TenantMember(
            identity_id=g.user.identity.id,
            tenant_id=tenant.id,
            activo=True,
        )
        db.session.add(member)
        db.session.commit()

    # Establecer sesión en este tenant
    session['member_id'] = str(member.id)
    session['tenant_id'] = str(tenant.id)
    session['tenant_slug'] = tenant.slug
    session['tenant_nombre'] = tenant.nombre

    set_tenant(tenant)

    flash(f'Has entrado como administrador en {tenant.nombre}.', 'success')
    return redirect(url_for('auth.dashboard'))