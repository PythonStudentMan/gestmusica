from datetime import date
from flask import Blueprint, render_template, redirect, url_for, flash, request, g
from app import db
from app.core.auth.routes import login_required
from app.modules.socios.models import (
    SociosConfig, UnidadFamiliar, Persona, TutorLegal,
    TipoSocio, Socio, Cuota, Recibo,
)
from app.modules.socios.forms import (
    TipoSocioForm, PersonaForm, SocioForm, BajaForm,
    CuotaForm, PagoReciboForm, TutorLegalForm, SociosConfigForm,
)

socios_bp = Blueprint('socios', __name__, url_prefix='/socios')

def socios_required(f):
    from functools import wraps

    @wraps(f)
    def decorated(*args, **kwargs):
        if not g.get('user'):
            flash('Debes iniciar sesión para acceder.', 'warning')
            return redirect(url_for('auth.login'))
        if not g.user.tiene_permiso('socios.ver'):
            flash('No tienes permiso para acceder al módulo de socios.', 'danger')
            return redirect(url_for('auth.dashboard'))
        return f(*args, **kwargs)

    return decorated


# ---- Dashboard Socio ----------------------------------------------------------------

@socios_bp.route('/')
@socios_required
def index():
    total_activos = Socio.for_tenant(g.tenant_id).filter_by(estado='activo').count()
    total_bajas = Socio.for_tenant(g.tenant_id).filter_by(estado='baja').count()
    recibos_pendientes = Recibo.query.filter_by(
        tenant_id=g.tenant_id, estado='pendiente'
    ).count()
    recibos_vencidos = Recibo.query.filter_by(
        tenant_id=g.tenant_id, estado='vencido'
    ).count()

    return render_template('socios/index.html',
                           total_activos=total_activos,
                           total_bajas=total_bajas,
                           recibos_pendientes=recibos_pendientes,
                           recibos_vencidos=recibos_vencidos)

# ---- Tipos de Socio ----------------------------------------------------------------

@socios_bp.route('/tipos/')
@socios_required
def tipos_socio():
    tipos = TipoSocio.query.filter_by(tenant_id=g.tenant_id).order_by(TipoSocio.nombre).all()
    return render_template('socios/tipos_socio.html', tipos=tipos)

@socios_bp.route('/tipos/nuevo/', methods=['GET', 'POST'])
@socios_required
def tipo_socio_nuevo():
    if not g.user.tiene_permiso('socios.crear'):
        flash('No tienes permiso para crear tipos de socio', 'danger')
        return redirect(url_for('socios.tipos_socio'))

    form = TipoSocioForm()
    if form.validate_on_submit():
        existente = TipoSocio.query.filter_by(
            tenant_id=g.tenant_id, nombre=form.nombre.data.strip()
        ).first()
        if existente:
            flash('Ya existe un tipo de socio con ese nombre', 'danger')
            return render_template('socios/tipo_socio_form.html',
                                   form=form, titulo='Nuevo tipo de socio')

        tipo = TipoSocio(
            tenant_id=g.tenant_id,
            nombre=form.nombre.data.strip(),
            descripcion=form.descripcion.data,
            importe_cuota=form.importe_cuota.data,
            periodicidad=form.periodicidad.data,
            activo=form.activo.data,
        )
        db.session.add(tipo)
        db.session.commit()
        flash(f'Tipo de socio {tipo.nombre} creado correctamente', 'success')
        return redirect(url_for('socios.tipos_socio'))

    return render_template('socios/tipo_socio_form.html',
                           form=form, titulo='Nuevo tipo de socio')

@socios_bp.route('/tipos/<uuid:tipo_id>/editar/', methods=['GET', 'POST'])
@socios_required
def tipo_socio_editar(tipo_id):
    if not g.user.tiene_permiso('socios.editar'):
        flash('No tienes permiso para editar tipos de socio.', 'danger')
        return redirect(url_for('socios.tipos_socio'))

    tipo = TipoSocio.query.filter_by(id=tipo_id, tenant_id=g.tenant_id).first_or_404()
    form = TipoSocioForm(obj=tipo)

    if form.validate_on_submit():
        tipo.nombre = form.nombre.data.strip()
        tipo.descripcion = form.descripcion.data
        tipo.importe_cuota = form.importe_cuota.data
        tipo.periodicidad = form.periodicidad.data
        tipo.activo = form.activo.data
        db.session.commit()
        flash(f'Tipo de socio {tipo.nombre} actualizado.', 'success')
        return redirect(url_for('socios.tipos_socio'))

    return render_template('socios/tipo_socio_form.html',
                           form=form, titulo='Editar tipo de socio')

# ---- Socios ----------------------------------------------------------------

@socios_bp.route('/lista/')
@socios_required
def lista():
    estado = request.args.get('estado', 'activo')
    query = Socio.for_tenant(g.tenant_id)
    if estado != 'todos':
        query = query.filter_by(estado=estado)
    socios = query.order_by(Socio.numero_socio).all()
    return render_template('socios/socios.html', socios=socios, estado=estado)

@socios_bp.route('/nuevo/', methods=['GET', 'POST'])
@socios_required
def socio_nuevo():
    if not g.user.tiene_permiso('socios.crear'):
        flash('No tienes permiso para crear socios.', 'danger')
        return redirect(url_for('socios.lista'))

    persona_form = PersonaForm()
    socio_form = SocioForm()

    # Poblar selectores
    tipos = TipoSocio.for_tenant(g.tenant_id).all()
    socio_form.tipo_socio_id.choices = [(str(t.id), t.nombre) for t in tipos]

    unidades = UnidadFamiliar.query.filter_by(tenant_id=g.tenant_id).all()
    socio_form.unidad_familiar_id.choices = [('', 'Sin unidad familiar')] + [
        (str(u.id), u.nombre) for u in unidades
    ]

    if request.method == 'POST' and persona_form.validate_on_submit() \
        and socio_form.validate_on_submit():

        # Comprobar número de socio único
        existente = Socio.query.filter_by(
            tenant_id=g.tenant_id,
            numero_socio=socio_form.numero_socio.data.strip(),
        ).first()
        if existente:
            flash('Ya existe un socio en ese número', 'danger')
            return render_template('socios/socio_form.html',
                                   persona_form=persona_form,
                                   socio_form=socio_form,
                                   titulo='Nuevo socio')

        # Crear persona
        persona = Persona(
            tenant_id=g.tenant_id,
            nombre=persona_form.nombre.data.strip(),
            apellidos=persona_form.apellidos.data.strip(),
            email=persona_form.email.data.strip() if persona_form.email.data else None,
            telefono=persona_form.telefono.data.strip() if persona_form.telefono.data else None,
            fecha_nacimiento=persona_form.fecha_nacimiento.data,
            dni=persona_form.dni.data.strip() if persona_form.dni.data else None,
        )
        persona.actualizar_es_menor()
        db.session.add(persona)
        db.session.flush()

        # Crear socio
        socio = Socio(
            tenant_id=g.tenant_id,
            persona_id=persona.id,
            tipo_socio_id=socio_form.tipo_socio_id.data,
            unidad_familiar_id=socio_form.unidad_familiar_id.data or None,
            numero_socio=socio_form.numero_socio.data.strip(),
            fecha_alta=socio_form.fecha_alta.data,
            estado=socio_form.estado.data,
            es_titular_familiar=socio_form.es_titular_familiar.data,
        )
        db.session.add(socio)
        db.session.commit()
        flash(f'Socio {persona.nombre_completo} dado de alta correctamente', 'success')
        return redirect(url_for('socios.socio_detalle', socio_id=socio.id))

    return render_template('socios/socio_form.html',
                           persona_form=persona_form,
                           socio_form=socio_form,
                           titulo='Nuevo socio')

@socios_bp.route('/<uuid:socio_id>/')
@socios_required
def socio_detalle(socio_id):
    socio = Socio.query.filter_by(id=socio_id, tenant_id=g.tenant_id).first_or_404()
    recibos = socio.recibos.order_by(Recibo.fecha_emision.desc()).all()
    tutores = socio.persona.tutores.all() if socio.persona.es_menor else []
    return render_template('socios/socio_detalle.html', socio=socio, recibos=recibos, tutores=tutores)

@socios_bp.route('/<uuid:socio_id>/editar/', methods=['GET', 'POST'])
@socios_required
def socio_editar(socio_id):
    if not g.user.tiene_permiso('socios.editar'):
        flash('No tienes permiso para editar socios', 'danger')
        return redirect(url_for('socios.lista'))

    socio = Socio.query.filter_by(id=socio_id, tenant_id=g.tenant_id).first_or_404()
    persona = socio.persona

    persona_form = PersonaForm(obj=persona)
    socio_form = SocioForm(obj=socio)

    tipos = TipoSocio.for_tenant(g.tenant_id).all()
    socio_form.tipo_socio_id.choices = [(str(t.id), t.nombre) for t in tipos]

    unidades = UnidadFamiliar.query.filter_by(tenant_id=g.tenant_id).all()
    socio_form.unidad_familiar_id.choices = [('', 'Sin unidad familiar')] + [
        (str(u.id), u.nombre) for u in unidades
    ]

    if request.method == 'POST' and persona_form.validate_on_submit() \
        and socio_form.validate_on_submit():

        persona.nombre = persona_form.nombre.data.strip()
        persona.apellidos = persona_form.apellidos.data.strip()
        persona.email = persona_form.email.data.strip() if persona_form.email else None
        persona.telefono = persona_form.telefono.data.strip() if persona_form.telefono else None
        persona.fecha_nacimiento = persona_form.fecha_nacimiento.data
        persona.dni = persona_form.dni.data if persona_form.dni else None
        persona.actualizar_es_menor()

        socio.tipo_socio_id = socio_form.tipo_socio_id.data
        socio.unidad_familiar_id = socio_form.unidad_familiar_id.data or None
        socio.numero_socio = socio_form.numero_socio.data.strip()
        socio.fecha_alta = socio_form.fecha_alta.data
        socio.estado = socio_form.estado.data
        socio.es_titular_familiar = socio_form.es_titular_familiar.data

        db.session.commit()
        flash(f'Socio {persona.nombre_completo} actualizado correctamente', 'success')
        return redirect(url_for('socios.socio_detalle', socio_id=socio.id))

    if request.method == 'GET':
        socio_form.tipo_socio_id.data = str(socio.tipo_socio_id)
        socio_form.unidad_familiar_id.data = str(socio.unidad_familiar_id) if socio.unidad_familiar_id else ''

    return render_template('socios/socio_form.html',
                       persona_form=persona_form,
                       socio_form=socio_form,
                       titulo='Editar socio',
                       socio=socio)

@socios_bp.route('/<uuid:socio_id>/baja/', methods=['GET', 'POST'])
@socios_required
def socio_baja(socio_id):
    if not g.user.tiene_permiso('socios.eliminar'):
        flash('No tienes permiso para dar de baja socios', 'danger')
        return redirect(url_for('socios.lista'))

    socio = Socio.query.filter_by(id=socio_id, tenant_id=g.tenant_id).first_or_404()
    form = BajaForm()

    if form.validate_on_submit():
        socio.dar_baja(form.fecha_baja.data)
        db.session.commit()
        flash(f'Socio {socio.nombre_completo} dado de baja', 'success')
        return redirect(url_for('socios.lista'))

    return render_template('socios/socio_baja.html', form=form, socio=socio)


# ---- Tutores legales ----------------------------------------------------------------

@socios_bp.route('/<uuid:socio_id>/tutores/nuevo/', methods=['GET', 'POST'])
@socios_required
def tutor_nuevo(socio_id):
    if not g.user.tiene_permiso('socios.editar'):
        flash('No tienes permiso para gestionar tutores.', 'danger')
        return redirect(url_for('socios.lista'))

    socio = Socio.query.filter_by(id=socio_id, tenant_id=g.tenant_id).first_or_404()

    if not socio.persona.es_menor:
        flash('Solo se pueden añadir tutores a personas menores de edad', 'warning')
        return redirect(url_for('socios.socio_detalle', socio_id=socio_id))

    config=SociosConfig.for_tenant(g.tenant_id)
    tutores_actuales = socio.persona.tutores.count()
    if tutores_actuales >= config.max_tutores_menor:
        flash(f'Este menor ya tiene el máximo de {config.max_tutores_menor} tutores', 'warning')
        return redirect(url_for('socios.socio_detalle', socio_id=socio_id))

    form = TutorLegalForm()
    personas = Persona.query.filter_by(
        tenant_id=g.tenant_id, es_menor=False
    ).order_by(Persona.apellidos).all()
    form.persona_tutor_id.choices = [(str(p.id), p.nombre_completo) for p in personas]

    if form.validate_on_submit():
        tutor = TutorLegal(
            tenant_id=g.tenant_id,
            persona_menor_id=socio.persona.id,
            persona_tutor_id=form.persona_tutor_id.data,
            relacion=form.relacion.data,
            patria_potestad=form.patria_potestad.data,
            firma_requerida=form.firma_requerida.data,
        )
        db.session.add(tutor)
        db.session.commit()
        flash('Tutor legal añadido correctamente', 'success')
        return redirect(url_for('socios.socio_detalle', socio_id=socio_id))

    return render_template('socios/tutor_form.html', form=form, socio=socio)

# ---- Cuotas ----------------------------------------------------------------

@socios_bp.route('/cuotas/')
@socios_required
def cuotas():
    cuotas = Cuota.for_tenant(g.tenant_id).order_by(Cuota.fecha_inicio.desc()).all()
    return render_template('socios/cuotas.html', cuotas=cuotas)

@socios_bp.route('/cuotas/nueva/', methods=['GET', 'POST'])
@socios_required
def cuota_nueva():
    if not g.user.tiene_permiso('cuotas.crear'):
        flash('No tienes permiso para crear cuotas.', 'danger')
        return redirect(url_for('socios.cuotas'))

    form = CuotaForm()
    tipos = TipoSocio.for_tenant(g.tenant_id).all()
    form.tipo_socio_id.choices = [(str(t.id), t.nombre) for t in tipos]

    if form.validate_on_submit():
        cuota = Cuota(
            tenant_id=g.tenant_id,
            tipo_socio_id=form.tipo_socio_id.data,
            descripcion=form.descripcion.data.strip(),
            importe=form.importe.data,
            fecha_inicio=form.fecha_inicio.data,
            fecha_fin=form.fecha_fin.data,
            activa=form.activa.data,
        )
        db.session.add(cuota)
        db.session.flush()

        # Generar recibos automáticamente
        recibos = cuota.generar_recibos(g.tenant_id)
        db.session.commit()
        flash(f'Cuota creada. Se han generado {len(recibos)} recibos.', 'success')
        return redirect(url_for('socios.cuotas'))

    return render_template('socios/cuota_form.html', form=form, titulo='Nueva cuota')

@socios_bp.route('/cuotas/<uuid:cuota_id>/editar/', methods=['GET', 'POST'])
@socios_required
def cuota_editar(cuota_id):
    if not g.user.tiene_permiso('cuotas.editar'):
        flash('No tienes permiso para editar cuotas.', 'danger')
        return redirect(url_for('socios.cuotas'))

    cuota = Cuota.query.filter_by(id=cuota_id, tenant_id=g.tenant_id).first_or_404()
    form = CuotaForm(obj=cuota)
    tipos = TipoSocio.for_tenant(g.tenant_id).all()
    form.tipo_socio_id.choices = [(str(t.id), t.nombre) for t in tipos]

    if request.method == 'GET':
        form.tipo_socio_id.data = str(cuota.tipo_socio_id)

    if form.validate_on_submit():
        cuota.tipo_socio_id = form.tipo_socio_id.data
        cuota.descripcion = form.descripcion.data.strip()
        cuota.importe = form.importe.data
        cuota.fecha_inicio = form.fecha_inicio.data
        cuota.fecha_fin = form.fecha_fin.data
        cuota.activa = form.activa.data
        db.session.commit()
        flash('Cuota actualizada correctamente', 'success')
        return redirect(url_for('socios.cuotas'))

    return render_template('socios/cuota_form.html', form=form, titulo='Editar cuota')

# ---- Recibos ----------------------------------------------------------------

@socios_bp.route('/recibos/')
@socios_required
def recibos():
    estado = request.args.get('estado', 'pendiente')
    query = Recibo.query.filter_by(tenant_id=g.tenant_id)
    if estado != 'todos':
        query = query.filter_by(estado=estado)
    recibos = query.order_by(Recibo.fecha_emision.desc()).all()
    return render_template('socios/recibos.html', recibos=recibos, estado=estado)

@socios_bp.route('/recibos/<uuid:recibo_id>/pagar/', methods=['GET', 'POST'])
@socios_required
def recibo_pagar(recibo_id):
    if not g.user.tiene_permiso('tesoreria.cobrar'):
        flash('No tienes permiso para registrar cobros', 'danger')
        return redirect(url_for('socios.recibos'))

    recibo = Recibo.query.filter_by(id=recibo_id, tenant_id=g.tenant_id).first_or_404()

    if recibo.estado == 'pagado':
        flash('Este recibo ya está pagado', 'warning')
        return redirect(url_for('socios.recibos'))

    form = PagoReciboForm()

    if form.validate_on_submit():
        recibo.registrar_pago(
            fecha=form.fecha_pago.data,
            metodo=form.metodo_pago.data,
            notas=form.notas.data,
        )
        if form.descuento.data:
            recibo.descuento = form.descuento.data
            recibo.motivo_descuento = form.motivo_descuento.data
        db.session.commit()
        flash(f'Pago del recibo {recibo.numero_recibo} registrado correctamente', 'success')
        return redirect(url_for('socios.recibos'))

    return render_template('socios/recibo_pagar.html', form=form, recibo=recibo)

@socios_bp.route('/recibos/<uuid:recibo_id>/anular/', methods=['POST'])
@socios_required
def recibo_anular(recibo_id):
    if not g.user.tiene_permiso('tesoreria.recibos.eliminar'):
        flash('No tienes permiso para anula recibos.', 'danger')
        return redirect(url_for('socios.recibos'))

    recibo = Recibo.query.filter_by(id=recibo_id, tenant_id=g.tenant_id).first_or_404()
    recibo.estado = 'anulado'
    db.session.commit()
    flash(f'Recibo {recibo.numero_recibo} anulado', 'success')
    return redirect(url_for('socios.recibos'))

# ---- Configuración ----------------------------------------------------------------

@socios_bp.route('/config/', methods=['GET', 'POST'])
@socios_required
def config():
    if not g.user.tiene_permiso('admin.roles'):
        flash('No tienes permiso para modificar la configuración', 'danger')
        return redirect(url_for('socios.index'))

    cfg = SociosConfig.for_tenant(g.tenant_id)
    form = SociosConfigForm(obj=cfg)

    if form.validate_on_submit():
        cfg.musicos_pueden_ser_socios = form.musicos_pueden_ser_socios.data
        cfg.un_socio_por_unidad_familiar = form.un_socio_por_unidad_familiar.data
        cfg.max_tutores_menor = int(form.max_tutores_menor.data)
        cfg.descuento_unidad_familiar = form.descuento_unidad_familiar.data
        cfg.tipo_descuento_escuela = form.tipo_descuento_escuela.data or None
        cfg.valor_descuento_escuela = form.valor_descuento_escuela.data
        db.session.commit()
        flash('Configuración guardada correctamente', 'success')
        return redirect(url_for('socios.config'))

    return render_template('socios/config.html', form=form)