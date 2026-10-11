"""Carga la estructura del Framework: dimensiones, variables, indicadores y cortes.

Los indicadores cubren las variables de entrada declaradas en el protocolo para la
RNA: rentabilidad, ROI, punto de equilibrio, costos operativos, consumo energético,
eficiencia operativa, residuos, impacto social e indicadores ambientales.

Uso:  python manage.py cargar_framework
"""

from django.core.management.base import BaseCommand

from delphi.models import Item
from framework.models import Dimension, Indicador, Variable

MAY, MEN = "MAY", "MEN"

ESTRUCTURA = [
    {
        "codigo": "D1",
        "nombre": "Económico-financiera",
        "peso": 0.30,
        "orden": 1,
        "descripcion": "Capacidad de generar excedente propio más allá del punto de equilibrio, "
                       "descontando los costos que la empresa transfiere a terceros.",
        "variables": [
            {
                "codigo": "V1.1",
                "nombre": "Rentabilidad",
                "indicadores": [
                    dict(codigo="ECO_MARGEN", nombre="Margen neto ajustado por externalidades",
                         unidad="%", formula="(Utilidad neta − costos externalizados) / Ventas × 100",
                         direccion=MAY, peso=1.2, c1=0, c2=5, c3=12, c4=20),
                    dict(codigo="ECO_ROI", nombre="Retorno sobre la inversión (ROI)",
                         unidad="%", formula="Utilidad / Inversión × 100",
                         direccion=MAY, peso=1.0, c1=0, c2=8, c3=15, c4=25),
                ],
            },
            {
                "codigo": "V1.2",
                "nombre": "Solidez sobre el break-even",
                "indicadores": [
                    dict(codigo="ECO_PE", nombre="Ventas sobre el punto de equilibrio",
                         unidad="veces", formula="Ventas / Punto de equilibrio",
                         direccion=MAY, peso=1.3, c1=0.9, c2=1.0, c3=1.4, c4=1.8),
                    dict(codigo="ECO_REINV", nombre="Utilidad reinvertida en capitales no financieros",
                         unidad="%", formula="Reinversión social+ambiental / Utilidad × 100",
                         direccion=MAY, peso=1.0, c1=0, c2=10, c3=25, c4=40),
                    dict(codigo="ECO_AUTON", nombre="Autonomía financiera",
                         unidad="%", formula="Ingresos operativos / Ingresos totales × 100",
                         direccion=MAY, peso=0.8, c1=50, c2=70, c3=85, c4=95),
                ],
            },
        ],
    },
    {
        "codigo": "D2",
        "nombre": "Operativa",
        "peso": 0.25,
        "orden": 2,
        "descripcion": "Eficiencia del sistema productivo entendida como el mecanismo que hace "
                       "económicamente viable la regeneración.",
        "variables": [
            {
                "codigo": "V2.1",
                "nombre": "Eficiencia y productividad",
                "indicadores": [
                    dict(codigo="OPE_EFIC", nombre="Eficiencia operativa global (OEE)",
                         unidad="%", formula="Disponibilidad × Rendimiento × Calidad × 100",
                         direccion=MAY, peso=1.2, c1=40, c2=60, c3=75, c4=85),
                    dict(codigo="OPE_PROD", nombre="Productividad por trabajador",
                         unidad="USD/empleado", formula="Ventas / Nº de empleados",
                         direccion=MAY, peso=1.0, c1=4000, c2=8000, c3=14000, c4=22000),
                ],
            },
            {
                "codigo": "V2.2",
                "nombre": "Estructura de costos",
                "indicadores": [
                    dict(codigo="OPE_COSTO", nombre="Costos operativos sobre ventas",
                         unidad="%", formula="Costos operativos / Ventas × 100",
                         direccion=MEN, peso=1.1, c1=95, c2=85, c3=72, c4=60),
                    dict(codigo="OPE_ENER", nombre="Consumo energético por unidad producida",
                         unidad="kWh/unidad", formula="Energía consumida / Unidades producidas",
                         direccion=MEN, peso=1.0, c1=3.0, c2=2.0, c3=1.2, c4=0.7),
                ],
            },
        ],
    },
    {
        "codigo": "D3",
        "nombre": "Social",
        "peso": 0.22,
        "orden": 3,
        "descripcion": "Capacidad instalada en las personas y en la red de proveedores, con la "
                       "condición de que el beneficio persista sin la intervención de la empresa.",
        "variables": [
            {
                "codigo": "V3.1",
                "nombre": "Valor social generado",
                "indicadores": [
                    dict(codigo="SOC_INGRESO", nombre="Incremento del ingreso de proveedores y trabajadores",
                         unidad="%", formula="(Ingreso actual − ingreso base) / Ingreso base × 100",
                         direccion=MAY, peso=1.2, c1=0, c2=8, c3=20, c4=35),
                    dict(codigo="SOC_CADENA", nombre="Participación del primer eslabón en el precio final",
                         unidad="%", formula="Precio pagado al productor / Precio final × 100",
                         direccion=MAY, peso=1.0, c1=10, c2=20, c3=32, c4=45),
                ],
            },
            {
                "codigo": "V3.2",
                "nombre": "Capital humano",
                "indicadores": [
                    dict(codigo="SOC_CAPAC", nombre="Horas de capacitación por trabajador al año",
                         unidad="h/año", formula="Horas de capacitación / Nº de trabajadores",
                         direccion=MAY, peso=0.9, c1=0, c2=8, c3=24, c4=40),
                    dict(codigo="SOC_AUTON", nombre="Autonomía del efecto social a 24 meses",
                         unidad="%", formula="Beneficios que persisten sin la empresa / Beneficios totales × 100",
                         direccion=MAY, peso=1.4, c1=10, c2=30, c3=60, c4=80),
                ],
            },
        ],
    },
    {
        "codigo": "D4",
        "nombre": "Ambiental",
        "peso": 0.23,
        "orden": 4,
        "descripcion": "Balance de los flujos de materia y energía: el criterio no es reducir el "
                       "daño sino incrementar la capacidad del ecosistema.",
        "variables": [
            {
                "codigo": "V4.1",
                "nombre": "Circularidad de materiales",
                "indicadores": [
                    dict(codigo="AMB_CIRC", nombre="Tasa de circularidad efectiva",
                         unidad="%", formula="Materiales reincorporados / Materiales totales × 100",
                         direccion=MAY, peso=1.1, c1=5, c2=25, c3=50, c4=70),
                    dict(codigo="AMB_RESID", nombre="Residuos no valorizados por unidad producida",
                         unidad="kg/unidad", formula="Residuos a disposición final / Unidades producidas",
                         direccion=MEN, peso=1.0, c1=1.2, c2=0.7, c3=0.3, c4=0.1),
                ],
            },
            {
                "codigo": "V4.2",
                "nombre": "Balance ecológico",
                "indicadores": [
                    dict(codigo="AMB_CARB", nombre="Balance neto de carbono",
                         unidad="tCO₂e", formula="Emisiones − capturas del período",
                         direccion=MEN, peso=1.3, c1=200, c2=0, c3=-100, c4=-300),
                    dict(codigo="AMB_AGUA", nombre="Eficiencia en el uso del agua",
                         unidad="L/unidad", formula="Agua consumida / Unidades producidas",
                         direccion=MEN, peso=0.9, c1=60, c2=40, c3=22, c4=12),
                ],
            },
        ],
    },
]

ITEMS_DELPHI = [
    ("I01", "CLA", "Definición de rentabilidad regenerativa",
     "La definición de rentabilidad regenerativa propuesta es clara y no se presta a ambigüedad."),
    ("I02", "PER", "Estructura de cuatro dimensiones",
     "Las dimensiones económica, operativa, social y ambiental son pertinentes para evaluar "
     "emprendimientos de triple impacto."),
    ("I03", "COH", "Escala de niveles 0–4",
     "La escala de cinco niveles (degenerativo a regenerativo) es coherente con los principios "
     "de la economía regenerativa."),
    ("I04", "COH", "Agregación geométrica no compensatoria",
     "La agregación mediante media geométrica ponderada es apropiada para impedir que una "
     "dimensión deficiente sea compensada por otra."),
    ("I05", "PER", "Indicadores económico-financieros",
     "Los indicadores de la dimensión económica capturan adecuadamente la rentabilidad más "
     "allá del punto de equilibrio."),
    ("I06", "PER", "Indicadores operativos",
     "Los indicadores operativos reflejan la eficiencia del sistema productivo desde la "
     "Ingeniería Industrial."),
    ("I07", "PER", "Indicadores sociales",
     "El criterio de autonomía del efecto social es pertinente para distinguir regeneración "
     "de asistencia sostenida."),
    ("I08", "PER", "Indicadores ambientales",
     "Los indicadores ambientales permiten verificar un balance neto positivo y no solo la "
     "reducción del daño."),
    ("I09", "APL", "Aplicabilidad en el contexto ecuatoriano",
     "El framework es aplicable a emprendimientos ecuatorianos de los sectores agroindustrial, "
     "manufacturero y de servicios."),
    ("I10", "FAC", "Factibilidad de la medición",
     "Un emprendimiento de tamaño pequeño o mediano puede levantar los datos que exigen los "
     "indicadores del framework."),
    ("I11", "APL", "Utilidad para la toma de decisiones",
     "El análisis de elasticidad identifica de manera útil dónde debe intervenir primero el "
     "emprendimiento."),
    ("I12", "FAC", "Modelado mediante RNA",
     "El uso de una red neuronal artificial aporta valor analítico a la estructura del framework."),
]


class Command(BaseCommand):
    help = "Carga dimensiones, variables, indicadores y el cuestionario Delphi del framework."

    def handle(self, *args, **opciones):
        for dim_data in ESTRUCTURA:
            campos_dim = {k: v for k, v in dim_data.items() if k != "variables"}
            dim, _ = Dimension.objects.update_or_create(
                codigo=campos_dim["codigo"], defaults=campos_dim
            )
            for var_data in dim_data["variables"]:
                var, _ = Variable.objects.update_or_create(
                    codigo=var_data["codigo"],
                    defaults={"dimension": dim, "nombre": var_data["nombre"]},
                )
                for orden, ind_data in enumerate(var_data["indicadores"]):
                    Indicador.objects.update_or_create(
                        codigo=ind_data["codigo"],
                        defaults={**ind_data, "variable": var, "orden": orden},
                    )

        for orden, (codigo, criterio, componente, enunciado) in enumerate(ITEMS_DELPHI):
            Item.objects.update_or_create(
                codigo=codigo,
                defaults={
                    "criterio": criterio,
                    "componente": componente,
                    "enunciado": enunciado,
                    "orden": orden,
                },
            )

        self.stdout.write(self.style.SUCCESS(
            f"Framework cargado: {Dimension.objects.count()} dimensiones, "
            f"{Variable.objects.count()} variables, {Indicador.objects.count()} indicadores, "
            f"{Item.objects.count()} ítems Delphi."
        ))
