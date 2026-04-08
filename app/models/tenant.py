import uuid
from app import db
from app.models.base import TimestampMixin

class Tenant(TimestampMixin, db.Model):
    __tablename__ = 'tenants'

    id = db.Column(db.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug = db.Column(db.String(64), unique=True, nullable=False, index=True)
    nombre = db.Column(db.String(255), nullable=False)
    modo = db.Column(db.String(16), nullable=False, default='saas')   # 'saas' | 'standalone'
    activo = db.Column(db.Boolean, nullable=False, default=True)

    # Relaciones
    config = db.relationship('TenantConfig', back_populates='tenant',
                             cascade='all, delete-orphan', lazy='dynamic')
    members = db.relationship('TenantMember', back_populates='tenant',
                            cascade='all, delete-orphan', lazy='dynamic')
    roles = db.relationship('Role', back_populates='tenant',
                            cascade='all, delete-orphan', lazy='dynamic')
    modules = db.relationship('TenantModule', back_populates='tenant',
                            cascade='all, delete-orphan', lazy='dynamic')
    subagrupaciones = db.relationship('Subagrupacion', back_populates='tenant',
                                      cascade='all, delete-orphan', lazy='dynamic')

    def has_module(self, codigo):
        from app.models.tenant import TenantModule, Module
        return TenantModule.query.join(TenantModule.module).filter(
            TenantModule.tenant_id == self.id,
            TenantModule.activo == True,
            Module.codigo == codigo,
        ).count() > 0

    def __repr__(self):
        return f'<Tenant {self.slug}>'


class TenantConfig(db.Model):
    __tablename__ = 'tenant_config'

    id = db.Column(db.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey('tenants.id'),
                          nullable=False, index=True)
    clave = db.Column(db.String(128), nullable=False)
    valor = db.Column(db.Text, nullable=True)
    updated_at = db.Column(db.DateTime(timezone=True),
                           server_default=db.func.now(),
                           onupdate=db.func.now(), nullable=False)

    tenant = db.relationship('Tenant', back_populates='config')

    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'clave', name='uq_tenant_config_clave'),
    )

    def __repr__(self):
        return f'<TenantConfig {self.clave}={self.valor}>'

class Module(db.Model):
    __tablename__ = 'modules'

    id = db.Column(db.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    codigo = db.Column(db.String(32), unique=True, nullable=False, index=True)
    nombre = db.Column(db.String(128), nullable=False)
    descripcion = db.Column(db.Text, nullable=True)
    activo = db.Column(db.Boolean, nullable=False, default=True)

    tenant_modules = db.relationship('TenantModule', back_populates='module')

    def __repr__(self):
        return f'<Module {self.codigo}>'

class TenantModule(db.Model):
    __tablename__ = 'tenant_modules'

    id = db.Column(db.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey('tenants.id'),
                          nullable=False, index=True)
    module_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey('modules.id'),
                          nullable=False)
    activo = db.Column(db.Boolean, nullable=False, default=True)
    config_json = db.Column(db.JSON, nullable=True)
    activated_at = db.Column(db.DateTime(timezone=True),
                             server_default=db.func.now(), nullable=False)

    tenant = db.relationship('Tenant', back_populates='modules')
    module = db.relationship('Module', back_populates='tenant_modules')

    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'module_id', name='uq_tenant_module'),
    )

    def __repr__(self):
        return f'<TenantModule tenant={self.tenant_id} module={self.module_id}>'


class Subagrupacion(db.Model):
    __tablename__ = 'subagrupaciones'

    id = db.Column(db.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey('tenants.id'),
                          nullable=False, index=True)
    nombre = db.Column(db.String(255), nullable=False)
    descripcion = db.Column(db.Text, nullable=True)
    activa = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime(timezone=True),
                           server_default=db.func.now(), nullable=False)

    tenant = db.relationship('Tenant', back_populates='subagrupaciones')
    musicos = db.relationship('MusicoSubagrupacion', back_populates='subagrupacion', lazy='dynamic')

    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'nombre', name='uq_subagrupacion_nombre_per_tenant'),
    )

    def __repr__(self):
        return f'<Subagrupacion {self.nombre}>'