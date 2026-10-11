"""Seguridad y funcionamiento del módulo de administración, tablero y lista."""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from administracion.models import ConfiguracionSistema, RegistroActividad
from emprendimientos.models import Emprendimiento, Periodo

User = get_user_model()
CLAVE = "Clave-Segura-2026"
RUTAS_ADMIN = ["adm_panel", "adm_usuarios", "adm_usuario_crear", "adm_roles", "adm_configuracion", "adm_auditoria"]


class AccesoTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser("jefa", "jefa@ejemplo.ec", CLAVE)
        cls.analista = User.objects.create_user("analista", "a@ejemplo.ec", CLAVE)

    def test_anonimo_es_redirigido_al_login(self):
        for nombre in RUTAS_ADMIN:
            with self.subTest(ruta=nombre):
                r = self.client.get(reverse(nombre))
                self.assertEqual(r.status_code, 302)
                self.assertIn(reverse("login"), r["Location"])

    def test_usuario_sin_privilegios_recibe_403_y_queda_auditado(self):
        self.client.force_login(self.analista)
        for nombre in RUTAS_ADMIN:
            with self.subTest(ruta=nombre):
                self.assertEqual(self.client.get(reverse(nombre)).status_code, 403)
        # Ni siquiera por POST directo (ocultar botones no basta).
        r = self.client.post(reverse("adm_usuario_estado", args=[self.admin.pk]), {"confirmado": "1"})
        self.assertEqual(r.status_code, 403)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)
        self.assertTrue(RegistroActividad.objects.filter(accion="DENEGADO", usuario=self.analista).exists())

    def test_administrador_ve_todas_las_pantallas(self):
        self.client.force_login(self.admin)
        for nombre in RUTAS_ADMIN:
            with self.subTest(ruta=nombre):
                self.assertEqual(self.client.get(reverse(nombre)).status_code, 200)

    def test_menu_de_administracion_solo_para_administradores(self):
        self.assertNotContains(self.client.get("/"), reverse("adm_usuarios"))
        self.client.force_login(self.analista)
        self.assertNotContains(self.client.get("/"), reverse("adm_usuarios"))
        self.client.force_login(self.admin)
        self.assertContains(self.client.get("/"), reverse("adm_usuarios"))

    def test_login_y_logout_quedan_en_auditoria(self):
        r = self.client.post(reverse("login"), {"username": "jefa", "password": CLAVE})
        self.assertEqual(r.status_code, 302)
        self.client.post(reverse("logout"))
        self.client.post(reverse("login"), {"username": "jefa", "password": "mala"})
        acciones = list(RegistroActividad.objects.values_list("accion", flat=True))
        for accion in ("LOGIN", "LOGOUT", "LOGIN_FALLIDO"):
            self.assertIn(accion, acciones)
        # La contraseña nunca se guarda en el registro.
        for r in RegistroActividad.objects.all():
            self.assertNotIn("mala", str(r.detalle) + r.objeto)


class UsuariosTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser("jefa", "jefa@ejemplo.ec", CLAVE)
        cls.rol = Group.objects.create(name="Analista")

    def setUp(self):
        self.client.force_login(self.admin)

    def test_crear_usuario_con_rol_y_validaciones(self):
        url = reverse("adm_usuario_crear")
        r = self.client.post(url, {"username": "nueva", "email": "jefa@ejemplo.ec",
                                   "password1": "123", "password2": "456", "is_active": "on"})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Ya existe otro usuario con este correo")
        self.assertContains(r, "Las contraseñas no coinciden")
        r = self.client.post(url, {"username": "nueva", "email": "nueva@ejemplo.ec", "first_name": "Ana",
                                   "password1": CLAVE, "password2": CLAVE, "is_active": "on",
                                   "groups": [self.rol.pk]})
        self.assertRedirects(r, reverse("adm_usuarios"))
        nueva = User.objects.get(username="nueva")
        self.assertTrue(nueva.check_password(CLAVE))
        self.assertEqual(list(nueva.groups.all()), [self.rol])
        self.assertTrue(RegistroActividad.objects.filter(accion="CREAR", entidad="Usuario", objeto="nueva").exists())

    def test_busqueda_filtros_y_paginacion(self):
        for i in range(30):
            u = User.objects.create_user(f"persona{i:02d}", f"p{i}@ejemplo.ec", CLAVE, is_active=i % 2 == 0)
            if i < 5:
                u.groups.add(self.rol)
        url = reverse("adm_usuarios")
        self.assertEqual(self.client.get(url, {"q": "persona0"}).context["total"], 10)
        self.assertEqual(self.client.get(url, {"estado": "inactivo"}).context["total"], 15)
        self.assertEqual(self.client.get(url, {"rol": self.rol.pk}).context["total"], 5)
        pagina = self.client.get(url).context["pagina"]
        self.assertEqual(pagina.paginator.num_pages, 2)

    def test_desactivar_exige_confirmacion(self):
        otro = User.objects.create_user("otro", "o@ejemplo.ec", CLAVE)
        url = reverse("adm_usuario_estado", args=[otro.pk])
        r = self.client.post(url)  # sin confirmar: muestra la confirmación
        self.assertContains(r, "Desactivar cuenta")
        otro.refresh_from_db()
        self.assertTrue(otro.is_active)
        self.client.post(url, {"confirmado": "1"})
        otro.refresh_from_db()
        self.assertFalse(otro.is_active)
        self.assertTrue(RegistroActividad.objects.filter(accion="DESACTIVAR", objeto="otro").exists())

    def test_ultimo_administrador_no_puede_quedar_bloqueado(self):
        # No puede desactivarse a sí mismo.
        self.client.post(reverse("adm_usuario_estado", args=[self.admin.pk]), {"confirmado": "1"})
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)
        # Otro superusuario desactivado no cuenta: quitarse la condición de superusuario
        # dejaría el sistema sin administradores.
        r = self.client.post(reverse("adm_usuario_editar", args=[self.admin.pk]), {
            "username": "jefa", "email": "jefa@ejemplo.ec", "is_active": "on",
        })
        self.assertContains(r, "sin ningún administrador activo")
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_superuser)

    def test_solo_un_superusuario_concede_superusuario(self):
        rol_admin = Group.objects.create(name="Administración")
        rol_admin.permissions.add(Permission.objects.get(codename="administrar_sistema"))
        gestor = User.objects.create_user("gestor", "g@ejemplo.ec", CLAVE)
        gestor.groups.add(rol_admin)
        otro = User.objects.create_user("otro", "o@ejemplo.ec", CLAVE)
        self.client.force_login(gestor)
        self.client.post(reverse("adm_usuario_editar", args=[otro.pk]), {
            "username": "otro", "email": "o@ejemplo.ec", "is_active": "on", "is_superuser": "on",
        })
        otro.refresh_from_db()
        self.assertFalse(otro.is_superuser)


class RolesYConfiguracionTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser("jefa", "jefa@ejemplo.ec", CLAVE)

    def setUp(self):
        self.client.force_login(self.admin)

    def test_matriz_de_permisos_concede_y_retira(self):
        self.client.post(reverse("adm_roles"), {"nombre": "Consulta"})
        rol = Group.objects.get(name="Consulta")
        url = reverse("adm_rol", args=[rol.pk])
        self.client.post(url, {"celda": ["emprendimientos:view", "framework:view"]})
        codigos = set(rol.permissions.values_list("codename", flat=True))
        self.assertIn("view_emprendimiento", codigos)
        self.assertIn("view_indicador", codigos)
        self.assertNotIn("add_emprendimiento", codigos)
        usuaria = User.objects.create_user("lectora", "l@ejemplo.ec", CLAVE)
        usuaria.groups.add(rol)
        self.assertTrue(User.objects.get(pk=usuaria.pk).has_perm("emprendimientos.view_emprendimiento"))
        self.client.post(url, {})
        self.assertEqual(rol.permissions.count(), 0)
        self.assertTrue(RegistroActividad.objects.filter(accion="PERMISOS", objeto="Consulta").exists())

    def test_no_se_retira_el_rol_que_sostiene_al_unico_administrador(self):
        rol = Group.objects.create(name="Administración")
        permiso = Permission.objects.get(codename="administrar_sistema")
        rol.permissions.add(permiso)
        gestor = User.objects.create_user("gestor", "g@ejemplo.ec", CLAVE)
        gestor.groups.add(rol)
        self.admin.is_active = False
        self.admin.save()
        self.client.force_login(gestor)
        self.client.post(reverse("adm_rol", args=[rol.pk]), {})
        self.assertTrue(rol.permissions.filter(pk=permiso.pk).exists())
        self.client.post(reverse("adm_rol_eliminar", args=[rol.pk]), {"confirmado": "1"})
        self.assertTrue(Group.objects.filter(pk=rol.pk).exists())

    def test_configuracion_registra_valor_anterior(self):
        datos = {
            "nombre_sistema": "FRR", "institucion": "UCACUE", "responsable": "", "moneda": "USD",
            "simbolo_moneda": "$", "decimales": 2, "formato_numerico": "EC", "iva_porcentaje": "15",
            "impuesto_renta_porcentaje": "25", "participacion_trabajadores": "15", "anio_analisis": "",
            "umbral_alerta_break_even": "1.2", "registros_por_pagina": 25,
        }
        r = self.client.post(reverse("adm_configuracion"), datos)
        self.assertRedirects(r, reverse("adm_configuracion"))
        evento = RegistroActividad.objects.get(accion="CONFIG")
        self.assertEqual(evento.detalle["cambios"]["umbral_alerta_break_even"], ["1.00", "1.2"])
        datos["iva_porcentaje"] = "150"
        r = self.client.post(reverse("adm_configuracion"), datos)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(ConfiguracionSistema.actual().iva_porcentaje, 15)


class TableroYListaTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("cargar_framework", verbosity=0)
        cls.a = Emprendimiento.objects.create(nombre="Alfa", sector="AGRO", provincia="AZUAY", fuente="SCVS")
        cls.b = Emprendimiento.objects.create(nombre="Beta", sector="SERV", provincia="GUAYAS")
        Periodo.objects.create(emprendimiento=cls.a, anio=2025, ventas=1000, costos_fijos=200, costos_variables=500)
        Periodo.objects.create(emprendimiento=cls.a, anio=2024, ventas=800, costos_fijos=200, costos_variables=400)
        Periodo.objects.create(emprendimiento=cls.b, anio=2025, ventas=500, costos_fijos=300, costos_variables=400)

    def test_kpis_proceden_de_la_base(self):
        d = self.client.get("/").context["d"]
        self.assertEqual(d["anio"], 2025)
        self.assertEqual(d["totales"]["ingresos"], 1500)
        self.assertEqual(d["totales"]["costos"], 1400)
        self.assertEqual(d["totales"]["resultado"], 100)
        self.assertEqual(d["rentables"], 1)
        self.assertEqual([f["periodo"].emprendimiento for f in d["alertas"]], [self.b])
        # Comparación coherente: solo Alfa tiene ambos años → (1000 − 800) / 800.
        self.assertEqual(d["comparacion"]["n"], 1)
        self.assertAlmostEqual(d["comparacion"]["ingresos"], 25.0)

    def test_filtros_del_tablero(self):
        d = self.client.get("/", {"provincia": "AZUAY"}).context["d"]
        self.assertEqual(d["totales"]["ingresos"], 1000)
        d = self.client.get("/", {"origen": "manual"}).context["d"]
        self.assertEqual(d["total_emprendimientos"], 1)
        d = self.client.get("/", {"anio": "2024"}).context["d"]
        self.assertEqual(d["totales"]["ingresos"], 800)

    def test_estado_vacio_sin_periodos(self):
        Periodo.objects.all().delete()
        r = self.client.get("/")
        self.assertContains(r, "No hay períodos financieros para esta selección")

    def test_lista_busca_filtra_y_pagina(self):
        url = reverse("emprendimiento_lista")
        self.assertEqual(self.client.get(url, {"q": "alf"}).context["total"], 1)
        self.assertEqual(self.client.get(url, {"sector": "SERV"}).context["total"], 1)
        self.assertEqual(self.client.get(url, {"pagina": "999"}).status_code, 200)

    def test_exportar_requiere_permiso(self):
        url = reverse("emprendimiento_exportar")
        self.assertEqual(self.client.get(url).status_code, 302)
        User.objects.create_user("lectora", "l@ejemplo.ec", CLAVE)
        self.client.login(username="lectora", password=CLAVE)
        self.assertEqual(self.client.get(url).status_code, 403)
        User.objects.create_superuser("jefa", "j@ejemplo.ec", CLAVE)
        self.client.login(username="jefa", password=CLAVE)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200)
        self.assertIn("Alfa", r.content.decode("utf-8"))
        self.assertTrue(RegistroActividad.objects.filter(accion="EXPORTAR").exists())
