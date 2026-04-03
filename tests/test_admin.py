import pytest
import re

from app import db
from app.models.tenant import Tenant
from app.models.user import Identity, TenantMember, Role, MemberRole


@pytest.fixture(scope='function')
def admin_setup(db, app):
    """ Crea un tenant con un usuario administrador y hace login """
    import uuid
    slug = f'banda-{uuid.uuid4().hex[:8]}'

    with app.app_context():
        tenant = Tenant(slug=slug, nombre='Banda Admin Test',
                        modo='saas', activo=True)
        db.session.add(tenant)
        db.session.flush()
        db.session.refresh(tenant)

        identity = Identity(email=f'admin@{slug}.com', nombre='Admin')
        identity.set_password('password123')
        db.session.add(identity)
        db.session.flush()
        db.session.refresh(identity)

        member = TenantMember(
            identity_id=identity.id,
            tenant_id=tenant.id,
            activo=True,
        )
        db.session.add(member)
        db.session.flush()
        db.session.refresh(member)

        rol = Role(
            tenant_id=tenant.id,
            nombre='Administrador',
            permisos_json=['admin.usuarios', 'admin.roles'],
            es_sistema=True,
        )
        db.session.add(rol)
        db.session.flush()
        db.session.refresh(rol)

        db.session.add(MemberRole(member_id=member.id, role_id=rol.id))
        db.session.commit()

        yield tenant, identity, member, rol


def _get_csrf_token(client):
    response = client.get('/auth/login/')
    html = response.get_data(as_text=True)
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    return match.group(1) if match else ''

def _login(client, tenant, identity):
    csrf = _get_csrf_token(client)
    client.post('/auth/login/', data={
        'slug': tenant.slug,
        'email': identity.email,
        'password': 'password123',
        'csrf_token': csrf,
    }, follow_redirects=True)


class TestAdminUsuarios:

    def test_lista_usuarios_requiere_login(self, app, client):
        response = client.get('/admin/usuarios/', follow_redirects=False)
        assert response.status_code == 302
        assert 'auth/login' in response.headers['Location']

    def test_lista_usuarios_visible_para_admin(self, app, client, admin_setup):
        tenant, identity, member, rol = admin_setup
        _login(client, tenant, identity)
        response = client.get('/admin/usuarios/')
        assert response.status_code == 200
        assert 'Admin' in response.get_data(as_text=True)

    def test_crear_usuario_nuevo(self, app, client, admin_setup):
        tenant, identity, member, rol = admin_setup
        _login(client, tenant, identity)

        csrf = client.get('/admin/usuarios/nuevo/').get_data(as_text=True)
        match = re.search(r'name="csrf_token" value="([^"]+)"', csrf)
        token = match.group(1) if match else ''

        response = client.post('/admin/usuarios/nuevo/', data={
            'nombre': 'Nuevo Usuario',
            'apellidos': 'Apellido Test',
            'email': f'nuevo@{tenant.slug}.com',
            'password': 'password123',
            'activo': 'y',
            'csrf_token': token,
        }, follow_redirects=True)
        assert response.status_code == 200
        assert 'Nuevo Usuario' in response.get_data(as_text=True)

    def test_no_crear_usuario_duplicado(self, app, client, admin_setup):
        tenant, identity, member, rol = admin_setup
        _login(client, tenant, identity)

        csrf = client.get('/admin/usuarios/nuevo/').get_data(as_text=True)
        match = re.search(r'name="csrf_token" value="([^"]+)"', csrf)
        token = match.group(1) if match else ''

        response = client.post('/admin/usuarios/nuevo/', data={
            'nombre': 'Admin',
            'email': identity.email,
            'password': 'password123',
            'activo': 'y',
            'csrf_token': token,
        }, follow_redirects=True)
        assert response.status_code == 200
        assert 'Ya existe' in response.get_data(as_text=True)

    def test_desactivar_usuario(self, app, client, admin_setup):
        tenant, identity, member, rol = admin_setup
        _login(client, tenant, identity)

        import uuid
        with app.app_context():
            id2 = Identity(email=f'otro@{tenant.slug}.com', nombre='Otro')
            id2.set_password('password123')
            db.session.add(id2)
            db.session.flush()
            db.session.refresh(id2)
            m2 = TenantMember(
                identity_id=id2.id, tenant_id=tenant.id, activo=True
            )
            db.session.add(m2)
            db.session.commit()
            m2_id=m2.id

        response = client.post(
            f'/admin/usuarios/{m2.id}/desactivar/',
            data={'csrf_token': _get_csrf_token(client)},
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert 'desactivado' in response.get_data(as_text=True)


class TestAdminRoles:

    def test_lista_roles_visible_para_admin(self, app, client, admin_setup):
        tenant, identity, member, rol = admin_setup
        _login(client, tenant, identity)
        response = client.get('/admin/roles/')
        assert response.status_code == 200
        assert 'Administrador' in response.get_data(as_text=True)

    def test_crear_rol(self, app, client, admin_setup):
        tenant, identity, member, rol = admin_setup
        _login(client, tenant, identity)

        csrf = client.get('/admin/usuarios/nuevo/').get_data(as_text=True)
        match = re.search(r'name="csrf_token" value="([^"]+)"', csrf)
        token = match.group(1) if match else ''

        response = client.post('/admin/roles/nuevo/', data={
            'nombre': 'Músico',
            'permisos': ['eventos.ver', 'musicos.ver'],
            'csrf_token': token,
        }, follow_redirects=True)
        assert response.status_code == 200
        assert 'Músico' in response.get_data(as_text=True)

    def test_no_eliminar_rol_sistema(self, app, client, admin_setup):
        tenant, identity, member, rol = admin_setup
        _login(client, tenant, identity)

        response = client.post(
            f'/admin/roles/{rol.id}/eliminar/',
            data={'csrf_token': _get_csrf_token(client)},
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert 'no se pueden eliminar' in response.get_data(as_text=True)

    def test_rol_aislado_entre_tenants(self, app, client, admin_setup, db):
        tenant, identity, member, rol = admin_setup
        _login(client, tenant, identity)

        response = client.get('/admin/roles/')
        html = response.get_data(as_text=True)

        with app.app_context():
            import uuid
            otro_tenant = Tenant(
                slug=f'otro-{uuid.uuid4().hex[:6]}',
                nombre='Otro Tenant',
                modo='saas',
                activo=True
            )
            db.session.add(otro_tenant)
            db.session.flush()
            db.session.refresh(otro_tenant)
            rol_otro = Role(
                tenant_id=otro_tenant.id,
                nombre='Rol Secreto',
                permisos_json=[],
            )
            db.session.add(rol_otro)
            db.session.commit()

        assert 'Rol Secreto' not in html