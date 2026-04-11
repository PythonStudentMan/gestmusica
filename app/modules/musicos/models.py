import uuid
from datetime import date
from app import db
from app.models.base import TimestampMixin


class Instrumento(TimestampMixin, db.Model):
    """ Catálogo de instrumentos por Tenant """
    __tablename__ = 'instrumentos'

    id = db.Column(db.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey('tenants.id'),
                          nullable=False, index=True)
    nombre = db.Column(db.String(64), nullable=False)
    familia = db.Column(db.String(32), nullable=True)
    activo = db.Column(db.Boolean, nullable=False, default=True)

    tenant = db.relationship('Tenant')

    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'nombre', name='uq_instrumento_nombre_tenant'),
    )

    @classmethod
    def for_tenant(cls, tenant_id):
        return cls.query.filter_by(tenant_id=tenant_id, activo=True).order_by(cls.nombre)

    def __repr__(self):
        return f'<Instrumento {self.nombre}>'


class Musico(TimestampMixin, db.Model):
    """ Músico perteneciente a una agrupación """
    __tablename__ = 'musicos'

    id = db.Column(db.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey('tenants.id'),
                          nullable=False, index=True)
    persona_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey('personas.id'),
                           nullable=False, index=True)
    identity_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey('identities.id'),
                            nullable=False, index=True)

    fecha_ingreso = db.Column(db.Date, nullable=False, default=date.today)
    fecha_baja = db.Column(db.Date, nullable=True)
    estado = db.Column(db.String(16), nullable=False, default='activo')
    observaciones = db.Column(db.Text, nullable=True)

    tenant = db.relationship('Tenant')
    persona = db.relationship('Persona', back_populates='musico')
    identity = db.relationship('Identity')
    subagrupaciones = db.relationship('MusicoSubagrupacion', back_populates='musico',
                                      lazy='dynamic')
    instrumentos = db.relationship('MusicoInstrumento', back_populates='musico',
                                   lazy='dynamic')

    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'persona_id', name='uq_musico_persona_tenant'),
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
        return f'<Músico {self.persona.nombre_completo if self.persona else self.id}>'


class MusicoSubagrupacion(TimestampMixin, db.Model):
    """ Asignación de un músico a una subagrupación con un instrumento específico """
    __tablename__ = 'musico_subagrupacion'

    id = db.Column(db.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    musico_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey('musicos.id'),
                          nullable=False, index=True)
    subagrupacion_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey('subagrupaciones.id'),
                                 nullable=False, index=True)
    instrumento_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey('instrumentos.id'),
                               nullable=False, index=True)

    fecha_inicio = db.Column(db.Date, nullable=False, default=date.today)
    fecha_fin = db.Column(db.Date, nullable=True)
    rol = db.Column(db.String(32), nullable=True)
    activo = db.Column(db.Boolean, nullable=False, default=True)

    musico = db.relationship('Musico', back_populates='subagrupaciones')
    subagrupacion = db.relationship('Subagrupacion', back_populates='musicos')
    instrumento = db.relationship('Instrumento')

    __table_args__ = (
        db.UniqueConstraint('musico_id', 'subagrupacion_id', 'fecha_inicio',
                            name='uq_musico_subagrupacion_activa'),
    )

    def finalizar(self, fecha=None):
        self.activo = False
        self.fecha_fin = fecha or date.today()

    def __repr__(self):
        return f'<MusicoSubagrupacion musico={self.musico_id} sub={self.subagrupacion_id}>'


class MusicoInstrumento(TimestampMixin, db.Model):
    """ Habilidades del músico: instrumentos que sabe tocar """
    __tablename__ = 'musico_instrumento'

    id = db.Column(db.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    musico_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey('musicos.id'),
                          nullable=False, index=True)
    instrumento_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey('instrumentos.id'),
                               nullable=False, index=True)

    nivel = db.Column(db.String(16), nullable=True)
    activo = db.Column(db.Boolean, nullable=False, default=True)

    musico = db.relationship('Musico', back_populates='instrumentos')
    instrumento = db.relationship('Instrumento')

    __table_args__ = (
        db.UniqueConstraint('musico_id', 'instrumento_id', name='uq_musico_instrumento'),
    )

    def __repr__(self):
        return f'<MusicoInstrumento musico={self.musico_id} inst={self.instrumento_id}>'