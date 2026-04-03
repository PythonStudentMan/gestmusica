"""
Tests de aislamiento de tenant.

Verifican que ninguna query atraviesa fronteras entre tenants.
Estos tests deben pasar SIEMPRE, antes de añadir cualquier
lógica de negocio al sistema
"""
import pytest
from flask import g
from app.models.user import TenantMember, Role, MemberRole, MemberPermiso
from app.middleware.tenant import set_tenant

class TestAislamientoBasico:

    def test_miembro_solo_ve_su_tenant(self, app, session, usuario_en_cada_tenant):
        """ Un tenant no puede ver los usuarios de otro tenant """
        member_a, member_b = usuario_en_cada_tenant

        with app.test_request_context('/'):
            # Activamos el tenant A
            set_tenant(member_a.tenant)

            members = TenantMember.query.filter_by(
                tenant_id=member_a.tenant_id
            ).all()
            emails = [m.email for m in members]

            assert 'user@banda-a.com' in emails
            assert 'user@banda-b.com' not in emails

    def test_tenant_b_no_ve_miembros_de_tenant_a(self, app, session, usuario_en_cada_tenant):
        """ Verificación inversa: tenant B no ve usuarios de tenant A """
        member_a, member_b = usuario_en_cada_tenant

        with app.test_request_context('/'):
            set_tenant(member_b.tenant)

            members = TenantMember.query.filter_by(
                tenant_id=member_b.tenant_id
            ).all()
            emails = [m.email for m in members]

            assert 'user@banda-b.com' in emails
            assert 'user@banda-a.com' not in emails

    def test_current_tenant_sin_contexto_lanza_error(self, app, session):
        """ Si no hay tenant activo, current_tenant() debe lanzar RuntimeError """
        with app.test_request_context('/'):
            # Aseguramos que tenant_id no está en g
            if hasattr(g, 'tenant_id'):
                delattr(g, 'tenant_id')

            with pytest.raises(RuntimeError, match='No hay tenant activo'):
                Role.current_tenant().all()

    def test_for_tenant_explicito(self, app, session, usuario_en_cada_tenant):
        """ for_tenant() permite consultar un tenant concreto sin depender de g """
        member_a, member_b = usuario_en_cada_tenant

        with (app.test_request_context('/')):
            members_a = TenantMember.query.filter_by(
                tenant_id=member_a.tenant_id
            ).all()
            members_b = TenantMember.query.filter_by(
                tenant_id=member_b.tenant_id
            ).all()

            assert all(m.tenant_id == member_a.tenant_id for m in members_a)
            assert all(m.tenant_id == member_b.tenant_id for m in members_b)

    def test_ids_de_tenants_distintos(self, app, session, dos_tenants):
        """ los dos tenants de prueba tienen IDs distintos """
        tenant_a, tenant_b = dos_tenants
        assert tenant_a.id != tenant_b.id

    def test_slug_unico_por_tenant(self, app, session, dos_tenants):
        """ Cada tenant tiene su propio slug único """
        tenant_a, tenant_b = dos_tenants
        assert tenant_a.slug != tenant_b.slug


class TestRolesAislados:

    def test_roles_aislados_por_tenant(self, app, session, dos_tenants):
        """ los roles de un tenant no son visibles desde otro tenant """
        tenant_a, tenant_b = dos_tenants

        rol_a = Role(
            tenant_id=tenant_a.id,
            nombre='Administrador',
            permisos_json=['socios.ver', 'socios.editar'],
            es_sistema=True,
        )
        rol_b = Role(
            tenant_id=tenant_b.id,
            nombre='Administrador',
            permisos_json=['musicos.ver'],
            es_sistema=True,
        )
        session.add_all([rol_a, rol_b])
        session.flush()
        session.refresh(rol_a)
        session.refresh(rol_b)

        with app.test_request_context('/'):
            set_tenant(tenant_a)
            roles = Role.current_tenant().all()
            tenant_ids = {str(r.tenant_id) for r in roles}

            assert str(tenant_a.id) in tenant_ids
            assert str(tenant_b.id) not in tenant_ids

class TestPermisos:

    def test_miembro_hereda_permisos_de_su_rol(self, app, session, usuario_en_cada_tenant):
        """ El usuario acumula los permisos de todos sus roles """
        member_a, _ = usuario_en_cada_tenant

        rol = Role(
            tenant_id=member_a.tenant_id,
            nombre='Secretario',
            permisos_json=['socios.ver', 'socios.editar', 'eventos.ver'],
        )
        session.add(rol)
        session.flush()
        session.refresh(rol)

        asignacion = MemberRole(member_id=member_a.id, role_id=rol.id)
        session.add(asignacion)
        session.flush()

        assert member_a.tiene_permiso('socios.ver')
        assert member_a.tiene_permiso('socios.editar')
        assert member_a.tiene_permiso('eventos.ver')
        assert not member_a.tiene_permiso('contabilidad.ver')

    def test_miembro_sin_roles_no_tiene_permisos(self, app, session, usuario_en_cada_tenant):
        """ un usuario sin roles asignados no tiene ningún permiso """
        _, member_b = usuario_en_cada_tenant
        assert member_b.permisos == set()
        assert not member_b.tiene_permiso('socios.ver')

    def test_permisos_individuales_se_suman_al_rol(self, app, session, usuario_en_cada_tenant):

        member_a, _ = usuario_en_cada_tenant

        rol = Role(
            tenant_id=member_a.tenant_id,
            nombre='Músico',
            permisos_json=['eventos.ver'],
        )
        session.add(rol)
        session.flush()
        session.refresh(rol)

        asignacion = MemberRole(member_id=member_a.id, role_id=rol.id)
        session.add(asignacion)

        permiso_extra = MemberPermiso(
            member_id=member_a.id,
            permiso='socios.ver',
            motivo='Ayuda puntual en secretaria',
        )
        session.add(permiso_extra)
        session.flush()

        perms = set()
        for mr in session.query(MemberRole).filter_by(member_id=member_a.id).all():
            perms.update(mr.role.permisos_json or [])
        for mp in session.query(MemberPermiso).filter_by(member_id=member_a.id).all():
            perms.add(mp.permiso)

        print(f"pemisos: {perms}")

        assert 'eventos.ver' in perms
        assert 'socios.ver' in perms
        assert 'socios.editar' not in perms
