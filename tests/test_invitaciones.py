"""
Tests del flujo de invitaciones.

Cubre:
  - Modelo Invitacion: creación, token único, caducidad, es_valida, marcar_aceptada
  - Ruta admin: crear invitación, reenviar, cancelar, protección por permiso
  - Ruta pública: aceptar invitación (usuario nuevo, usuario existente en otra agrupación)
  - Casos de error: token inválido, invitación caducada, ya aceptada
  - Aislamiento: una agrupación no ve invitaciones de otra
"""

import re
import pytest
from datetime import datetime, timezone, timedelta

from app import db
from app.models.tenant import Tenant
from app.models.user import Identity, TenantMember, Role, MemberRole, Invitacion


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope='function')
def tenant_admin(db, app):
    """Tenant con un usuario administrador completo."""
    import uuid
    slug = f'inv-{uuid.uuid4().hex[:8]}'

    with app.app_context():
        tenant = Tenant(slug=slug, nombre='Banda Invitaciones', modo='saas', activo=True)
        db.session.add(tenant)
        db.session.flush()
        db.session.refresh(tenant)

        identity = Identity(email=f'admin@{slug}.com', nombre='Admin')
        identity.set_password('password123')
        db.session.add(identity)
        db.session.flush()
        db.session.refresh(identity)

        member = TenantMember(identity_id=identity.id, tenant_id=tenant.id, activo=True)
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

        yield tenant, identity, member


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_csrf(client, url='/auth/login/'):
    html = client.get(url).get_data(as_text=True)
    m = re.search(r'name="csrf_token" value="([^"]+)"', html)
    return m.group(1) if m else ''


def _login(client, identity):
    csrf = _get_csrf(client)
    client.post('/auth/login/', data={
        'email': identity.email,
        'password': 'password123',
        'csrf_token': csrf,
    }, follow_redirects=True)


# ---------------------------------------------------------------------------
# 1. Tests de modelo
# ---------------------------------------------------------------------------

class TestInvitacionModelo:

    def test_crear_invitacion(self, app, tenant_admin):
        tenant, identity, member = tenant_admin
        with app.app_context():
            m = db.session.get(TenantMember, member.id)
            inv = Invitacion.crear(
                tenant_id=tenant.id,
                email='nuevo@test.com',
                nombre='Nuevo Usuario',
                invitado_por_id=m.id,
            )
            db.session.add(inv)
            db.session.flush()

            assert inv.token is not None
            assert len(inv.token) > 20
            assert inv.estado == 'pendiente'
            assert inv.email == 'nuevo@test.com'
            assert inv.es_valida
            db.session.rollback()

    def test_token_unico(self, app, tenant_admin):
        """Dos invitaciones nunca comparten token."""
        from sqlalchemy.exc import IntegrityError
        tenant, identity, member = tenant_admin
        with app.app_context():
            m = db.session.get(TenantMember, member.id)
            token = Invitacion.generar_token()
            expires = datetime.now(timezone.utc) + timedelta(hours=72)

            i1 = Invitacion(
                tenant_id=tenant.id, email='a@test.com',
                token=token, estado='pendiente',
                invitado_por_id=m.id, expires_at=expires,
            )
            i2 = Invitacion(
                tenant_id=tenant.id, email='b@test.com',
                token=token, estado='pendiente',
                invitado_por_id=m.id, expires_at=expires,
            )
            db.session.add_all([i1, i2])
            with pytest.raises(IntegrityError):
                db.session.flush()
            db.session.rollback()

    def test_email_normalizado(self, app, tenant_admin):
        """El email se guarda en minúsculas."""
        tenant, identity, member = tenant_admin
        with app.app_context():
            m = db.session.get(TenantMember, member.id)
            inv = Invitacion.crear(
                tenant_id=tenant.id,
                email='MAYUSCULAS@TEST.COM',
                nombre=None,
                invitado_por_id=m.id,
            )
            assert inv.email == 'mayusculas@test.com'
            db.session.rollback()

    def test_ha_caducado_false_recien_creada(self, app, tenant_admin):
        tenant, identity, member = tenant_admin
        with app.app_context():
            m = db.session.get(TenantMember, member.id)
            inv = Invitacion.crear(
                tenant_id=tenant.id, email='x@test.com',
                nombre=None, invitado_por_id=m.id,
            )
            assert not inv.ha_caducado
            assert inv.es_valida
            db.session.rollback()

    def test_ha_caducado_true_expirada(self, app, tenant_admin):
        tenant, identity, member = tenant_admin
        with app.app_context():
            m = db.session.get(TenantMember, member.id)
            inv = Invitacion.crear(
                tenant_id=tenant.id, email='x@test.com',
                nombre=None, invitado_por_id=m.id,
            )
            # Forzar caducidad al pasado
            inv.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
            assert inv.ha_caducado
            assert not inv.es_valida
            db.session.rollback()

    def test_es_valida_false_si_aceptada(self, app, tenant_admin):
        tenant, identity, member = tenant_admin
        with app.app_context():
            m = db.session.get(TenantMember, member.id)
            inv = Invitacion.crear(
                tenant_id=tenant.id, email='x@test.com',
                nombre=None, invitado_por_id=m.id,
            )
            db.session.add(inv)
            db.session.flush()
            db.session.refresh(inv)

            nueva_identity = Identity(email='x@test.com', nombre='X')
            nueva_identity.set_password('pass12345')
            db.session.add(nueva_identity)
            db.session.flush()
            db.session.refresh(nueva_identity)

            inv.marcar_aceptada(nueva_identity.id)
            assert inv.estado == 'aceptada'
            assert not inv.es_valida
            assert inv.accepted_at is not None
            db.session.rollback()

    def test_es_valida_false_si_caducada(self, app, tenant_admin):
        tenant, identity, member = tenant_admin
        with app.app_context():
            m = db.session.get(TenantMember, member.id)
            inv = Invitacion.crear(
                tenant_id=tenant.id, email='x@test.com',
                nombre=None, invitado_por_id=m.id,
            )
            inv.estado = 'caducada'
            assert not inv.es_valida
            db.session.rollback()


# ---------------------------------------------------------------------------
# 2. Tests de rutas admin
# ---------------------------------------------------------------------------

class TestAdminInvitaciones:

    def test_lista_requiere_login(self, app, client):
        r = client.get('/admin/invitaciones/', follow_redirects=False)
        assert r.status_code == 302
        assert 'auth/login' in r.headers['Location']

    def test_lista_visible_para_admin(self, app, client, tenant_admin):
        tenant, identity, member = tenant_admin
        _login(client, identity)
        r = client.get('/admin/invitaciones/')
        assert r.status_code == 200

    def test_crear_invitacion(self, app, client, tenant_admin):
        tenant, identity, member = tenant_admin
        _login(client, identity)

        csrf = _get_csrf(client, '/admin/invitaciones/nueva/')
        r = client.post('/admin/invitaciones/nueva/', data={
            'email':      'invitado@test.com',
            'nombre':     'Usuario Invitado',
            'csrf_token': csrf,
        }, follow_redirects=True)
        assert r.status_code == 200
        assert 'invitado@test.com' in r.get_data(as_text=True)

        with app.app_context():
            inv = Invitacion.query.filter_by(
                tenant_id=tenant.id, email='invitado@test.com'
            ).first()
            assert inv is not None
            assert inv.estado == 'pendiente'
            assert inv.es_valida

    def test_no_invitar_miembro_activo(self, app, client, tenant_admin):
        """No se puede invitar a alguien que ya es miembro activo."""
        tenant, identity, member = tenant_admin
        _login(client, identity)

        csrf = _get_csrf(client, '/admin/invitaciones/nueva/')
        r = client.post('/admin/invitaciones/nueva/', data={
            'email':      identity.email,  # ya es miembro
            'nombre':     'Admin',
            'csrf_token': csrf,
        }, follow_redirects=True)
        assert r.status_code == 200
        assert 'Ya existe' in r.get_data(as_text=True)

    def test_cancelar_invitacion(self, app, client, tenant_admin):
        tenant, identity, member = tenant_admin

        with app.app_context():
            m = db.session.get(TenantMember, member.id)
            inv = Invitacion.crear(
                tenant_id=tenant.id, email='cancelar@test.com',
                nombre=None, invitado_por_id=m.id,
            )
            db.session.add(inv)
            db.session.commit()
            inv_id = inv.id

        _login(client, identity)
        csrf = _get_csrf(client, '/admin/invitaciones/')
        r = client.post(
            f'/admin/invitaciones/{inv_id}/cancelar/',
            data={'csrf_token': csrf},
            follow_redirects=True,
        )
        assert r.status_code == 200

        with app.app_context():
            inv = db.session.get(Invitacion, inv_id)
            assert inv.estado == 'caducada'

    def test_reenviar_invitacion(self, app, client, tenant_admin):
        tenant, identity, member = tenant_admin

        with app.app_context():
            m = db.session.get(TenantMember, member.id)
            inv = Invitacion.crear(
                tenant_id=tenant.id, email='reenviar@test.com',
                nombre=None, invitado_por_id=m.id,
            )
            db.session.add(inv)
            db.session.commit()
            inv_id = inv.id

        _login(client, identity)

        r = client.post(
            f'/admin/invitaciones/{inv_id}/reenviar/',
            data={},
            follow_redirects=True,
        )

        assert r.status_code == 200
        assert 'reenviada' in r.get_data(as_text=True).lower()

    def test_nueva_invitacion_anula_pendiente_previa(self, app, client, tenant_admin):
        """Si ya hay una invitación pendiente para ese email, se caduca antes de crear la nueva."""
        tenant, identity, member = tenant_admin

        with app.app_context():
            m = db.session.get(TenantMember, member.id)
            inv_vieja = Invitacion.crear(
                tenant_id=tenant.id, email='doble@test.com',
                nombre=None, invitado_por_id=m.id,
            )
            db.session.add(inv_vieja)
            db.session.commit()
            inv_vieja_id = inv_vieja.id

        _login(client, identity)
        csrf = _get_csrf(client, '/admin/invitaciones/nueva/')
        client.post('/admin/invitaciones/nueva/', data={
            'email':      'doble@test.com',
            'nombre':     '',
            'csrf_token': csrf,
        }, follow_redirects=True)

        with app.app_context():
            vieja = db.session.get(Invitacion, inv_vieja_id)
            assert vieja.estado == 'caducada'
            nueva = Invitacion.query.filter_by(
                tenant_id=tenant.id, email='doble@test.com', estado='pendiente'
            ).first()
            assert nueva is not None
            assert nueva.id != inv_vieja_id

    def test_aislamiento_invitaciones_entre_tenants(self, app, client, db, tenant_admin):
        """Un admin no puede cancelar invitaciones de otro tenant."""
        tenant, identity, member = tenant_admin
        import uuid

        with app.app_context():
            otro = Tenant(
                slug=f'otro-{uuid.uuid4().hex[:6]}', nombre='Otro', modo='saas', activo=True
            )
            db.session.add(otro)
            db.session.flush()
            db.session.refresh(otro)

            id2 = Identity(email=f'admin2@otro.com', nombre='Admin2')
            id2.set_password('pass')
            db.session.add(id2)
            db.session.flush()
            db.session.refresh(id2)

            m2 = TenantMember(identity_id=id2.id, tenant_id=otro.id, activo=True)
            db.session.add(m2)
            db.session.flush()
            db.session.refresh(m2)

            inv_otro = Invitacion.crear(
                tenant_id=otro.id, email='x@otro.com',
                nombre=None, invitado_por_id=m2.id,
            )
            db.session.add(inv_otro)
            db.session.commit()
            inv_otro_id = inv_otro.id

        _login(client, identity)
        csrf = _get_csrf(client, '/admin/invitaciones/')
        r = client.post(
            f'/admin/invitaciones/{inv_otro_id}/cancelar/',
            data={'csrf_token': csrf},
        )
        # Debe devolver 404 porque filter_by incluye tenant_id del admin logado
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# 3. Tests de la ruta pública — aceptar invitación
# ---------------------------------------------------------------------------

class TestAceptarInvitacion:

    def _crear_inv(self, app, tenant, member_id, email='nuevo@test.com', nombre='Nuevo'):
        with app.app_context():
            inv = Invitacion.crear(
                tenant_id=tenant.id,
                email=email,
                nombre=nombre,
                invitado_por_id=member_id,
            )
            db.session.add(inv)
            db.session.commit()
            # Devolver datos primitivos para usar fuera del contexto
            return str(inv.id), inv.token, inv.email

    def test_get_formulario_valido(self, app, client, tenant_admin):
        tenant, identity, member = tenant_admin
        inv_id, token, email = self._crear_inv(app, tenant, member.id)

        r = client.get(f'/auth/invitacion/{token}/')
        assert r.status_code == 200
        html = r.get_data(as_text=True)
        assert 'Activa tu cuenta' in html
        assert 'Banda Invitaciones' in html

    def test_token_invalido_devuelve_404(self, app, client):
        r = client.get('/auth/invitacion/token-que-no-existe/')
        assert r.status_code == 404

    def test_invitacion_caducada_redirige(self, app, client, tenant_admin):
        tenant, identity, member = tenant_admin

        with app.app_context():
            m = db.session.get(TenantMember, member.id)
            inv = Invitacion.crear(
                tenant_id=tenant.id, email='caduca@test.com',
                nombre=None, invitado_por_id=m.id,
            )
            inv.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
            db.session.add(inv)
            db.session.commit()
            token = inv.token

        r = client.get(f'/auth/invitacion/{token}/', follow_redirects=True)
        assert r.status_code == 200
        assert 'caducado' in r.get_data(as_text=True).lower()

    def test_invitacion_ya_aceptada_redirige(self, app, client, tenant_admin):
        tenant, identity, member = tenant_admin

        with app.app_context():
            m = db.session.get(TenantMember, member.id)
            inv = Invitacion.crear(
                tenant_id=tenant.id, email='ya@test.com',
                nombre=None, invitado_por_id=m.id,
            )
            inv.estado = 'aceptada'
            inv.accepted_at = datetime.now(timezone.utc)
            db.session.add(inv)
            db.session.commit()
            token = inv.token

        r = client.get(f'/auth/invitacion/{token}/', follow_redirects=True)
        assert r.status_code == 200
        assert 'ya fue aceptada' in r.get_data(as_text=True)

    def test_aceptar_crea_identity_y_member(self, app, client, tenant_admin):
        """Un usuario nuevo acepta la invitación → se crea Identity + TenantMember."""
        tenant, identity, member = tenant_admin
        import uuid
        email = f'nuevo-{uuid.uuid4().hex[:6]}@test.com'
        inv_id, token, _ = self._crear_inv(app, tenant, member.id, email=email)

        r = client.post(f'/auth/invitacion/{token}/', data={
            'nombre':    'Nuevo',
            'apellidos': 'Usuario',
            'password':  'password123',
            'password2': 'password123',
            'csrf_token': '',  # CSRF desactivado en tests
        }, follow_redirects=True)
        assert r.status_code == 200
        assert 'Bienvenido' in r.get_data(as_text=True)

        with app.app_context():
            nueva_id = Identity.query.filter_by(email=email).first()
            assert nueva_id is not None
            assert nueva_id.nombre == 'Nuevo'

            nuevo_member = TenantMember.query.filter_by(
                identity_id=nueva_id.id, tenant_id=tenant.id
            ).first()
            assert nuevo_member is not None
            assert nuevo_member.activo

            inv = db.session.get(Invitacion, inv_id)
            assert inv.estado == 'aceptada'
            assert inv.identity_id == nueva_id.id

    def test_aceptar_usuario_existente_en_otra_agrupacion(self, app, client, tenant_admin):
        """
        Si el email ya tiene Identity (de otra agrupación), se reutiliza
        y solo se crea el nuevo TenantMember.
        """
        tenant, identity, member = tenant_admin
        import uuid

        email = f'existente-{uuid.uuid4().hex[:6]}@test.com'

        # Crear Identity preexistente en otro tenant
        with app.app_context():
            otro = Tenant(
                slug=f'otro-{uuid.uuid4().hex[:6]}', nombre='Otro', modo='saas', activo=True
            )
            db.session.add(otro)
            db.session.flush()
            db.session.refresh(otro)

            id_prev = Identity(email=email, nombre='Ya Existe')
            id_prev.set_password('otraclave123')
            db.session.add(id_prev)
            db.session.flush()
            db.session.refresh(id_prev)

            m_prev = TenantMember(identity_id=id_prev.id, tenant_id=otro.id, activo=True)
            db.session.add(m_prev)
            db.session.commit()
            id_prev_id = id_prev.id

        inv_id, token, _ = self._crear_inv(app, tenant, member.id, email=email)

        client.post(f'/auth/invitacion/{token}/', data={
            'nombre':     'Ya Existe',
            'apellidos':  '',
            'password':   'nuevaclave123',
            'password2':  'nuevaclave123',
            'csrf_token': '',
        }, follow_redirects=True)

        with app.app_context():
            # La Identity original se reutiliza (mismo id)
            ids = Identity.query.filter_by(email=email).all()
            assert len(ids) == 1
            assert ids[0].id == id_prev_id

            # Ahora tiene membresía en ambos tenants
            members = TenantMember.query.filter_by(identity_id=id_prev_id).all()
            tenant_ids = {str(m.tenant_id) for m in members}
            assert str(tenant.id) in tenant_ids

    def test_contrasenas_no_coinciden(self, app, client, tenant_admin):
        tenant, identity, member = tenant_admin
        inv_id, token, _ = self._crear_inv(app, tenant, member.id, email='mismatch@test.com')

        r = client.post(f'/auth/invitacion/{token}/', data={
            'nombre':     'Test',
            'apellidos':  '',
            'password':   'password123',
            'password2':  'diferente456',
            'csrf_token': '',
        }, follow_redirects=False)
        # Debe quedarse en el formulario (no redirigir)
        assert r.status_code == 200
        assert 'no coinciden' in r.get_data(as_text=True)

        with app.app_context():
            # La invitación sigue pendiente
            inv = db.session.get(Invitacion, inv_id)
            assert inv.estado == 'pendiente'
