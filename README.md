# FRR · Framework de Rentabilidad Regenerativa

Soporte informático del protocolo de titulación **«Más allá del Break-even: Propuesta de un
Framework de Rentabilidad Regenerativa para la Evaluación de Emprendimientos de Triple
Impacto»** (Norma Liliana Pañi Ochoa · Ingeniería Industrial · Universidad Católica de Cuenca ·
tutor: Ing. Santiago Moscoso Bernal, PhD.).

Django 6.1 + SQLite. Sin dependencias externas más allá de Django: la red neuronal y toda la
estadística están implementadas en Python puro para que el proyecto corra en cualquier equipo.

## Puesta en marcha

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe manage.py migrate
.venv/Scripts/python.exe manage.py cargar_framework
.venv/Scripts/python.exe manage.py cargar_demo
.venv/Scripts/python.exe manage.py runserver
```

Abrir <http://127.0.0.1:8000/>. El panel de administración está en `/admin/`
(usuario `admin`, contraseña `admin` si se creó con el comando de demostración; en un equipo
nuevo, crear uno con `manage.py createsuperuser`).

## Correspondencia con los objetivos del protocolo

| Objetivo específico | Módulo | Ruta |
|---|---|---|
| 1. Revisión bibliométrica y documental | `bibliometria` | `/bibliometria/` |
| 2. Dimensiones, variables e indicadores | `framework` | `/framework/` |
| 3. Modelado mediante Redes Neuronales Artificiales | `rna` | `/rna/` |
| 4. Simulación de escenarios y sensibilidad | `escenarios` | `/escenarios/` |
| 5. Validación mediante método Delphi | `delphi` | `/delphi/` |

Instrumentos del protocolo implementados: matriz bibliográfica, registro PRISMA, matriz de
construcción del framework, matriz de indicadores (KPIs), cuestionario Delphi con escala
Likert de cinco niveles y matriz de validación (IVC, S-CVI y W de Kendall).

## El modelo de cálculo (FRR 1.0)

Implementa la especificación *Fase 2. Diseño conceptual y operacional del FRR* (versión
científica 2.0, carpeta `Documentación Base`).

**Arquitectura.** D1 rentabilidad económica · D2 regeneración ambiental · D3 valor social ·
D4 excelencia operacional, con 42 KPI candidatos (E1–E7, A1–A10, S1–S13, O1–O12), cada uno con
fórmula, componentes, rol, estado (candidato, activo, excluido) y tipo de normalización.

**Dos niveles de evaluación.**

1. *Salvaguardas* `R = G1 × G2 × G3 × G4 × G5`: viabilidad económica, no daño social crítico,
   resultado ambiental positivo (A10 frente a línea base), trazabilidad y cobertura, y
   persistencia temporal. Si alguna es desconocida, R es «indeterminado», nunca 0.
2. *Puntuaciones descriptivas*, solo con cobertura suficiente:

```
z    = min[1, max(0, (x − L)/(U − L))]       (beneficio; costo y objetivo análogos)
S(d) = Σ w·z / Σ w                            (KPI observados y puntuables)
C(d) = Σ w observados / Σ w aplicables        (NA documentados fuera del denominador)
IRR  = Π (ε + (1−ε)·S(d))^α(d)                IRR₀ = Π S(d)^α(d)
```

**Clasificación.** (a) información insuficiente · (b) inviabilidad económica · (c) viabilidad
sin evidencia regenerativa · (d) desempeño sostenible o de transición · (e) regeneración
verificable (solo con R = 1).

**Reglas de datos.** Los faltantes se registran como ND, NA o NV y nunca como cero. Un KPI sin
referencias L/U justificadas se registra pero no se puntúa. Los pesos α son iguales (0,25)
hasta la validación experta. Cada evaluación guarda la versión y los parámetros usados.

`manage.py calcular_referencias` propone L/U provisionales (percentiles P10–P90 de la muestra
observada) y los guarda solo con `--aplicar`, dejando constancia en la auditoría.

## La red neuronal

Perceptrón multicapa `n → h → 1` (tanh en la capa oculta, sigmoide en la salida). Sus
entradas son los KPI con referencias justificadas y su salida es el IRR. Es **exploratoria**:
entrenada con escenarios simulados mide la capacidad de reproducir el framework y no
constituye validación empírica. No se entrena si el IRR no es calculable, y no predice si
falta alguna entrada (los faltantes nunca se reemplazan por cero).

## Estadística Delphi

- **IVC por ítem**: proporción de expertos que califican 4 o 5. Umbral 0,80.
- **S-CVI/Ave**: promedio de los IVC.
- **W de Kendall** con corrección por empates, más su χ² y grados de libertad.

Advertencia metodológica implementada en el código: el W mide concordancia en el
*ordenamiento* de los ítems. Cuando los expertos coinciden en calificar casi todo con el valor
máximo, los rangos se vuelven empates y el W cae aunque el acuerdo sea total — es el efecto
techo de la escala Likert. En ese caso el sistema declara el consenso sobre la base del S-CVI
y de la dispersión observada, y lo deja explícito en el informe en lugar de reportar un falso
desacuerdo.

## Interfaz y administración

- **Navegación:** barra lateral con iconos Lucide (SVG incrustado mediante `{% icono %}`, sin CDN).
  Solo enlaza módulos con pantalla funcional, y el grupo Administración aparece solo para quien
  tiene permiso. La barra superior incluye la ruta de navegación, la búsqueda global de
  emprendimientos, la fecha y el menú de la cuenta.
- **Tablero ejecutivo (`/`):** ingresos, costos, resultado operativo, margen, punto de equilibrio,
  rentables y alertas, con filtros de ejercicio, sector, provincia y origen. Todo sale de los
  períodos guardados. La variación anual compara solo emprendimientos con datos en ambos años.
- **Administración (`/administracion/`):** panel con alertas de integridad, usuarios (búsqueda,
  filtros, paginación, alta, edición y activación con confirmación), roles con matriz de permisos
  (consultar, crear, editar, eliminar, exportar y administrar), configuración por secciones y
  auditoría de solo lectura.
- **Seguridad:** el acceso se valida en el servidor (permiso `administracion.administrar_sistema`).
  El sistema impide dejarse sin administrador activo y solo un superusuario puede conceder la
  condición de superusuario. El login está en `/cuenta/ingresar/`.
- **CSS:** un único `static/css/frr.css`, con variables de diseño y componentes (layout, tarjetas,
  KPI, tablas, formularios, botones, etiquetas, alertas, paginación, estados vacíos, modal y
  gráficos de barras HTML).

## Comandos disponibles

| Comando | Qué hace |
|---|---|
| `manage.py cargar_framework` | Carga dimensiones, variables, indicadores y el cuestionario Delphi |
| `manage.py cargar_demo` | Carga tres emprendimientos de ejemplo, expertos, dos rondas Delphi, referencias y PRISMA |
| `manage.py preparar_dataset_publico --companias … --ranking … --blab …` | Regenera `emprendimientos/datos/emprendimientos_ecuador.csv` desde los archivos oficiales de la SCVS y el directorio de B Lab |
| `manage.py importar_emprendimientos [archivo.csv]` | Carga (o actualiza, sin duplicar) los emprendimientos del CSV, con sus períodos y mediciones |
| `manage.py test` | Ejecuta las 70 pruebas del motor de cálculo, la RNA, Delphi, la carga de datos, la administración y las vistas |

## Datos de demostración

Los tres emprendimientos cargados por `cargar_demo` (Raíz Andina, Textiles Sisa,
Ecoservicios del Austro) son **casos ilustrativos construidos para probar el framework**; no
corresponden a empresas reales. Los datos reales se cargan desde `/admin/`.

## Emprendimientos ecuatorianos de fuentes públicas

`emprendimientos/datos/emprendimientos_ecuador.csv` contiene 120 emprendimientos reales,
cada uno con su fuente y URL de verificación:

| Origen | Casos | Criterio |
|---|---|---|
| B Lab · directorio *Find a B Corp* | 43 | Todas las Empresas B con sede en Ecuador (consulta 2026-10-10). 17 se identifican sin ambigüedad en la SCVS y traen RUC y estados financieros 2025 |
| SCVS · ranking empresarial 2025 | 77 | SAS (Ley Orgánica de Emprendimiento e Innovación) de Azuay, 1–49 empleados, ventas > 0, estratificadas por sección CIIU (A, C, G, I, J, M), mayores ventas primero |

Archivos oficiales de la SCVS: <https://appscvsmovil.supercias.gob.ec/ranking/reporte.html>
(`recursos/bi_compania.csv` y `recursos/bi_ranking.csv`, unos 430 MB; no se versionan).

Indicadores que se derivan, porque su fórmula coincide con un dato publicado:
`ECO_ROI` (= ROA), `ECO_AUTON`, `OPE_PROD` y `OPE_COSTO`; además ventas y costos del período
(costos variables = costo de ventas; costos fijos = gastos de administración y ventas, una
aproximación). **Las dimensiones social y ambiental no tienen fuente pública**: quedan sin dato
y el sistema informa «Evaluación incompleta», nunca «degenerativa». Para que un caso califique
hay que levantar esas mediciones en campo.

## Estructura

```
config/          configuración del proyecto
core/            tablero y trazabilidad de objetivos
framework/       dimensiones, variables, indicadores y motor de cálculo del IRR
emprendimientos/ casos, períodos, mediciones y evaluaciones
escenarios/      simulación optimista/esperado/pesimista y sensibilidad
rna/             perceptrón multicapa y generación de datos simulados
delphi/          expertos, rondas, cuestionario, IVC y W de Kendall
bibliometria/    matriz bibliográfica y registro PRISMA
```
