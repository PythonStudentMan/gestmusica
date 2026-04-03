import uuid
from datetime import date
from app import db
from app.models.base import TimestampMixin


class SociosConfig(db.Model):
    """ Configuración del módulo SOCIOS por tenant. """
    __tablename__ = 'socios_config'

    id = db.Column(db.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey('tenants.id'),
                          nullable=False, unique=True, index=True)
    musicos_pueden_ser_socios = db.Column(db.Boolean, nullable=False, default=True)
    un_socio_por_unidad_familiar = db.Column(db.Boolean, nullable=False, default=False)
    max_tutores_menor = db.Column(db.Integer, nullable=False, default=2)
    descuento_unidad_familiar = db.Column(db.Boolean, nullable=False, default=False)
    tipo_descuento_escuela = db.Column(db.String(16), nullable=True)
    valor_descuento_escuela = db.Column(db.Numeric(10, 2), nullable=True)
    updated_at = db.Column(db.DateTime(timezone=True),
                           server_default=db.func.now(),
                           onupdate=db.func.now(), nullable=False)

    tenant = db.relationship('Tenant')

    @classmethod
    def for_tenant(cls, tenant_id):
        """ Devuelve la config del tenant, creándola con valores por defecto si no existe """
        config = cls.query.filter_by(tenant_id=tenant_id).first()
        if config is None:
            config = cls(tenant_id=tenant_id)
            db.session.add(config)
            db.session.flush()
        return config

    def __repr__(self):
        return f'<SociosConfig tenant={self.tenant_id}>'


class UnidadFamiliar(TimestampMixin, db.Model):
    __tablename__ = 'unidades_familiares'

    id = db.Column(db.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey('tenants.id'),
                          nullable=False, index=True)
    nombre = db.Column(db.String(255), nullable=False)

    tenant = db.relationship('Tenant')
    socios = db.relationship('Socio', back_populates='unidad_familiar', lazy='dynamic')

    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'nombre', name='uq_unidad_familiar_nombre'),
    )

    def __repr__(self):
        return f'<UnidadFamiliar {self.nombre}>'


class Persona(TimestampMixin, db.Model):
    """
    Representa a cualquier persona física relacionada con la agrupación.
    Puede ser socio, músico, educando, tutor o cualquier combinación
    """
    __tablename__ = 'personas'

    id = db.Column(db.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey('tenants.id'),
                          nullable=False, index=True)
    identity_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey('identities.id'),
                            nullable=True, index=True)
    nombre = db.Column(db.String(128), nullable=False)
    apellidos = db.Column(db.String(128), nullable=False)
    email = db.Column(db.String(255), nullable=True)
    telefono = db.Column(db.String(32), nullable=True)
    fecha_nacimiento = db.Column(db.Date, nullable=True)
    es_menor = db.Column(db.Boolean, nullable=False, default=False)
    dni = db.Column(db.String(16), nullable=True)

    tenant = db.relationship('Tenant')
    identity = db.relationship('Identity')
    socio = db.relationship('Socio', back_populates='persona',
                            uselist=False, lazy='select')
    tutores = db.relationship('TutorLegal',
                              foreign_keys='TutorLegal.persona_menor_id',
                              back_populates='menor', lazy='dynamic')
    tutelados = db.relationship('TutorLegal',
                                foreign_keys='TutorLegal.persona_tutor_id',
                                back_populates='tutor', lazy='dynamic')

    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'dni', name='uq_persona_dni_per_tenant'),
    )

    @property
    def nombre_completo(self):
        return f'{self.apellidos}, {self.nombre}'

    def actualizar_es_menor(self):
        """ Recalcula es_menor a partir de fecha_nacimiento """
        if self.fecha_nacimiento:
            hoy = date.today()
            edad = hoy.year - self.fecha_nacimiento.year - (
                (hoy.month, hoy.day) < (self.fecha_nacimiento.month, self.fecha_nacimiento.day)
            )
            self.es_menor = edad < 18
        else:
            self.es_menor = False

    def __repr__(self):
        return f'<Persona {self.nombre_completo}>'


class TutorLegal(TimestampMixin, db.Model):
    __tablename__ = 'tutores_legales'

    id = db.Column(db.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey('tenants.id'),
                          nullable=False, index=True)
    persona_menor_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey('personas.id'),
                          nullable=False, index=True)
    persona_tutor_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey('personas.id'),
                                 nullable=False, index=True)
    relacion = db.Column(db.String(64), nullable=False)
    patria_potestad = db.Column(db.Boolean, nullable=False, default=True)
    firma_requerida = db.Column(db.Boolean, nullable=False, default=True)

    tenant = db.relationship('Tenant')
    menor = db.relationship('Persona', foreign_keys=[persona_menor_id],
                            back_populates='tutores')
    tutor = db.relationship('Persona', foreign_keys=[persona_tutor_id],
                            back_populates='tutelados')

    __table_args__ = (
        db.UniqueConstraint('persona_menor_id', 'persona_tutor_id', name='uq_tutor_menor'),
    )

    def __repr__(self):
        return f'<TutorLegal {self.relacion}>'


class TipoSocio(TimestampMixin, db.Model):
    __tablename__ = 'tipos_socio'

    id = db.Column(db.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey('tenants.id'),
                          nullable=False, index=True)
    nombre = db.Column(db.String(128), nullable=False)
    descripcion = db.Column(db.Text, nullable=True)
    importe_cuota = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    periodicidad = db.Column(db.String(16), nullable=False, default='anual')
    activo = db.Column(db.Boolean, nullable=False, default=True)

    tenant = db.relationship('Tenant')
    socios = db.relationship('Socio', back_populates='tipo_socio', lazy='dynamic')
    cuotas = db.relationship('Cuota', back_populates='tipo_socio', lazy='dynamic')

    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'nombre', name='uq_tipo_socio_nombre'),
    )

    @classmethod
    def for_tenant(cls, tenant_id):
        return cls.query.filter_by(tenant_id=tenant_id, activo=True).order_by(cls.nombre)

    def __repr__(self):
        return f'<TipoSocio {self.nombre}>'


class Socio(TimestampMixin, db.Model):
    __tablename__ = 'socios'

    id = db.Column(db.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey('tenants.id'),
                          nullable=False, index=True)
    persona_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey('personas.id'),
                           nullable=False, index=True)
    tipo_socio_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey('tipos_socio.id'),
                           nullable=False)
    unidad_familiar_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey('unidades_familiares.id'),
                           nullable=True)
    numero_socio = db.Column(db.String(32), nullable=False)
    fecha_alta = db.Column(db.Date, nullable=False, default=date.today)
    fecha_baja = db.Column(db.Date, nullable=True)
    estado = db.Column(db.String(16), nullable=False, default='activo')
    es_titular_familiar = db.Column(db.Boolean, nullable=False, default=False)

    tenant = db.relationship('Tenant')
    persona = db.relationship('Persona', back_populates='socio')
    tipo_socio = db.relationship('TipoSocio', back_populates='socios')
    unidad_familiar = db.relationship('UnidadFamiliar', back_populates='socios')
    recibos = db.relationship('Recibo', back_populates='socio',
                              cascade='all, delete-orphan', lazy='dynamic')

    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'numero_socio', name='uq_socio_numero'),
    )

    @classmethod
    def for_tenant(cls, tenant_id):
        return cls.query.filter_by(tenant_id=tenant_id)

    @property
    def nombre_completo(self):
        return self.persona.nombre_completo

    def dar_baja(self, fecha=None):
        self.estado = 'baja'
        self.fecha_baja = fecha or date.today()

    def __repr__(self):
        return f'<Socio {self.numero_socio}>'


class Cuota(TimestampMixin, db.Model):
    __tablename__ = 'cuotas'

    id = db.Column(db.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey('tenants.id'),
                          nullable=False, index=True)
    tipo_socio_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey('tipos_socio.id'),
                          nullable=False)
    descripcion = db.Column(db.String(255), nullable=False)
    importe = db.Column(db.Numeric(10, 2), nullable=False)
    fecha_inicio = db.Column(db.Date, nullable=False)
    fecha_fin = db.Column(db.Date, nullable=False)
    activa = db.Column(db.Boolean, nullable=False, default=True)

    tenant = db.relationship('Tenant')
    tipo_socio = db.relationship('TipoSocio', back_populates='cuotas')
    recibos = db.relationship('Recibo', back_populates='cuota', lazy='dynamic')

    @classmethod
    def for_tenant(cls, tenant_id):
        return cls.query.filter_by(tenant_id=tenant_id)

    def generar_recibos(self, tenant_id):
        """
        Genera un recibo por cada socio activo del tipo correspondiente
        que no tenga ya recibo para esta cuota.
        """
        socios = Socio.query.filter_by(
            tenant_id=tenant_id,
            tipo_socio_id=self.tipo_socio_id,
            estado='activo',
        ).all()

        recibos_nuevos = []
        for socio in socios:
            existe = Recibo.query.filter_by(
                socio_id=socio.id,
                cuota_id=self.id,
            ).first()
            if not existe:
                recibo = Recibo(
                    tenant_id=tenant_id,
                    socio_id=socio.id,
                    cuota_id=self.id,
                    numero_recibo=Recibo.generar_numero(tenant_id),
                    importe=self.importe,
                    descuento=0,
                    fecha_emision=date.today(),
                    fecha_vencimiento=self.fecha_fin,
                    estado='pendiente',
                )
                db.session.add(recibo)
                recibos_nuevos.append(recibo)

        return recibos_nuevos

    def __repr__(self):
        return f'<Cuota {self.descripcion}>'


class Recibo(TimestampMixin, db.Model):
    __tablename__ = 'recibos'

    id = db.Column(db.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey('tenants.id'),
                          nullable=False, index=True)
    socio_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey('socios.id'),
                          nullable=False, index=True)
    cuota_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey('cuotas.id'),
                          nullable=False)
    numero_recibo = db.Column(db.String(32), nullable=False)
    importe = db.Column(db.Numeric(10, 2), nullable=False)
    descuento = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    motivo_descuento = db.Column(db.String(255), nullable=True)
    fecha_emision = db.Column(db.Date, nullable=False, default=date.today)
    fecha_vencimiento = db.Column(db.Date, nullable=False)
    estado = db.Column(db.String(16), nullable=False, default='pendiente')
    fecha_pago = db.Column(db.Date, nullable=True)
    metodo_pago = db.Column(db.String(32), nullable=True)
    notas = db.Column(db.Text, nullable=True)

    tenant = db.relationship('Tenant')
    socio = db.relationship('Socio', back_populates='recibos')
    cuota = db.relationship('Cuota', back_populates='recibos')

    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'numero_recibo', name='uq_recibo_numero'),
    )

    @property
    def importe_final(self):
        return float(self.importe) - float(self.descuento)

    @staticmethod
    def generar_numero(tenant_id):
        """ Genera el siguiente número de recibo para el tenant """
        from sqlalchemy import func
        ultimo = db.session.query(func.max(Recibo.numero_recibo)).filter_by(
            tenant_id=tenant_id
        ).scalar()
        if ultimo is None:
            return f'REC-{date.today().year}-0001'
        try:
            partes = ultimo.split('-')
            anio_actual = str(date.today().year)
            if partes[1] == anio_actual:
                siguiente = int(partes[2]) + 1
            else:
                siguiente = 1
            return f'REC-{anio_actual}-{siguiente:04d}'
        except (IndexError, ValueError):
            return f'REC-{date.today().year}-0001'

    def registrar_pago(self, fecha=None, metodo='efectivo', notas=None):
        self.estado = 'pagado'
        self.fecha_pago = fecha or date.today()
        self.metodo_pago = metodo
        if notas:
            self.notas = notas

    def __repr__(self):
        return f'<Recibo {self.numero_recibo}>'