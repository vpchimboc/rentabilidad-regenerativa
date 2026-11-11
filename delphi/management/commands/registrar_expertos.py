"""Panel de expertos del cuestionario FRR: registra los expertos reales y elimina los anteriores.

    manage.py registrar_expertos              → muestra lo que haría (no guarda)
    manage.py registrar_expertos --aplicar    → registra el panel y elimina a los demás expertos,
                                                con sus respuestas, dictámenes y resultados de ronda

Solo se registran los datos aportados por la investigación. Grado (si no se conoce), años de
experiencia y publicaciones quedan vacíos o en 0 hasta completarlos en el administrador (sin ellos no se marca «cumple criterios»).
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from administracion.models import registrar
from delphi.models import Experto, ResultadoRonda

PANEL = [
    {
        "nombre": "Dr. Hayrold José Ureña Espaillat",
        "grado": "PHD",
        "institucion": "Ministerio de Relaciones Exteriores de la República Dominicana (MIREX) · "
                       "Director de Ciencia, Tecnología y Medio Ambiente",
        "pais": "República Dominicana",
        "area": "Ingeniero Industrial · Doctor en Ciencias Económicas, Empresariales y Jurídicas · "
                "Investigador científico, docente y consultor",
    },
    {
        "nombre": "Dr. Yussef Salomón Quirarte",
        "grado": "PHD",
        "institucion": "Desarrollo Profesional SyS · Director General",
        "pais": "",
        "area": "Ingeniero Industrial · Máster en Administración y Dirección de Empresas · "
                "Doctorado en Negocios Sostenibles",
    },
    {
        "nombre": "Diego Armando Cale Pillco",
        "grado": "",
        "institucion": "Instituto Superior Tecnológico del Azuay · Docente",
        "pais": "Ecuador",
        "area": "",
    },
    {
        "nombre": "Verónica Paulina Chimbo Coronel",
        "grado": "",
        "institucion": "Instituto Superior Tecnológico del Azuay · Docente",
        "pais": "Ecuador",
        "area": "",
    },
]


class Command(BaseCommand):
    help = "Registra el panel de expertos reales y elimina a los expertos anteriores."

    def add_arguments(self, parser):
        parser.add_argument("--aplicar", action="store_true")

    @transaction.atomic
    def handle(self, *args, aplicar, **opts):
        nombres = [e["nombre"] for e in PANEL]
        sobrantes = Experto.objects.exclude(nombre__in=nombres)
        for e in sobrantes:
            self.stdout.write(f"  eliminar: {e.nombre} ({e.respuestas.count()} respuestas)")
        for datos in PANEL:
            existe = Experto.objects.filter(nombre=datos["nombre"]).exists()
            self.stdout.write(f"  {'actualizar' if existe else 'registrar'}: {datos['nombre']}")
        if not aplicar:
            self.stdout.write(self.style.WARNING("Simulación: no se guardó nada. Use --aplicar."))
            return
        eliminados = sobrantes.count()
        sobrantes.delete()  # en cascada: respuestas y dictámenes de esos expertos
        ResultadoRonda.objects.all().delete()  # los resultados calculados con ellos ya no son válidos
        for datos in PANEL:
            Experto.objects.update_or_create(
                nombre=datos["nombre"],
                defaults={**datos, "activo": True},
                create_defaults={**datos, "activo": True, "anios_experiencia": 0, "publicaciones": 0},
            )
        registrar("CONFIG", None, "Experto", f"Panel de expertos registrado ({len(PANEL)}); eliminados {eliminados}")
        self.stdout.write(self.style.SUCCESS(f"Panel registrado: {len(PANEL)} expertos · eliminados {eliminados}."))
