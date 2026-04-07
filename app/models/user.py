import uuid
import secrets
from datetime import datetime, timezone, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

from app import db
from app.models.base import TimestampMixin


class Identity(TimestampMixin, db.Model):
    """
    Representa a una persona física en un sistema.
    Es independiente de cualquier agrupación - una persona
    puede pertenecer a varias agrupaciones con una sola identidad.
    """
    __tablename__ = 'identities'

    id = db.Column(db.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    nombre = db.Column(db.String(128), nullable=False)
    apellidos = db.Column(db.String(128), nullable=True)
    activo = db.Column(db.Boolean, nullable=False, default=True)

    memberships = db.relationship('TenantMember', back_populates='identity',
                                  cascade='all, delete-orphan', lazy='dynamic')
    sessions = db.relationship('Session', back_populates='identity',
                               cascade='all, delete-orphan', lazy='dynamic')
    invitaciones = db.relationship('Invitacion', back_populates='identity',
                                   cascade='all, delete-orphan', lazy='dynamic',
                                   foreign_keys='Invitacion.identity_id')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_member(self, tenant_id):
        """ Devuelve el TenantMember de esta identidad un un tenant concreto. """
        return TenantMember.query.filter_by(
            identity_id=self.id,
            tenant_id=tenant_id,
            activo=True,
        ).first()

    def __repr__(self):
        return f'<Identity {self.email}'


class TenantMember(db.Model):
    """
    Representa la pertenencia de una identidad a una agrupación concreta.
    Aquí viven los roles y permisos individuales - no en identity.
    """
    __tablename__ = 'tenant_members'

    id = db.Column(db.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    identity_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey('identities.id'),
                            nullable=False, index=True)
    tenant_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey('tenants.id'),
                          nullable=False, index=True)
    activo = db.Column(db.Boolean, nullable=False, default=True)
    joined_at = db.Column(db.DateTime(timezone=True),
                          server_default=db.func.now(), nullable=False)

    identity = db.relationship('Identity', back_populates='memberships')
    tenant = db.relationship('Tenant', back_populates='members')
    member_roles = db.relationship('MemberRole', back_populates='member',
                                   cascade='all, delete-orphan', lazy='dynamic')
    member_permisos = db.relationship('MemberPermiso', back_populates='member',
                                      cascade='all, delete-orphan', lazy='dynamic')

    __table_args__ = (
        db.UniqueConstraint('identity_id', 'tenant_id', name='uq_identity_tenant'),
    )

    @property
    def nombre(self):
        return self.identity.nombre

    @property
    def apellidos(self):
        return self.identity.apellidos

    @property
    def email(self):
        return self.identity.email

    @property
    def permisos(self):
        """
        Devuelve el conjunto completo de permisos del miembro:
        unión de los permisos de sus roles más sus permisos individuales.
        """
        from sqlalchemy.orm import object_session
        perms = set()

        s = object_session(self)
        if s is None:
            return perms

        for mr in s.query(MemberRole).filter_by(member_id=self.id).all():
            perms.update(mr.role.permisos_json or [])

        for mp in s.query(MemberPermiso).filter_by(member_id=self.id).all():
            perms.add(mp.permiso)

        return perms

    def tiene_permiso(self, permiso):
        return permiso in self.permisos

    def __repr__(self):
        return f'<TenantMember identity={self.identity_id} tenant={self.tenant_id}>'


class Session(db.Model):
    __tablename__ = 'sessions'

    id = db.Column(db.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    identity_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey('identities.id'),
                        nullable=False, index=True)
    tenant_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey('tenants.id'),
                          nullable=False, index=True)
    session_token = db.Column(db.String(255), unique=True, nullable=False, index=True)
    expired_at = db.Column(db.DateTime(timezone=True), nullable=False)
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True),
                           server_default=db.func.now(), nullable=False)

    identity = db.relationship('Identity', back_populates='sessions')

    def __repr__(self):
        return f'<Session identity={self.identity_id} tenant={self.tenant_id}>'


class Role(db.Model):
    __tablename__ = 'roles'

    id = db.Column(db.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey('tenants.id'),
                          nullable=False, index=True)
    nombre = db.Column(db.String(128), nullable=False)
    permisos_json = db.Column(db.JSON, nullable=True, default=list)
    es_sistema = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime(timezone=True),
                           server_default=db.func.now(), nullable=False)

    tenant = db.relationship('Tenant', back_populates='roles')
    member_roles = db.relationship('MemberRole', back_populates='role',
                                 cascade='all, delete-orphan', lazy='dynamic')

    @classmethod
    def for_tenant(cls, tenant_id):
        return cls.query.filter_by(tenant_id=tenant_id)

    @classmethod
    def current_tenant(cls):
        from flask import g
        try:
            tenant_id = g.tenant_id
        except AttributeError:
            raise RuntimeError(
                f'No hay tenant activo en el contexto al consultar {cls.__name__}.'
            )
        if tenant_id is None:
            raise RuntimeError(
                f'No hay tenant activo en el contexto al consultar {cls.__name__}.'
            )
        return cls.query.filter_by(tenant_id=tenant_id)

    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'nombre', name='uq_role_nombre_per_tenant'),
    )

    def __repr__(self):
        return f'<Role {self.nombre}>'


class MemberRole(db.Model):
    __tablename__ = 'member_roles'

    id = db.Column(db.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    member_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey('tenant_members.id'),
                        nullable=False, index=True)
    role_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey('roles.id'),
                        nullable=False)
    assigned_at = db.Column(db.DateTime(timezone=True),
                            server_default=db.func.now(), nullable=False)

    member = db.relationship('TenantMember', back_populates='member_roles')
    role = db.relationship('Role', back_populates='member_roles')

    __table_args__ = (
        db.UniqueConstraint('member_id', 'role_id', name='uq_member_role'),
    )

    def __repr__(self):
        return f'<MemberRole member={self.member_id} role={self.role_id}>'


class MemberPermiso(db.Model):
    """ Permiso individual adicional asignado a un miembro concreto. """
    __tablename__ = 'member_permisos'

    id = db.Column(db.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    member_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey('tenant_members.id'),
                          nullable=False, index=True)

    permiso = db.Column(db.String(128), nullable=False)
    motivo = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True),
                           server_default=db.func.now(), nullable=False)

    member = db.relationship('TenantMember', back_populates='member_permisos')

    __table_args__ = (
        db.UniqueConstraint('member_id', 'permiso', name='uq_member_permiso'),
    )

    def __repr__(self):
        return f'<MemberPermiso {self.permiso} member={self.member_id}>'


class Invitacion(db.Model):
    """
    Token de invitación para incorporar un nuevo usuario a una agrupación.
    """
    __tablename__ = 'invitaciones'

    ESTADOS = ('pendiente', 'aceptada', 'caducada')
    TTL_HORAS = 72

    id = db.Column(db.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey('tenants.id'),
                          nullable=False, index=True)
    email = db.Column(db.String(255), nullable=False, index=True)
    nombre = db.Column(db.String(128), nullable=True)
    token = db.Column(db.String(64), unique=True, nullable=False, index=True)
    estado = db.Column(db.String(16), nullable=False, default='pendiente')
    invitado_por = db.Column(db.UUID(as_uuid=True), db.ForeignKey('tenant_members.id'),
                             nullable=False)
    identity_id = db.Column(db.UUID(as_uuid=True), db.ForeignKey('identities.id'),
                            nullable=True)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True),
                           server_default=db.func.now(), nullable=False)
    accepted_at = db.Column(db.DateTime(timezone=True), nullable=True)

    tenant = db.relationship('Tenant')
    invitador = db.relationship('TenantMember', foreign_keys=[invitado_por])
    identity = db.relationship('Identity', back_populates='invitaciones',
                               foreign_keys=[identity_id])

    @staticmethod
    def generar_token():
        return secrets.token_urlsafe(32)

    @classmethod
    def crear(cls, tenant_id, email, nombre, invitado_por_id):
        """ Crea una nueva invitación pendiente con token y caducidad """
        expires = datetime.now(timezone.utc) + timedelta(hours=cls.TTL_HORAS)
        inv = cls(
            tenant_id=tenant_id,
            email=email.strip().lower(),
            nombre=nombre.strip() if nombre else None,
            token=cls.generar_token(),
            estado='pendiente',
            invitado_por=invitado_por_id,
            expires_at=expires,
        )
        return inv

    @property
    def ha_caducado(self):
        return datetime.now(timezone.utc) > self.expires_at

    @property
    def es_valida(self):
        return self.estado == 'pendiente' and not self.ha_caducado

    def marcar_aceptada(self, identity_id):
        self.estado = 'aceptada'
        self.identity_id = identity_id
        self.accepted_at = datetime.now(timezone.utc)

    def __repr__(self):
        return f'<Invitacion {self.email} estado={self.estado}>'