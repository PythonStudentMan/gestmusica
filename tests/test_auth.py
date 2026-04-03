import pytest
import re

from jinja2.runtime import identity

from app import db
from app.models.tenant import Tenant
from app.models.user import Identity, TenantMember, Role, MemberRole


@pytest.fixture(scope='function')
def tenant_con_usuario(db, app):
    import uuid
    slug_unico = f'banda-{uuid.uuid4().hex[:8]}'

    with app.app_context():
        tenant = Tenant(slug=slug_unico, nombre='Banda Test', modo='saas', activo=True)
        db.session.add(tenant)
        db.session.flush()
        db.session.refresh(tenant)

        identity = Identity(
            email=f'admin@{slug_unico}.com',
            nombre='Admin',
        )
        identity.set_password('password123')
        db.session.add(identity)
        db.session.flush()
        db.session.refresh(identity)

        member = TenantMember(identity_id=identity.id, tenant_id=tenant.id, activo=True,)
        db.session.add(member)
        db.session.flush()
        db.session.refresh(member)
        db.session.commit()

        yield tenant, identity, member


class TestLogin:

    def test_login_correcto(self, app, client, tenant_con_usuario):
        """ Login con credenciales correctas. Redirige al dashboard """
        tenant, identity, member = tenant_con_usuario
        response = client.post('/auth/login/', data={
            'slug': tenant.slug,
            'email': identity.email,
            'password': 'password123',
            'csrf_token': _get_csrf_token(client),
        }, follow_redirects=True)

        assert response.status_code == 200
        assert 'Bienvenido' in response.get_data(as_text=True)

    def test_login_slug_incorrecto(self, app, client, tenant_con_usuario):
        """ login con slug inexistente muestra error """
        response = client.post('/auth/login/', data={
            'slug': 'banda-inexistente',
            'email': 'alguien@ejemplo.com',
            'password': 'password123',
            'csrf_token': _get_csrf_token(client),
        }, follow_redirects=True)

        assert response.status_code == 200
        assert 'no encontrada' in response.get_data(as_text=True)

    def test_login_password_incorrecta(self, app, client, tenant_con_usuario):
        """ login con contraseña incorrecta muestra error """
        tenant, identity, member = tenant_con_usuario
        response = client.post('/auth/login/', data={
            'slug': tenant.slug,
            'email': identity.email,
            'password': 'wrongpassword',
            'csrf_token': _get_csrf_token(client),
        }, follow_redirects=True)

        assert response.status_code == 200
        assert 'incorrectos' in response.get_data(as_text=True)

    def test_login_sin_membresia(self, app, client, tenant_con_usuario):
        """ Una identidad que existe pero no pertenece a la agrupación """
        import uuid
        tenant, identity, member = tenant_con_usuario

        with app.app_context():
            otro_tenant = Tenant(
                slug=f'otra-banda-{uuid.uuid4().hex[:6]}',
                nombre='Otra Banda',
                modo='saas',
                activo=True,
            )
            db.session.add(otro_tenant),
            db.session.commit()
            otro_slug = otro_tenant.slug

        response = client.post('/auth/login/', data={
            'slug': otro_slug,
            'email': identity.email,
            'password': 'password123',
            'csrf_token': _get_csrf_token(client),
        }, follow_redirects=True)
        assert response.status_code == 200
        assert 'No tienes acceso' in response.get_data(as_text=True)

    def test_logout(self, app, client, tenant_con_usuario):
        """ logout limpia la sesión y redirige al login """
        tenant, identity, member = tenant_con_usuario
        # Primero login
        response = client.post('/auth/login/', data={
            'slug': tenant.slug,
            'email': identity.email,
            'password': 'password123',
            'csrf_token': _get_csrf_token(client),
        }, follow_redirects=True)

        # Luego logout
        response = client.get('/auth/logout/', follow_redirects=True)
        assert response.status_code == 200
        assert 'cerrado sesión' in response.get_data(as_text=True)

    def test_dashboard_sin_login_redirige(self, app, client):
        """ Acceder al dashboard sin lgin redirige al login """
        response = client.get('/auth/dashboard/', follow_redirects=False)
        assert response.status_code == 302
        assert '/auth/login' in response.headers['Location']

def _get_csrf_token(client):
    """ Obtiene el token CSRF del formulario de login. """
    response = client.get('/auth/login')
    html = response.get_data(as_text=True)
    import re
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    return match.group(1) if match else ''


