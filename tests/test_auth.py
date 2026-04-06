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

@pytest.fixture(scope='function')
def usuario_dos_agrupaciones(db, app):
    """Una identidad que pertenece a dos tenants. """
    import uuid
    slug_a = f'banda-a-{uuid.uuid4().hex[:6]}'
    slug_b = f'banda-b-{uuid.uuid4().hex[:6]}'

    with app.app_context():
        tenant_a = Tenant(slug=slug_a, nombre='Banda A', modo='saas', activo=True)
        tenant_b = Tenant(slug=slug_b, nombre='Banda B', modo='saas', activo=True)
        db.session.add_all([tenant_a, tenant_b])
        db.session.flush()
        db.session.refresh(tenant_a)
        db.session.refresh(tenant_b)

        identity = Identity(email=f'multi-{uuid.uuid4().hex[:8]}@test.com', nombre='Usuario Multi')
        identity.set_password('password123')
        db.session.add(identity)
        db.session.flush()
        db.session.refresh(identity)

        m_a = TenantMember(identity_id=identity.id, tenant_id=tenant_a.id, activo=True)
        m_b = TenantMember(identity_id=identity.id, tenant_id=tenant_b.id, activo=True)
        db.session.add_all([m_a, m_b])
        db.session.commit()

        yield identity, tenant_a, tenant_b

def _get_csrf(client, url='/auth/login/'):
    html = client.get(url).get_data(as_text=True)
    m = re.search(r'name="csrf_token" value="([^"]+)"', html)
    return m.group(1) if m else ''

def _login(client, email, password='password123'):
    csrf = _get_csrf(client)
    return client.post('/auth/login/', data={
        'email': email,
        'password': password,
        'csrf_token': csrf,
    }, follow_redirects=True)


class TestLogin:

    def test_login_correcto_una_agrupacion(self, app, client, tenant_con_usuario):
        """ Login con una sola agrupación. Redirige al dashboard """
        tenant, identity, member = tenant_con_usuario
        r = _login(client, identity.email)
        assert r.status_code == 200
        assert 'Bienvenido' in r.get_data(as_text=True)

    def test_login_password_incorrecta(self, app, client, tenant_con_usuario):
        """ login con contraseña incorrecta muestra error """
        tenant, identity, member = tenant_con_usuario
        r = _login(client, identity.email, password='wrongpassword')
        assert r.status_code == 200
        assert 'incorrectos' in r.get_data(as_text=True)

    def test_login_email_inexistente(self, app, client):
        """ Email que no existe muestra error genéerico. """
        r = _login(client, 'nadie@noexiste.com')
        assert r.status_code == 200
        assert 'incorrectos' in r.get_data(as_text=True)

    def test_login_sin_membresia(self, app, client, tenant_con_usuario):
        """ Una identidad que existe pero no pertenece a la agrupación """
        import uuid
        with app.app_context():
            identity_huerfana = Identity(
                email=f'huerfano@test.com',
                nombre='Huérfano'
            )
            identity_huerfana.set_password('password123')
            db.session.add(identity_huerfana)
            db.session.commit()

        r = _login(client, 'huerfano@test.com')
        assert r.status_code == 200
        assert 'acceso' in r.get_data(as_text=True).lower()

    def test_login_multi_agrupacion_muestra_selector(self, app, client, usuario_dos_agrupaciones):
        """ Con dos agrupaciones se redirige al selector. """
        identity, tenant_a, tenant_b = usuario_dos_agrupaciones
        csrf = _get_csrf(client)
        r = client.post('/auth/login/', data={
            'email': identity.email,
            'password': 'password123',
            'csrf_token': csrf,
        }, follow_redirects=True)
        assert r.status_code == 200
        html = r.get_data(as_text=True)
        assert 'Selecciona una agrupación' in html
        assert 'Banda A' in html
        assert 'Banda B' in html

    def test_login_multi_agrupacion_seleccion_correcta(self, app, client, usuario_dos_agrupaciones):
        """ Seleccionar una agrupación completa el login """
        identity, tenant_a, tenant_b = usuario_dos_agrupaciones

        csrf = _get_csrf(client)
        client.post('/auth/login/', data={
            'email': identity.email,
            'password': 'password123',
            'csrf_token': csrf,
        }, follow_redirects=True)

        csrf2 = _get_csrf(client, '/auth/seleccionar/')
        r = client.post('/auth/seleccionar/', data={
            'tenant_id': str(tenant_a.id),
            'csrf_token': csrf2,
        }, follow_redirects=True)
        assert r.status_code == 200
        assert 'Bienvenido' in r.get_data(as_text=True)

    def test_selector_sin_pending_redirige_login(self, app, client):
        """ Acceder al selector sin haber pasado por login redirige al login """
        r = client.get('/auth/seleccionar/', follow_redirects=True)
        assert r.status_code == 200
        assert 'Iniciar sesión' in r.get_data(as_text=True)

    def test_logout(self, app, client, tenant_con_usuario):
        """ logout limpia la sesión y redirige al login """
        tenant, identity, member = tenant_con_usuario
        # Primero login
        _login(client, identity.email)
        # Luego logout
        response = client.get('/auth/logout/', follow_redirects=True)
        assert response.status_code == 200
        assert 'cerrado sesión' in response.get_data(as_text=True)

    def test_dashboard_sin_login_redirige(self, app, client):
        """ Acceder al dashboard sin lgin redirige al login """
        response = client.get('/auth/dashboard/', follow_redirects=False)
        assert response.status_code == 302
        assert '/auth/login' in response.headers['Location']

    def test_ya_autenticado_redirige_dashboard(self, app, client, tenant_con_usuario):
        """ Si ya estás logado, GET /login/ redirige al dashboard """
        tenant, identity, member = tenant_con_usuario
        _login(client, identity.email)

        r = client.get('/auth/login/', follow_redirects=False)
        assert r.status_code == 302
        assert 'dashboard' in r.headers['Location']

    def test_usuario_inactivo_no_puede_entrar(self, app, client, db, tenant_con_usuario):
        """ Una identidad desactivada no puede iniciar sesión """
        tenant, identity, member = tenant_con_usuario
        with app.app_context():
            ident = db.session.get(Identity, identity.id)
            ident.activo = False
            db.session.commit()

        r = _login(client, identity.email)
        assert r.status_code == 200
        assert 'incorrectos' in r.get_data(as_text=True)

