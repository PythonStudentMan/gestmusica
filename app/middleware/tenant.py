from flask import g, request, abort
from app.models.tenant import Tenant
import os

class TenantMiddleware:
    """
    Detecta el tenant activo en cada request e inyecta
    g.tenant y g.tenant_id en el contexto de Flask

    Modos de detección (controlados por APP_MODE):
       - saas:        subdominio en la URL
       - standalone:  tenant fijo desde variable de entorno STANDALONE_TENANT_SLUG
       - login:       slug introducido por el usuario (asignado tras el login)
    """

    def __init__(self, app=None):
        self.app = app
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        app.before_request(self._detect_tenant)

    def _detect_tenant(self):
        from flask import request as flask_request
        try:
            mode = os.environ.get('APP_MODE', 'saas')
        except RuntimeError:
            return

        if mode == 'standalone':
            self._load_from_env()
        elif mode == 'saas':
            self._load_from_subdomain()
        # En modo 'login' el tenant se asigna manualmente tras autenticación
        # No hacemos nada aquí - la vista de login llamará a set_tenant()

    def _load_from_env(self):
        """ Modo stadalone: tenant fijo desde STANDALONE_TENANT_SLUG """
        slug = os.environ.get('STANDALONE_TENANT_SLUG')
        if not slug:
            raise RuntimeError(
                'APP_MODE=standalone requiere definir STANDALONE_TENANT_SLUG en .env'
            )
        self._set_tenant_by_slug(slug)

    def _load_from_subdomain(self):
        """ Modo saas: extrae el slug del subdominio de la URL """
        try:
            host = request.host.split(':')[0] # Quitar puerto si lo hay
        except RuntimeError:
            return

        # Si es una IP, no hay subdominio - ignorar
        import re
        if re.match(r'^\d{1,3}(\.\d{1,3}){3}$', host):
            return

        # Si es localhost, no hay subdominio - ignorar
        if host == 'localhost':
            return

        parts = host.split('.')

        # Necesitamos al menos subdominio.dominio.tld
        if len(parts) < 3:
            return

        slug = parts[0]

        # Ignorar subdominios reservados
        if slug in ('www', 'api', 'admin', 'static'):
            return

        self._set_tenant_by_slug(slug)

    def _set_tenant_by_slug(self, slug):
        """ Carga el tenant de la BD y lo inyecta en g. """
        tenant = Tenant.query.filter_by(slug=slug, activo=True).first()
        if tenant is None:
            abort(404, description=f'Agrupacion "{slug}" no encontrada o inactiva.')
        set_tenant(tenant)

def set_tenant(tenant):
    """
    Inyecta el tenant en el contexto de Flask.
    Se puede llamar manualmente desde la vista de login.
    """
    g.tenant = tenant
    g.tenant_id = tenant.id

def get_current_tenant():
    """ Devuelve el tenant activo o None si no hay ninguno """
    return getattr(g, 'tenant', None)

def require_tenant(f):
    """
    Decorador para vistas que requieren tenant activo.
    Aborta con 400 si no hay tenant en el contexto.
    """
    from functools import wraps

    @wraps(f)
    def decorated(*args, **kwargs):
        if get_current_tenant() is None:
            abort(400, description='No hay agrupación activa en esta sesión.')
        return f(*args, **kwargs)

    return decorated