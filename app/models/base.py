from flask import g
from sqlalchemy import event
from sqlalchemy.orm import Query

from app import db

class TenantQuery(Query):
    """ Query personalizada que aplica filtro tenant_id automáticamente """

    def get(self, ident):
        obj = super().get(ident)
        if obj is None:
            return None
        tenant_id = getattr(g, 'tenant_id', None)
        if tenant_id and str(getattr(obj, 'tenant_id', None)) != str(tenant_id):
            return None
        return obj

class TenantMixin:
    """
    Mixin que añade Tenant_id a cualquier modelo y filtra queries
    automáticamente según el tenant activo en el contexto (g.tenant_id)
    """
    tenant_id = db.Column(
        db.UUID(as_uuid=True),
        db.ForeignKey('tenants.id'),
        nullable=False,
        index=True,
    )

    @classmethod
    def for_tenant(cls, tenant_id):
        """ Devuelve una query filtrada por el tenant_id explícito. """
        return cls.query.filter_by(tenant_id=tenant_id)

    @classmethod
    def current_tenant(cls):
        """ Devuelve una query filtrada por el tenant activo en g. """
        tenant_id = None

        try:
            tenant_id = g.tenant_id
        except AttributeError:
            pass

        if tenant_id is None:
            raise RuntimeError(
                f'No hay tenant activo en el contexto al consultar {cls.__name__}.'
                ' Asegúrate de que TenantMiddleware está configurado.'
            )
        return cls.query.filter_by(tenant_id=tenant_id)

class TimestampMixin:
    """ Añade created_at y updated_at a cualquier modelo. """
    created_at = db.Column(
        db.DateTime(timezone=True),
        server_default=db.func.now(),
        nullable=False,
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        server_default=db.func.now(),
        onupdate=db.func.now(),
        nullable=False,
    )