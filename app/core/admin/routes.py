from flask import Blueprint, render_template, redirect, url_for, flash, request, g, abort
from app import db
from app.core.admin.forms import UsuarioForm, RolForm
from app.models.user import Identity, TenantMember, Role, MemberRole

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


def admin_required(f):
    """ Decorador que exige permiso admin.usuarios o admin.roles """
    from functools import wraps

    @wraps(f)
    def decorated(*args, **kwargs):
        if not g.get('user'):
            flash('Debes iniciar sesión para acceder.', 'warning')
            return redirect(url_for('auth.login'))
        if not g.user.tiene_permiso('admin.usuarios') and \
            not g.user.tiene_permiso('admin.roles'):
            abort(403)
        return f(*args, **kwargs)

    return decorated

# ----- Usuarios --------------------------------------------------------------------------

@admin_bp.route('/usuarios/')
@admin_required
def usuarios():
    members = TenantMember.query.filter_by(
        tenant_id=g.tenant_id
    ).order_by(TenantMember.joined_at).all()
    return render_template('admin/usuarios.html', usuarios=members)

@admin_bp.route('/usuarios/nuevo/', methods=['GET', 'POST'])
@admin_required
def usuario_nuevo():
    form = UsuarioForm()

    if form.validate_on_submit():
        # Comprobar email único en este tenant
        identity = Identity.query.filter_by(email=form.email.data.strip().lower()).first()
        if identity:
            member_existente = TenantMember.query.filter_by(
                identity_id=identity.id,
                tenant_id=g.tenant_id,
            ).first()
            if member_existente:
                flash('Ya existe un usuario con ese email en esta agrupación.', 'danger')
                return render_template('admin/usuario_form.html', form=form, titulo='Nuevo Usuario')
        else:
            # Crear una nueva identidad
            if not form.password.data:
                flash('La contraseña es obligatoria para nuevos usuarios.', 'danger')
                return render_template('adin/usuario_form.html', form=form, titulo='Nuevo Usuario')
            identity = Identity(
                email=form.email.data.strip().lower(),
                nombre=form.nombre.data.strip(),
                apellidos=form.apellidos.data.strip() if form.apellidos.data else None,
                activo=form.activo.data,
            )
            identity.set_password(form.password.data)
            db.session.add(identity)
            db.session.flush()

        # Crear la membresía en este tenant
        member = TenantMember(
            identity_id=identity.id,
            tenant_id=g.tenant_id,
            activo=form.activo.data,
        )
        db.session.add(member)
        db.session.commit()
        flash(f'Usuario {identity.nombre} creado correctamente.', 'success')
        return redirect(url_for('admin.usuarios'))

    return render_template('admin/usuario_form.html', form=form, titulo='Nuevo usuario')


@admin_bp.route('/usuarios/<uuid:member_id>/editar/', methods=['GET', 'POST'])
@admin_required
def usuario_editar(member_id):
    member = TenantMember.query.filter_by(
        id=member_id, tenant_id=g.tenant_id
    ).first_or_404()
    identity = member.identity
    form = UsuarioForm(obj=identity)

    if form.validate_on_submit():
        # Comprobar email único excluyendo el usuario actual
        existente = Identity.query.filter(
            Identity.email == form.email.data.strip().lower(),
            Identity.id != identity.id,
        ).first()
        if existente:
            # Comprobamos que el existente no es ya miembro de este tenant
            member_existente = TenantMember.query.filter_by(
                identity_id=existente.id,
                tenant_id=g.tenant_id,
            ).first()
            if member_existente:
                flash('Ya existe otro usuario con ese email en esta agrupación.', 'danger')
                return render_template('admin/usuario_form.html', form=form,
                                       titulo='Editar usuario', user=member)

        identity.nombre = form.nombre.data.strip()
        identity.apellidos = form.apellidos.data.strip() if form.apellidos.data else None
        identity.email = form.email.data.strip().lower()
        identity.activo = form.activo.data
        member.activo = form.activo.data

        if form.password.data:
            identity.set_password(form.password.data)

        db.session.commit()
        flash(f'Usuario {identity.nombre} actualizado correctamente.', 'success')
        return redirect(url_for('admin.usuarios'))

    return render_template('admin/usuario_form.html', form=form,
                           titulo='Editar usuario', user=member)


@admin_bp.route('/usuarios/<uuid:member_id>/desactivar/', methods=['POST'])
@admin_required
def usuario_desactivar(member_id):
    member = TenantMember.query.filter_by(
        id=member_id, tenant_id=g.tenant_id
    ).first_or_404()

    if member.id == g.user.id:
        flash('No puedes desactivar tu propio usuario.', 'warning')
        return redirect(url_for('admin.usuarios'))

    member.activo = not member.activo
    db.session.commit()
    estado = 'activado' if member.activo else 'desactivado'
    flash(f'Usuario {member.nombre} {estado} correctamente.', 'success')
    return redirect(url_for('admin.usuarios'))


@admin_bp.route('/usuarios/<uuid:member_id>/roles/', methods=['GET', 'POST'])
@admin_required
def usuario_roles(member_id):
    member = TenantMember.query.filter_by(
        id=member_id, tenant_id=g.tenant_id
    ).first_or_404()
    roles_tenant = Role.current_tenant().order_by(Role.nombre).all()

    if request.method == 'POST':
        role_ids = request.form.getlist('role_ids')

        # Eliminar asignaciones actuales
        MemberRole.query.filter_by(member_id=member.id).delete()

        # Crear nuevas asignaciones
        for role_id in role_ids:
            rol = Role.current_tenant().filter_by(id=role_id).first()
            if rol:
                db.session.add(MemberRole(member_id=member.id, role_id=rol.id))

        db.session.commit()
        flash(f'Roles de {member.nombre} actualizados correctamente.', 'success')
        return redirect(url_for('admin.usuarios'))

    roles_usuario = {str(ur.role_id) for ur in member.member_roles}
    return render_template('admin/usuario_roles.html',
                           user=member,
                           roles_tenant=roles_tenant,
                           roles_usuario=roles_usuario)

# ---- Roles ------------------------------------------------------------------------------

@admin_bp.route('/roles/')
@admin_required
def roles():
    roles = Role.current_tenant().order_by(Role.nombre).all()
    return render_template('admin/roles.html', roles=roles)


@admin_bp.route('/roles/nuevo/', methods=['GET', 'POST'])
@admin_required
def rol_nuevo():
    form = RolForm()

    if form.validate_on_submit():
        existente = Role.current_tenant().filter_by(nombre=form.nombre.data.strip()).first()
        if existente:
            flash('Ya existe un rol con ese nombre en esta agrupación.', 'danger')
            return render_template('admin/rol_form.html', form=form, titulo='Nuevo rol')

        rol = Role(
            tenant_id=g.tenant_id,
            nombre=form.nombre.data.strip(),
            permisos_json=form.permisos.data,
            es_sistema=False,
        )
        db.session.add(rol)
        db.session.commit()
        flash(f'Rol {rol.nombre} creado correctamente.', 'success')
        return redirect(url_for('admin.roles'))

    return render_template('admin/rol_form.html', form=form, titulo='Nuevo rol')


@admin_bp.route('/roles/<uuid:role_id>/editar/', methods=['GET', 'POST'])
@admin_required
def rol_editar(role_id):
    rol = Role.current_tenant().filter_by(id=role_id).first_or_404()

    if rol.es_sistema:
        flash('Los roles de sistema no se pueden editar.', 'warning')
        return redirect(url_for('admin.roles'))

    form = RolForm(obj=rol)
    if request.method == 'GET':
        form.permisos.data = rol.permisos_json or []

    if form.validate_on_submit():
        existente = Role.current_tenant().filter(
            Role.nombre == form.nombre.data.strip(),
            Role.id != rol.id,
        ).first()
        if existente:
            flash('Ya existe otro rol con ese nombre en esta agrupación.', 'danger')
            return render_template('admin/rol_form.html', form=form,
                                   titulo='Editar rol', rol=rol)

        rol.nombre = form.nombre.data.strip()
        rol.permisos_json = form.permisos.data
        db.session.commit()
        flash(f'Rol {rol.nombre} actualizado correctamente.', 'success')
        return redirect(url_for('admin.roles'))

    return render_template('admin/rol_form.html', form=form,
                           titulo='Editar rol', rol=rol)


@admin_bp.route('/roles/<uuid:role_id>/eliminar/', methods=['POST'])
@admin_required
def rol_eliminar(role_id):
    rol = Role.current_tenant().filter_by(id=role_id).first_or_404()

    if rol.es_sistema:
        flash('Los roles de sistema no se pueden eliminar.', 'warning')
        return redirect(url_for('admin.roles'))

    db.session.delete(rol)
    db.session.commit()
    flash(f'Rol {rol.nombre} eliminado correctamente.', 'success')
    return redirect(url_for('admin.roles'))