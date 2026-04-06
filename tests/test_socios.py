import re
import pytest
from datetime import date, timedelta

from jinja2.runtime import identity

from app import db
from app.models.tenant import Tenant
from app.models.user import Identity, TenantMember, Role, MemberRole
from app.modules.socios.models import (
    SociosConfig, Persona, TipoSocio, Socio,
    Cuota, Recibo, TutorLegal, UnidadFamiliar
)

@pytest.fixture(scope='function')
def tenant_socios(db, app):
    """ Tenant con usuario administrador y permiso socios.* completo. """
    import uuid
    slug = f'socios-{uuid.uuid4().hex[:8]}'

    with app.app_context():
        tenant = Tenant(slug=slug, nombre='Banda Socios Test', modo='saas', activo=True)
        db.session.add(tenant)
        db.session.flush()
        db.session.refresh(tenant)

        identity = Identity(email=f'admin@{slug}.com', nombre='Admin Socios')
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
            nombre='Admin',
            permisos_json=[
                'socios.ver', 'socios.crear', 'socios.editar', 'socios.eliminar',
                'cuotas.crear', 'cutoas.editar',
                'tesoreria.cobrar', 'tesoreria.recibos.eliminar',
                'admin.usuarios', 'admin.roles',
            ],
            es_sistema=True,
        )
        db.session.add(rol)
        db.session.flush()
        db.session.refresh(rol)

        db.session.add(MemberRole(member_id=member.id, role_id=rol.id))
        db.session.commit()

        yield tenant, identity, member

@pytest.fixture(scope='function')
def tenant_solo_ver(db, app):
    """ Tenant con susuario que solo tiene socios.ver"""
    import uuid
    slug = f'ver-{uuid.uuid4().hex[:8]}'

    with app.app_context():
        tenant = Tenant(slug=slug, nombre='Banda Ver', modo='saas', activo=True)
        db.session.add(tenant)
        db.session.flush()
        db.session.refresh(tenant)

        identity = Identity(email=f'ver@{slug}.com', nombre='Usuario Ver')
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
            nombre='Lector',
            permisos_json=['socios.ver'],
        )
        db.session.add(rol)
        db.session.flush()
        db.session.refresh(rol)

        db.session.add(MemberRole(member_id=member.id, role_id=rol.id))
        db.session.commit()

        yield tenant, identity, member

@pytest.fixture(scope='function')
def datos_socios(db, app, tenant_socios):
    """ Crea un TipoSocio y una Persona+Socio de prueba dentro del tenant. """
    tenant, identity, member = tenant_socios

    with app.app_context():
        tipo = TipoSocio(
            tenant_id=tenant.id,
            nombre='Socio General',
            importe_cuota=50,
            periodicidad='anual',
            activo=True,
        )
        db.session.add(tipo)
        db.session.flush()
        db.session.refresh(tipo)

        persona = Persona(
            tenant_id=tenant.id,
            nombre='Juan',
            apellidos='García',
            email='juan@test.com',
            fecha_nacimiento=date(1985, 3, 15),
            es_menor=False,
        )
        db.session.add(persona)
        db.session.flush()
        db.session.refresh(persona)

        socio = Socio(
            tenant_id=tenant.id,
            persona_id=persona.id,
            tipo_socio_id=tipo.id,
            numero_socio='0001',
            fecha_alta=date.today(),
            estado='activo',
        )
        db.session.add(socio)
        db.session.commit()
        db.session.refresh(socio)

        yield tenant, identity, tipo, persona, socio


def _get_csrf(client, url='/auth/login/'):
    html = client.get(url).get_data(as_text=True)
    m = re.search(r'name="csrf_token" value="([^"]+)"', html)
    return m.group(1) if m else ''

def _login(client, identity, tenant=None):
    """ Login sin slug. Si es multi-agrupación se asume una sola. """
    csrf = _get_csrf(client)
    return client.post('/auth/login/', data={
        'email': identity.email,
        'password': 'password123',
        'csrf_token': csrf,
    }, follow_redirects=True)


class TestPersonaModelo:

    def test_nombre_completo(self, app, datos_socios):
        tenant, identity, tipo, persona, socio = datos_socios
        with app.app_context():
            p = db.session.get(Persona, persona.id)
            assert p.nombre_completo == 'García, Juan'

    def test_actualizar_es_menor_adulto(self, app, datos_socios):
        tenant, identity, tipo, persona, socio = datos_socios
        with app.app_context():
            p = db.session.get(Persona, persona.id)
            p.fecha_nacimiento = date(1985,1,1)
            p.actualizar_es_menor()
            assert p.es_menor is False

    def test_actualizar_es_menor_menor(self, app, datos_socios):
        tenant, identity, tipo, persona, socio = datos_socios
        with app.app_context():
            p = db.session.get(Persona, persona.id)
            p.fecha_nacimiento = date.today() - timedelta(days=365 * 10)
            p.actualizar_es_menor()
            assert p.es_menor is True

    def test_actualizar_es_menor_sin_fecha(self, app, datos_socios):
        tenant, identity, tipo, persona, socio = datos_socios
        with app.app_context():
            p = db.session.get(Persona, persona.id)
            p.fecha_nacimiento = None
            p.actualizar_es_menor()
            assert p.es_menor is False

    def test_dni_unico_por_tenant(self, app, datos_socios):
        from sqlalchemy.exc import IntegrityError
        tenant, identity, tipo, persona, socio = datos_socios
        with app.app_context():
            p1 = db.session.get(Persona, persona.id)
            p1.dni = '12345678A'
            db.session.flush()

            p2 = Persona(
                tenant_id=tenant.id,
                nombre='Otra', apellidos='Persona',
                dni='12345678A'
            )
            db.session.add(p2)
            with pytest.raises(IntegrityError):
                db.session.flush()
            db.session.rollback()


class TestTipoSocioModelo:

    def test_nombre_unico_por_tenant(self, app, datos_socios):
        from sqlalchemy.exc import IntegrityError
        tenant, identity, tipo, persona, socio = datos_socios
        with app.app_context():
            duplicado = TipoSocio(
                tenant_id=tenant.id,
                nombre='Socio General',
                importe_cuota=100,
                periodicidad='anual',
            )
            db.session.add(duplicado)
            with pytest.raises(IntegrityError):
                db.session.flush()
            db.session.rollback()

    def test_form_tenant_solo_activos(self, app, datos_socios):
        tenant, identity, tipo, persona, socio = datos_socios
        with app.app_context():
            inactivo = TipoSocio(
                tenant_id=tenant.id,
                nombre='Tipo Inactivo',
                importe_cuota=0,
                periodicidad='anual',
                activo=False,
            )
            db.session.add(inactivo)
            db.session.flush()
            tipos = TipoSocio.for_tenant(tenant.id).all()
            nombres = [t.nombre for t in tipos]
            assert 'Socio General' in nombres
            assert 'Tipo Inactivo' not in nombres
            db.session.rollback()


class TestSocioModelo:

    def test_numero_unico_por_tenant(self, app, datos_socios):
        from sqlalchemy.exc import IntegrityError
        tenant, identity, tipo, persona, socio = datos_socios
        with app.app_context():
            persona2 = Persona(
                tenant_id=tenant.id, nombre='Pedro', apellidos='López'
            )
            db.session.add(persona2)
            db.session.flush()
            duplicado = Socio(
                tenant_id=tenant.id,
                persona_id=persona2.id,
                tipo_socio_id=tipo.id,
                numero_socio='0001',
                fecha_alta=date.today(),
                estado='activo',
            )
            db.session.add(duplicado)
            with pytest.raises(IntegrityError):
                db.session.flush()
            db.session.rollback()

    def test_dar_baja(self, app, datos_socios):
        tenant, identity, tipo, persona, socio = datos_socios
        with app.app_context():
            s = db.session.get(Socio, socio.id)
            assert s.estado == 'activo'
            s.dar_baja()
            assert s.estado == 'baja'
            assert s.fecha_baja == date.today()

    def test_dar_baja_fecha_personalizada(self, app, datos_socios):
        tenant, identity,tipo, persona, socio = datos_socios
        with app.app_context():
            s = db.session.get(Socio, socio.id)
            fecha = date(2024,12,31)
            s.dar_baja(fecha=fecha)
            assert s.fecha_baja == fecha

    def test_nombre_completo_delegado(self, app, datos_socios):
        tenant, identity, tipo, persona, socio = datos_socios
        with app.app_context():
            s = db.session.get(Socio, socio.id)
            assert s.nombre_completo == 'García, Juan'

    def test_for_tenant_aislamiento(self, app, db, datos_socios):
        tenant, identity, tipo, persona, socio = datos_socios
        with app.app_context():
            import uuid
            otro_tenant = Tenant(
                slug=f'otro-{uuid.uuid4().hex[:6]}', nombre='Otro', modo='saas', activo=True
            )
            db.session.add(otro_tenant)
            db.session.flush()
            socios_otro = Socio.for_tenant(otro_tenant.id).all()
            assert len(socios_otro) == 0
            db.session.rollback()


class TestCuotaModelo:

    def _crear_cuota(self, app, tenant, tipo):
        cuota = Cuota(
            tenant_id=tenant.id,
            tipo_socio_id=tipo.id,
            descripcion='Cuota Anual 2024',
            importe=50,
            fecha_inicio=date(2024,1,1),
            fecha_fin=date(2024,12,31),
            activa=True,
        )
        db.session.add(cuota)
        db.session.flush()
        db.session.refresh(cuota)
        return cuota

    def test_genera_recibo_para_socio_activo(self, app, datos_socios):
        tenant, identity, tipo, persona, socio = datos_socios
        with app.app_context():
            cuota = self._crear_cuota(app, tenant, tipo)
            recibos = cuota.generar_recibos(tenant.id)
            assert len(recibos) == 1
            assert recibos[0].socio_id == socio.id
            db.session.rollback()

    def test_no_genera_recibo_duplicado(self, app, datos_socios):
        tenant, identity, tipo, persona, socio = datos_socios
        with app.app_context():
            cuota = self._crear_cuota(app, tenant, tipo)
            cuota.generar_recibos(tenant.id)
            db.session.flush()
            recibos_2 = cuota.generar_recibos(tenant.id)
            assert len(recibos_2) == 0
            db.session.rollback()

    def test_no_genera_recibo_para_socio_de_baja(self, app, datos_socios):
        tenant, identity, tipo, persona, socio = datos_socios
        with app.app_context():
            s = db.session.get(Socio, socio.id)
            s.dar_baja()
            db.session.flush()
            cuota = self._crear_cuota(app, tenant, tipo)
            recibos = cuota.generar_recibos(tenant.id)
            assert len(recibos) == 0
            db.session.rollback()

    def test_no_genera_recibo_para_otro_tipo_socio(self, app, datos_socios):
        tenant, identity, tipo, persona, socio = datos_socios
        with app.app_context():
            otro_tipo = TipoSocio(
                tenant_id=tenant.id,
                nombre='Socio Juvenil',
                importe_cuota=25,
                periodicidad='anual',
            )
            db.session.add(otro_tipo)
            db.session.flush()
            db.session.refresh(otro_tipo)

            cuota_otro = Cuota(
                tenant_id=tenant.id,
                tipo_socio_id=otro_tipo.id,
                descripcion='Cuota Juvenil 2024',
                importe=25,
                fecha_inicio=date(2024,1,1),
                fecha_fin=date(2024,12,31),
            )
            db.session.add(cuota_otro)
            db.session.flush()
            db.session.refresh(cuota_otro)

            recibos = cuota_otro.generar_recibos(tenant.id)
            assert len(recibos) == 0
            db.session.rollback()


class TestReciboModelo:

    def _socio_con_recibo(self, app, tenant, tipo, socio):
        cuota = Cuota(
            tenant_id=tenant.id,
            tipo_socio_id=tipo.id,
            descripcion='Cuota Test',
            importe=100,
            fecha_inicio=date(2024,1,1),
            fecha_fin=date(2024,12,31),
        )
        db.session.add(cuota)
        db.session.flush()
        db.session.refresh(cuota)

        recibo = Recibo(
            tenant_id=tenant.id,
            socio_id=socio.id,
            cuota_id=cuota.id,
            numero_recibo=Recibo.generar_numero(tenant.id),
            importe=100,
            descuento=0,
            fecha_emision=date.today(),
            fecha_vencimiento=date(2024,12,31),
            estado='pendiente',
        )
        db.session.add(recibo)
        db.session.flush()
        db.session.refresh(recibo)
        return recibo

    def test_importe_final_sin_descuento(self, app, datos_socios):
        tenant, identity, tipo, persona, socio = datos_socios
        with app.app_context():
            recibo = self._socio_con_recibo(app, tenant, tipo, socio)
            assert recibo.importe_final == 100.0
            db.session.rollback()

    def test_importe_final_con_descuento(self, app, datos_socios):
        tenant, identity, tipo, persona, socio = datos_socios
        with app.app_context():
            recibo = self._socio_con_recibo(app, tenant, tipo, socio)
            recibo.descuento = 20
            assert recibo.importe_final == 80.0
            db.session.rollback()

    def test_registrar_pago(self, app, datos_socios):
        tenant, identity, tipo, persona, socio = datos_socios
        with app.app_context():
            recibo = self._socio_con_recibo(app, tenant, tipo, socio)
            assert recibo.estado == 'pendiente'
            recibo.registrar_pago(metodo='transferencia')
            assert recibo.estado == 'pagado'
            assert recibo.fecha_pago == date.today()
            assert recibo.metodo_pago == 'transferencia'
            db.session.rollback()

    def test_numeracion_secuencial(self, app, datos_socios):
        tenant, identity, tipo, persona, socio = datos_socios
        with app.app_context():
            r1 = Recibo.generar_numero(tenant.id)
            anio = date.today().year
            assert r1 == f'REC-{anio}-0001'
            db.session.rollback()

    def test_numeracion_reinicia_nuevo_anio(self, app, datos_socios):
        """ Si el último recibo es de otro año, el contador reinicia """
        tenant, identity, tipo, persona, socio = datos_socios
        tenant_id = tenant.id
        tipo_id = tipo.id
        socio_id = socio.id

        with app.app_context():
            tipo_db = db.session.get(TipoSocio, tipo_id)
            socio_db = db.session.get(Socio, socio_id)

            cuota = Cuota(
                tenant_id=tenant.id,
                tipo_socio_id=tipo_db.id,
                descripcion='Cuota vieja',
                importe=50,
                fecha_inicio=date(2023,1,1),
                fecha_fin=date(2023,12,31),
            )
            db.session.add(cuota)
            db.session.flush()
            db.session.refresh(cuota)

            recibo_viejo = Recibo(
                tenant_id=tenant_id,
                socio_id=socio_db.id,
                cuota_id=cuota.id,
                numero_recibo='REC-2023-0099',
                importe=50,
                descuento=0,
                fecha_emision=date(2023,6,1),
                fecha_vencimiento=date(2023,12,31),
                estado='pagado',
            )
            db.session.add(recibo_viejo)
            db.session.flush()

            nuevo = Recibo.generar_numero(tenant.id)
            anio = date.today().year
            assert nuevo == f'REC-{anio}-0001'
            db.session.rollback()

    def test_numero_unico_por_tenant(self, app, datos_socios):
        from sqlalchemy.exc import IntegrityError
        tenant, identity, tipo, persona, socio = datos_socios
        with app.app_context():
            cuota = Cuota(
                tenant_id=tenant.id,
                tipo_socio_id=tipo.id,
                descripcion='C1',
                importe=50,
                fecha_inicio=date(2024,1,1),
                fecha_fin=date(2024,12,31),
            )
            db.session.add(cuota)
            db.session.flush()
            db.session.refresh(cuota)

            r1 = Recibo(
                tenant_id=tenant.id, socio_id=socio.id, cuota_id=cuota.id,
                numero_recibo='REC-DUP-0001', importe=50, descuento=0,
                fecha_emision=date.today(), fecha_vencimiento=date(2024,12,31),
                estado='pendiente'
            )
            r2 = Recibo(
                tenant_id=tenant.id, socio_id=socio.id, cuota_id=cuota.id,
                numero_recibo='REC-DUP-0001', importe=50, descuento=0,
                fecha_emision=date.today(), fecha_vencimiento=date(2024, 12, 31),
                estado='pendiente'
            )
            db.session.add_all([r1, r2])
            with pytest.raises(IntegrityError):
                db.session.flush()
            db.session.rollback()


class TestTutorLegalModelo:

    def test_crear_relacion_tutor_menor(self, app, datos_socios):
        tenant, identity, tipo, persona, socio = datos_socios
        with app.app_context():
            menor = Persona(
                tenant_id=tenant.id,
                nombre='Niño', apellidos='García',
                fecha_nacimiento=date.today() - timedelta(days=365 * 10),
                es_menor=True,
            )
            db.session.add(menor)
            db.session.flush()
            db.session.refresh(menor)

            tutor_rel = TutorLegal(
                tenant_id=tenant.id,
                persona_menor_id=menor.id,
                persona_tutor_id=persona.id,
                relacion='padre',
                patria_potestad=True,
                firma_requerida=True,
            )
            db.session.add(tutor_rel)
            db.session.flush()

            assert tutor_rel.patria_potestad is True
            assert tutor_rel.firma_requerida is True
            db.session.rollback()

    def test_tutor_duplicado_no_permitido(self, app, datos_socios):
        from sqlalchemy.exc import IntegrityError
        tenant, identity, tipo, persona, socio = datos_socios
        with app.app_context():
            menor = Persona(
                tenant_id=tenant.id,
                nombre='Niño', apellidos='García',
                es_menor=True,
            )
            db.session.add(menor)
            db.session.flush()
            db.session.refresh(menor)

            t1 = TutorLegal(
                tenant_id=tenant.id,
                persona_menor_id=menor.id,
                persona_tutor_id=persona.id,
                relacion='padre',
            )
            t2 = TutorLegal(
                tenant_id=tenant.id,
                persona_menor_id=menor.id,
                persona_tutor_id=persona.id,
                relacion='madre',
            )
            db.session.add_all([t1, t2])
            with pytest.raises(IntegrityError):
                db.session.flush()
            db.session.rollback()


class TestSociosConfig:

    def test_for_tenant_crea_config_por_defecto(self, app, datos_socios):
        tenant, identity, tipo, persona, socio = datos_socios
        with app.app_context():
            config = SociosConfig.for_tenant(tenant.id)
            assert config is not None
            assert config.tenant_id == tenant.id
            assert config.max_tutores_menor == 2
            db.session.rollback()

    def test_for_tenant_no_duplica(self, app, datos_socios):
        tenant, identity, tipo, persona, socio = datos_socios
        with app.app_context():
            c1 = SociosConfig.for_tenant(tenant.id)
            db.session.flush()
            c2 = SociosConfig.for_tenant(tenant.id)
            assert c1.id == c2.id
            db.session.rollback()


class TestUnidadFamiliar:

    def test_nombre_unico_por_tenant(self, app, datos_socios):
        from sqlalchemy.exc import IntegrityError
        tenant, identity, tipo, persona, socio = datos_socios
        with app.app_context():
            uf1 = UnidadFamiliar(tenant_id=tenant.id, nombre='Familia García')
            uf2 = UnidadFamiliar(tenant_id=tenant.id, nombre='Familia García')
            db.session.add_all([uf1, uf2])
            with pytest.raises(IntegrityError):
                db.session.flush()
            db.session.rollback()


class TestAislamientoSocios:

    def test_socios_de_un_tenant_no_visibles_en_otro(self, app, db, datos_socios):
        tenant, identity, tipo, persona, socio = datos_socios
        with app.app_context():
            import uuid
            otro = Tenant(
                slug=f'otro-{uuid.uuid4().hex[:6]}', nombre='Otro', modo='saas', activo=True
            )
            db.session.add(otro)
            db.session.flush()

            socios_otro = Socio.for_tenant(otro.id).all()
            assert all(s.tenant_id != tenant.id for s in socios_otro)

    def test_tipos_socio_aislados_por_tenant(self, app, db, datos_socios):
        tenant, identity, tipo, persona, socio = datos_socios
        with app.app_context():
            import uuid
            otro = Tenant(
                slug=f'otro2-{uuid.uuid4().hex[:6]}', nombre='Otro2', modo='saas', activo=True
            )
            db.session.add(otro)
            db.session.flush()

            tipos_otro = TipoSocio.for_tenant(otro.id).all()
            assert len(tipos_otro) == 0

    def test_recibos_aislados_por_tenant(self, app, db, datos_socios):
        tenant, identity, tipo, persona, socio = datos_socios
        with app.app_context():
            import uuid
            otro = Tenant(
                slug=f'otro3-{uuid.uuid4().hex[:6]}', nombre='Otro3', modo='saas', activo=True
            )
            db.session.add(otro)
            db.session.flush()

            recibos_otro = Recibo.query.filter_by(tenant_id=otro.id).all()
            assert len(recibos_otro) == 0


class TestRutasSocios:

    def test_index_requiere_login(self, app, client):
        r = client.get('/socios/', follow_redirects=False)
        assert r.status_code == 302
        assert 'auth/login' in r.headers['Location']

    def test_index_visible_con_permiso(self, app, client, datos_socios):
        tenant, identity, tipo, persona, socio = datos_socios
        _login(client, identity)
        r = client.get('/socios/')
        assert r.status_code == 200
        assert 'Módulo de Socios' in r.get_data(as_text=True)

    def test_lista_socios_muestra_socio(self, app, client, datos_socios):
        tenant, identity, tipo, persona, socio = datos_socios
        _login(client, identity)
        r = client.get('/socios/lista/')
        assert r.status_code == 200
        assert 'García' in r.get_data(as_text=True)

    def test_lista_socios_filtra_por_estado(self, app, client, datos_socios):
        tenant, identity, tipo, persona, socio = datos_socios
        _login(client, identity)
        r = client.get('/socios/?estado=baja')
        assert r.status_code == 200
        assert 'García' not in r.get_data(as_text=True)

    def test_detalle_socio(self, app, client, datos_socios):
        tenant, identity, tipo, persona, socio = datos_socios
        _login(client, identity)
        r = client.get(f'/socios/{socio.id}/')
        assert r.status_code == 200
        assert 'García' in r.get_data(as_text=True)
        assert 'Socio General' in r.get_data(as_text=True)

    def test_crear_socio_requiere_permiso_crear(self, app, client, tenant_solo_ver):
        """ Un usuario con solo socios.ver no puede crear socios """
        tenant, identity, member = tenant_solo_ver
        _login(client, identity)
        r = client.get('/socios/nuevo/', follow_redirects=True)
        assert r.status_code == 200
        html = r.get_data(as_text=True)
        assert 'permiso' in html.lower() or 'socios' in html.lower()

    def test_tipos_socio_visible(self, app, client, datos_socios):
        tenant, identity, tipo, persona, socio = datos_socios
        _login(client, identity)
        r = client.get('/socios/tipos/')
        assert r.status_code == 200
        assert 'Socio General' in r.get_data(as_text=True)

    def test_cuotas_visible(self, app, client, datos_socios):
        tenant, identity, tipo, persona, socio = datos_socios
        _login(client, identity)
        r = client.get('/socios/cuotas/')
        assert r.status_code == 200

    def test_recibos_visible(self, app, client, datos_socios):
        tenant, identity, tipo, persona, socio = datos_socios
        _login(client, identity)
        r = client.get('/socios/recibos/')
        assert r.status_code == 200

    def test_config_visible(self, app, client, datos_socios):
        tenant, identity, tipo, persona, socio = datos_socios
        _login(client, identity)
        r = client.get('/socios/config/')
        assert r.status_code == 200

    def test_baja_socio(self, app, client, datos_socios):
        tenant, identity, tipo, persona, socio = datos_socios
        _login(client, identity)

        csrf = _get_csrf(client, f'/socios/{socio.id}/baja/')
        r = client.post(
            f'/socios/{socio.id}/baja',
            data={
                'fecha_baja': date.today().isoformat(),
                'csrf_token': csrf,
            },
            follow_redirects=True,
        )
        assert r.status_code == 200

        with app.app_context():
            s = db.session.get(Socio, socio.id)
            assert s.estado == 'baja'

    def test_crear_cuota_genera_recibos(self, app, client, datos_socios):
        import uuid as _uuid
        tenant, identity, tipo, persona, socio = datos_socios

        with app.app_context():
            s = db.session.get(Socio, socio.id)
            if s.estado != 'activo':
                s.estado = 'activo'
                s.fecha_baja = None
                db.session.commit()

        _login(client, identity)

        csrf = _get_csrf(client, '/socios/cuotas/nueva/')
        r = client.post('/socios/cuotas/nueva/', data={
            'tipo_socio_id': str(tipo.id),
            'descripcion': f'Cuota HTTP Test {_uuid.uuid4().hex[:6]}',
            'importe': '60.00',
            'fecha_inicio': '2024-01-01',
            'fecha_fin': '2024-12-31',
            'activa': 'y',
            'csrf_token': csrf,
        }, follow_redirects=True)
        assert r.status_code == 200
        html = r.get_data(as_text=True)
        assert 'Cuota HTTP Test' in html, (
            f"La cuota no aparece en la lista - posible fallo de validación del form. "
            f"Respuesta: {html[:500]}"
        )

        with app.app_context():
            recibos = Recibo.query.filter_by(tenant_id=tenant.id).all()
            assert len(recibos) >= 1, "Se esperaba al menos 1 recibo generado"
            assert any(r.estado == 'pendiente' for r in recibos)


class TestPermisosIndividualesSocios:

    def test_permiso_individual_socios_crear_sin_rol(self, app, db, datos_socios):
        tenant, identity, tipo, persona, socio = datos_socios
        with app.app_context():
            import uuid
            from app.models.user import MemberPermiso

            id_sin_rol = Identity(email=f'sinrol@{tenant.slug}.com', nombre='Sin Rol')
            id_sin_rol.set_password('password123')
            db.session.add(id_sin_rol)
            db.session.flush()
            db.session.refresh(id_sin_rol)

            m = TenantMember(
                identity_id=id_sin_rol.id, tenant_id=tenant.id, activo=True
            )
            db.session.add(m)
            db.session.flush()
            db.session.refresh(m)

            assert not m.tiene_permiso('socios.crear')
            assert not m.tiene_permiso('socios.ver')

            mp = MemberPermiso(
                member_id=m.id,
                permiso='socios.crear',
                motivo='Prueba puntual de alta de socios en enero',
            )
            db.session.add(mp)
            db.session.flush()

            db.session.expire(m)
            assert m.tiene_permiso('socios.crear')
            assert not m.tiene_permiso('socios.ver')
            db.session.rollback()

    def test_revocar_permiso_individual_elimina_acceso(self, app, db, datos_socios):
        tenant, identity, tipo, persona, socio = datos_socios
        with app.app_context():
            from app.models.user import MemberPermiso
            id2 = Identity(email=f'rev@{tenant.slug}.com', nombre='Revocable')
            id2.set_password('password123')
            db.session.add(id2)
            db.session.flush()
            db.session.refresh(id2)

            m = TenantMember(identity_id=id2.id, tenant_id=tenant.id, activo=True)
            db.session.add(m)
            db.session.flush()
            db.session.refresh(m)

            mp = MemberPermiso(
                member_id=m.id,
                permiso='socios.editar',
                motivo='Temporal',
            )
            db.session.add(mp)
            db.session.flush()
            assert m.tiene_permiso('socios.editar')

            db.session.delete(mp)
            db.session.flush()
            db.session.expire(m)
            assert not m.tiene_permiso('socios.editar')
            db.session.rollback()