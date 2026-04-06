import pytest
from app import create_app, db as _db
from app.models.tenant import Tenant, Module, TenantModule
from app.models.user import Identity, TenantMember, Role, MemberRole, MemberPermiso


@pytest.fixture(scope='session')
def app():
    app = create_app('testing')
    with app.app_context():
        _db.create_all()
        yield app
        _db.drop_all()

@pytest.fixture(scope='session')
def db(app):
    """ Limpia todas las tablas anes de cada test. """
    with app.app_context():
        yield _db
        _db.session.remove()
        # Limpiar tablas en orden correcto (respetando FK)
        _db.session.execute(_db.text(
            'TRUNCATE TABLE '
            'recibos, cuotas, socios, tipos_socio, tutores_legales, '
            'unidades_familiares, socios_config, personas, '
            'member_roles, member_permisos, sessions, '
            'tenant_members, identities, roles, tenant_modules, '
            'tenant_config, subagrupaciones, tenants, modules '
            'RESTART IDENTITY CASCADE'
        ))
        _db.session.commit()

@pytest.fixture(scope='function')
def session(app, db):
    with app.app_context():
        yield db.session

@pytest.fixture(scope='function')
def client(app):
    return app.test_client()

@pytest.fixture(scope='function')
def dos_tenants(session):
    """ Crea dos tenants de prueba y los devuelve """
    tenant_a = Tenant(slug='banda-a', nombre='Banda A', modo='saas', activo=True)
    tenant_b = Tenant(slug='banda-b', nombre='Banda B', modo='saas', activo=True)
    session.add_all([tenant_a, tenant_b])
    session.flush()
    session.refresh(tenant_a)
    session.refresh(tenant_b)
    return tenant_a, tenant_b

@pytest.fixture(scope='function')
def usuario_en_cada_tenant(session, dos_tenants):
    """ Crea un usuario en cada tenant """
    tenant_a, tenant_b = dos_tenants

    identity_a = Identity(email='user@banda-a.com', nombre='Usuario A')
    identity_a.set_password('password123')
    identity_b = Identity(email='user@banda-b.com', nombre='Usuario B')
    identity_b.set_password('password123')
    session.add_all([identity_a, identity_b])
    session.flush()

    member_a = TenantMember(identity_id=identity_a.id, tenant_id=tenant_a.id, activo=True)
    member_b = TenantMember(identity_id=identity_b. id, tenant_id=tenant_b.id, activo=True)
    session.add_all([member_a, member_b])
    session.flush()
    session.refresh(member_a)
    session.refresh(member_b)

    return member_a, member_b