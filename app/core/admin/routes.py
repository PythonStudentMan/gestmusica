from flask import Blueprint, render_template, redirect, url_for, flash, request, g, abort
from app import db
from app.core.admin.forms import UsuarioForm, RolForm, MemberPermisoForm, InvitacionForm
from app.models.user import Identity, TenantMember, Role, MemberRole, MemberPermiso, Invitacion

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

    return render_template('admin/usuario_form.html', form=form, titulo='Editar usuario')


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

# ---- Permisos individuales -----------------------------------------------------------
@admin_bp.route('/usuarios/<uuid:member_id>/permisos/', methods=['GET', 'POST'])
@admin_required
def usuario_permisos(member_id):
    """
    Gestiona los permisos individuales (MemberPermiso) de un miembro.
    Estos permisos son aditivos: amplían lo que dan sus roles sin modificarlos.
    Útil para accesos temporales o excepcionales.
    """
    member = TenantMember.query.filter_by(
        id=member_id, tenant_id=g.tenant_id
    ).first_or_404()

    form = MemberPermisoForm()

    if form.validate_on_submit():
        # Evitar duplicados
        existente = MemberPermiso.query.filter_by(
            member_id=member.id,
            permiso=form.permiso.data,
        ).first()
        if existente:
            flash('Este permiso ya está asignado a este usuario', 'warning')
        else:
            mp = MemberPermiso(
                member_id=member.id,
                permiso=form.permiso.data,
                motivo=form.motivo.data.strip(),
            )
            db.session.add(mp)
            db.session.commit()
            flash(f'Permiso "{form.permiso.data}" añadido correctamente.', 'success')
        return redirect(url_for('admin.usuario_permisos', member_id=member_id))

    permisos_individuales = MemberPermiso.query.filter_by(
        member_id=member.id
    ).order_by(MemberPermiso.created_at).all()

    return render_template('admin/usuario_permisos.html', user=member,
                           form=form, permisos_individuales=permisos_individuales)


@admin_bp.route('/usuarios/<uuid:member_id>/permisos/<uuid:permiso_id>/revocar/', methods=['POST'])
@admin_required
def usuario_permiso_revocar(member_id, permiso_id):
    member = TenantMember.query.filter_by(
        id=member_id, tenant_id=g.tenant_id
    ).first_or_404()
    mp = MemberPermiso.query.filter_by(
        id=permiso_id, member_id=member.id
    ).first_or_404()

    permiso_nombre = mp.permiso
    db.session.delete(mp)
    db.session.commit()
    flash(f'Permiso "{permiso_nombre} revocado correctamente.', 'success')
    return redirect(url_for('admin.usuario_permisos', member_id=member_id))


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

# -------- Invitaciones -----------------------------------------------------------------
@admin_bp.route('/invitaciones/', methods=['GET'])
@admin_required
def invitaciones():
    """ Lista de invitaciones enviadas en esta agrupación """
    invs = Invitacion.query.filter_by(
        tenant_id=g.tenant_id
    ).order_by(Invitacion.created_at.desc()).all()
    return render_template('admin/invitaciones.html', invitaciones=invs)

@admin_bp.route('/invitaciones/nueva/', methods=['GET', 'POST'])
@admin_required
def invitacion_nueva():
    """ El admin genera una invitación y se envía por email """
    form = InvitacionForm()

    if form.validate_on_submit():
        email = form.email.data.strip().lower()

        # Comprobar que no hay ya un miembro activo con ese email en este tenant
        identity = Identity.query.filter_by(email=email).first()
        if identity:
            ya_miembro = TenantMember.query.filter_by(
                identity_id=identity.id,
                tenant_id=g.tenant_id,
                activo=True,
            ).first()
            if ya_miembro:
                flash('Ya existe un usuario activo con ese email en esta agrupación', 'warning')
                return render_template('admin/invitacion_form.html', form=form)

        # Anular invitaciones pendientes previas para el mismo email en este tenant
        Invitacion.query.filter_by(
            tenant_id=g.tenant_id,
            email=email,
            estado='pendiente',
        ).update({'estado': 'caducada'}, synchronize_session='fetch')
        db.session.flush()

        inv = Invitacion.crear(
            tenant_id=g.tenant_id,
            email=email,
            nombre=form.nombre.data,
            invitado_por_id=g.user.id,
        )
        db.session.add(inv)
        db.session.flush()
        db.session.refresh(inv)

        db.session.commit()

        # Enviar email
        try:
            from app.core.email import send_invitacion
            send_invitacion(inv)
            flash(f'Invitación enviada a {email}.', 'success')
        except Exception as e:
            flash(f'Invitación creada pero error al enviar el email: {e}', 'warning')

        return redirect(url_for('admin.invitaciones'))

    return render_template('admin/invitacion_form.html', form=form)


@admin_bp.route('/invitaciones/<uuid:inv_id>/reenviar/', methods=['POST'])
@admin_required
def invitacion_reenviar(inv_id):
    print("\n" + "=" * 60)
    print("DEBUG: Entrando a invitación_reenviar")
    print(f"DEBUG: inv_id= {inv_id}")
    print(f"DEBUG: g.tenant_id = {g.tenant_id}")
    print(f"DEBUG: g.user = {g.user}")
    print("=" * 60 + "\n")

    """ Reenvía el email de una invitación pendiente """
    inv = Invitacion.query.filter_by(
        id=inv_id, tenant_id=g.tenant_id
    ).first_or_404()

    print(f"DEBUG: Invitación encontrada: {inv.id}, estado: {inv.estado}, es_valida={inv.es_valida}")

    if not inv.es_valida:
        flash('Esta invitación ya no es válida (aceptada o caducada).', 'warning')
        return redirect(url_for('admin.invitaciones'))

    try:
        from app.core.email import send_invitacion
        send_invitacion(inv)
        flash(f'Invitación reenviada a {inv.email}.', 'success')
    except Exception as e:
        flash(f'Error al reenviar el email: {e}', 'danger')

    print("DEBUG: Redirigiando a admin.invitaciones")
    return redirect(url_for('admin.invitaciones'))


@admin_bp.route('/invitaciones/<uuid:inv_id>/cancelar/', methods=['POST'])
@admin_required
def invitacion_cancelar(inv_id):
    """ Cancela (caduca) una invitación pendiente """
    inv = Invitacion.query.filter_by(
        id=inv_id, tenant_id=g.tenant_id
    ).first_or_404()

    if inv.estado != 'pendiente':
        flash('Solo se pueden cancelar invitaciones pendientes.', 'warning')
        return redirect(url_for('admin.invitaciones'))

    inv.estado = 'caducada'
    db.session.commit()
    flash(f'Invitación a {inv.email} cancelada.', 'success')
    return redirect(url_for('admin.invitaciones'))


# ---- Subagrupaciones -----------------------------------------------------------

@admin_bp.route('/subagrupaciones/')
@admin_required
def subagrupaciones():
    from app.models.tenant import Subagrupacion
    subags = Subagrupacion.query.filter_by(tenant_id=g.tenant_id).order_by(
        Subagrupacion.nombre
    ).all()
    return render_template('admin/subagrupaciones.html', subagrupaciones=subags)


@admin_bp.route('/subagrupaciones/nueva/', methods=['GET', 'POST'])
@admin_required
def subagrupacion_nueva():
    from app.models.tenant import Subagrupacion
    from app.core.admin.forms import SubagrupacionForm

    form = SubagrupacionForm()

    if form.validate_on_submit():
        existente = Subagrupacion.query.filter_by(
            tenant_id=g.tenant_id, nombre=form.nombre.data.strip()
        ).first()
        if existente:
            flash('Ya existe una sección con ese nombre.', 'danger')
            return render_template('admin/subagrupacion_form.html',
                                   form=form, titulo='Nueva sección')

        subag = Subagrupacion(
            tenant_id=g.tenant_id,
            nombre=form.nombre.data.strip(),
            descripcion=form.descripcion.data,
            activa=form.activa.data,
        )
        db.session.add(subag)
        db.session.commit()
        flash(f'Sección "{subag.nombre}" creada correctamente.', 'success')
        return redirect(url_for('admin.subagrupaciones'))

    return render_template('admin/subagrupacion_form.html',
                           form=form, titulo='Nueva sección')


@admin_bp.route('/subagrupaciones/<uuid:subag_id>/editar/', methods=['GET', 'POST'])
@admin_required
def subagrupacion_editar(subag_id):
    from app.models.tenant import Subagrupacion
    from app.core.admin.forms import SubagrupacionForm

    subag = Subagrupacion.query.filter_by(
        id=subag_id, tenant_id=g.tenant_id
    ).first_or_404()
    form = SubagrupacionForm(obj=subag)

    if form.validate_on_submit():
        existente = Subagrupacion.query.filter(
            Subagrupacion.tenant_id == g.tenant_id,
            Subagrupacion.nombre == form.nombre.data.strip(),
            Subagrupacion.id != subag.id
        ).first()
        if existente:
            flash('Ya existe otra sección con ese nombre.', 'danger')
            return render_template('admin/subagrupacion_form.html',
                                   form=form, titulo='Editar sección', subag=subag)

        subag.nombre = form.nombre.data.strip()
        subag.descripcion = form.descripcion.data
        subag.activa = form.activa.data
        db.session.commit()
        flash(f'Sección "{subag.nombre}" actualizada.', 'success')
        return redirect(url_for('admin.subagrupaciones'))

    return render_template('admin/subagrupacion_form.html',
                           form=form, titulo='Editar sección', subag=subag)


@admin_bp.route('/subagrupaciones/<uuid:subag_id>/toggle/', methods=['POST'])
@admin_required
def subagrupacion_toggle(subag_id):
    from app.models.tenant import Subagrupacion

    subag = Subagrupacion.query.filter_by(
        id=subag_id, tenant_id=g.tenant_id
    ).first_or_404()
    subag.activa = not subag.activa
    db.session.commit()

    estado = 'activada' if subag.activa else 'desactivada'
    flash(f'Sección "{subag.nombre}" {estado}.', 'success')
    return redirect(url_for('admin.subagrupaciones'))


# ---- Instrumentos ------------------------------------------------------

@admin_bp.route('/instrumentos/')
@admin_required
def instrumentos():
    from app.modules.musicos.models import Instrumento
    insts = Instrumento.query.filter_by(tenant_id=g.tenant_id).order_by(
        Instrumento.nombre
    ).all()
    return render_template('admin/instrumentos.html', instrumentos=insts)


@admin_bp.route('/instrumentos/nuevo/', methods=['GET', 'POST'])
@admin_required
def instrumento_nuevo():
    from app.modules.musicos.models import Instrumento
    from app.core.admin.forms import InstrumentoForm

    form = InstrumentoForm()

    if form.validate_on_submit():
        existente = Instrumento.query.filter_by(
            tenant_id=g.tenant_id, nombre=form.nombre.data.strip()
        ).first()
        if existente:
            flash('Ya existe un instrumento con ese nombre', 'danger')
            return render_template('admin/instrumento_form.html',
                                   form=form, titulo='Nuevo instrumento')

        inst = Instrumento(
            tenant_id=g.tenant_id,
            nombre=form.nombre.data.strip(),
            familia=form.familia.data or None,
            activo=form.activo.data,
        )
        db.session.add(inst)
        db.session.commit()
        flash(f'Instrumento "{inst.nombre}" creado correctamente.', 'success')
        return redirect(url_for('admin.instrumentos'))

    return render_template('admin/instrumento_form.html',
                           form=form, titulo='Nuevo instrumento')


@admin_bp.route('/instrumentos/<uuid:inst_id>/editar/', methods=['GET', 'POST'])
@admin_required
def instrumento_editar(inst_id):
    from app.modules.musicos.models import Instrumento
    from app.core.admin.forms import InstrumentoForm

    inst = Instrumento.query.filter_by(
        id=inst_id, tenant_id=g.tenant_id
    ).first_or_404()
    form = InstrumentoForm(obj=inst)

    if form.validate_on_submit():
        existente = Instrumento.query.filter(
            Instrumento.tenant_id == g.tenant_id,
            Instrumento.nombre == form.nombre.data.strip(),
            Instrumento.id != inst.id
        ).first()
        if existente:
            flash('Ya existe otro instrumento con ese nombre', 'danger')
            return render_template('admin/instrumento_form.html',
                                   form=form, titulo='Editar instrumento', inst=inst)

        inst.nombre = form.nombre.data.strip()
        inst.familia = form.familia.data or None
        inst.activo = form.activo.data
        db.session.commit()
        flash(f'Instrumento "{inst.nombre}" actualizado', 'success')
        return redirect(url_for('admin.instrumentos'))

    return render_template('admin/instrumento_form.html',
                           form=form, titulo='Editar instrumento', inst=inst)


@admin_bp.route('/instrumentos/<uuid:inst_id>/toggle/', methods=['POST'])
@admin_required
def instrumento_toggle(inst_id):
    from app.modules.musicos.models import Instrumento

    inst = Instrumento.query.filter_by(
        id=inst_id, tenant_id=g.tenant_id
    ).first_or_404()
    inst.activo = not inst.activo
    db.session.commit()

    estado = 'activado' if inst.activo else 'desactivado'
    flash(f'Instrumento "{inst.nombre}" {estado}.', 'success')
    return redirect(url_for('admin.instrumentos'))