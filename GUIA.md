# Guía de uso del sistema FRR

Cómo encender el sistema, cargar los datos de un emprendimiento, calcular su índice, simular
escenarios y correr la validación Delphi. Pensada para usarse con el programa abierto al lado.

---

## 1. Encender y apagar

**Para encenderlo**, abra PowerShell y pegue estas dos líneas:

```
cd C:\Users\59398\proyectos_tecnologicos\rentabilidad-regenerativa
.venv\Scripts\python.exe manage.py runserver
```

Cuando aparezca `Starting development server at http://127.0.0.1:8000/`, abra esa dirección en
el navegador. **Deje la terminal abierta**: si la cierra, el sistema se apaga.

**Para apagarlo**: `Ctrl + C` en la terminal, o cierre la ventana. Los datos no se pierden.

**Para respaldar todo**: copie el archivo `db.sqlite3`. Ese solo archivo contiene todos sus
emprendimientos, mediciones, expertos y respuestas. Hágalo antes de cada avance importante.

Direcciones fijas: `http://127.0.0.1:8000/` para el sistema, `http://127.0.0.1:8000/admin/` para
cargar datos (usuario `admin`, contraseña `admin` — cámbielos antes de mostrarlo fuera de su
computadora).

---

## 2. Qué hay en cada pantalla

| Menú | Objetivo | Para qué sirve |
|---|---|---|
| **Tablero** | — | Inicio. Avance de los cinco objetivos y últimas evaluaciones |
| **Bibliometría** | 1 | Matriz bibliográfica y flujo PRISMA |
| **Framework** | 2 | Las 4 dimensiones, variables y 17 indicadores con sus cortes |
| **Emprendimientos** | 2 y 3 | Los casos evaluados; aquí se calcula el índice |
| **Escenarios** | 4 | Optimista, esperado, pesimista y sensibilidad |
| **RNA** | 3 | Entrenamiento de la red neuronal y predicción |
| **Delphi** | 5 | Expertos, rondas, cuestionario, IVC y W de Kendall |
| **Admin** | — | Donde se crean y editan todos los datos |

Regla práctica: el **Admin** es para *escribir* datos; los demás módulos son para *calcular y
leer* resultados.

---

## 3. Evaluar su primer emprendimiento real

1. **Cree el emprendimiento.** `/admin/` → Emprendimientos → Agregar. Nombre, sector, ciudad,
   empleados.
2. **Cree el período.** Dentro del emprendimiento, tabla Períodos: año, **ventas**, **costos
   fijos** y **costos variables**. Con esos tres números el sistema calcula solo el punto de
   equilibrio y cuántas veces las ventas lo superan.
3. **Cargue las mediciones.** Períodos → abra el período → tabla Mediciones. Una fila por
   indicador: valor y fuente del dato. No necesita los 17 de golpe; el sistema calcula con los
   que tenga y marca los faltantes como «sin dato».
4. **Calcule el índice.** Emprendimientos → su caso → **Calcular IRR**. Para dejarlo en el
   historial, pulse **Guardar evaluación**.
5. **Simule los escenarios.** **Simular escenarios** → **Recalcular y guardar**.

Repita el paso 3 para cada año: el framework cobra fuerza cuando compara períodos.

---

## 4. Cómo leer el resultado

Escala de niveles, igual para las cuatro dimensiones:

| Nivel | Nombre | Criterio |
|---|---|---|
| 0 | Degenerativo | Reduce la capacidad del capital |
| 1 | Mitigado | Menos daño, balance aún negativo |
| 2 | Neutro / sostenible | Balance ≈ 0, se mantiene |
| 3 | Restaurativo | Recupera capacidad perdida |
| 4 | Regenerativo | Supera la línea base y el efecto persiste |

| Lo que ve | Qué significa | Qué hacer con eso |
|---|---|---|
| **IRR** (el número grande) | De 0 a 1; resume las cuatro dimensiones | Sirve para **comparar y ordenar**. Por sí solo no decide nada |
| **Mínimo dimensional** | Nivel de la dimensión más débil | **Este es el que califica.** Menor a 3 → no es regenerativo, sea cual sea el IRR |
| **Cuello de botella** | Qué dimensión frena al conjunto | Ahí va la recomendación de mejora |
| **Elasticidad** | Cuánto sube el índice si esa dimensión sube un nivel | Ordena las intervenciones. La primera fila es la prioridad |

**Ejemplo que conviene entender.** Raíz Andina obtiene IRR = 0,8108 —alto— y aun así *no
califica*: su dimensión operativa quedó en 2,98 y no llegó a 3. Eso es precisamente lo que un
puntaje ESG convencional no hace, porque deja que las dimensiones fuertes tapen a la débil.
El índice ordena; el mínimo califica.

**Si una dimensión cae a nivel 0, el índice completo se vuelve 0.** No es un error: es la
propiedad central del framework.

---

## 5. Escenarios y sensibilidad

**Los tres escenarios.** El *factor* es cuánto mejoran o empeoran todos los indicadores a la
vez: 1,15 = «15 % mejor», 0,85 = «15 % peor». El sistema respeta el sentido de cada indicador:
en residuos o consumo energético, «mejor» significa **menos**.

**El análisis de sensibilidad.** Mueve una dimensión a la vez (±10 % por defecto) y mide cuánto
se desplaza el índice. La columna *Amplitud* ordena las dimensiones de la más influyente a la
menos: responde con números a «¿qué variables gobiernan su modelo?».

---

## 6. Ajustar los cortes y los pesos

**Cortes (c1–c4).** Marcan dónde empieza cada nivel de un indicador. En «Margen neto ajustado»:
c1=0, c2=5, c3=12, c4=20 → un margen del 15 % es nivel 3; uno del 22 %, nivel 4.
Se editan en `/admin/` → **Indicadores (KPIs)**. El cambio se aplica de inmediato.

Justifíquelos siempre: referencia sectorial, dato del GEM o del INEC, promedio de la muestra, o
consenso de los expertos. Anote de dónde salió cada corte — se lo van a preguntar.

**Pesos (w).** Cada dimensión pesa distinto. Vienen en 0,30 · 0,25 · 0,22 · 0,23 y no tienen que
sumar 1: el sistema los normaliza. Se editan en `/admin/` → **Dimensiones**. Calibrarlos con el
panel de expertos es un uso legítimo y esperable de la ronda Delphi.

---

## 7. La red neuronal

La red aprende a estimar el índice a partir de los indicadores. Como todavía no existe una base
grande de emprendimientos medidos con este framework, el sistema genera casos simulados a partir
del propio modelo y entrena con ellos — la salida que el protocolo dejó prevista.

**Para entrenarla:** módulo RNA → **Entrenar**. Los valores por defecto (600 muestras, 8
neuronas, 300 épocas) funcionan bien y tardan segundos.

| Métrica | Qué mide | Qué buscar |
|---|---|---|
| **R²** | Cuánto del comportamiento del índice explica la red | Cerca de 1. El entrenamiento actual dio **0,91** |
| **RMSE** | Error típico, en unidades del índice | Cerca de 0. Actualmente **0,026** |
| **MAE** | Error promedio absoluto | Similar al RMSE, castiga menos los errores grandes |

En cada evaluación verá lado a lado la predicción de la red y el cálculo analítico. Esa
diferencia es el error del modelo en ese caso concreto: material directo para su capítulo de
resultados.

---

## 8. Validación Delphi

1. **Registre a los expertos.** `/admin/` → Expertos. El sistema marca solo si cada uno cumple
   los criterios del protocolo: maestría o doctorado y cinco años de experiencia.
2. **Cree la ronda.** `/admin/` → Rondas. En *Observaciones* anote después qué ajustó tras esa
   ronda: es evidencia del proceso iterativo y se cita en la tesis.
3. **Registre las respuestas.** Delphi → Cuestionario → elija al experto → marque de 1 a 5 los 12
   ítems → Guardar. Si aplicó el cuestionario por Google Forms o Tally, transcríbalo aquí: el
   cálculo necesita tener las respuestas dentro.
4. **Lea los resultados.** Delphi → Resultados: IVC por ítem, S-CVI global, W de Kendall con su
   chi-cuadrado, y qué ítems reformular antes de la siguiente ronda.

**Un punto que le van a preguntar en la defensa.** Puede pasar que el S-CVI dé 1,0 (acuerdo
perfecto) y la W de Kendall apenas 0,46. No es contradicción. La W mide concordancia en el
*ordenamiento* de los ítems: si los expertos califican casi todo con 5, casi todo queda empatado
y el coeficiente se hunde aunque el acuerdo sea total. Es el **efecto techo** de la escala
Likert. El sistema lo detecta, declara el consenso con base en el S-CVI y la dispersión, y
muestra la explicación en pantalla — puede citarla tal cual.

---

## 9. Bibliometría y PRISMA

**Matriz bibliográfica.** `/admin/` → Matriz bibliográfica. Guarda autores, año, revista, base,
DOI, metodología, variables y hallazgos. Si excluye una referencia, desmarque *Incluida* y
escriba el motivo: esa trazabilidad es lo que exige PRISMA.

**Registro PRISMA.** `/admin/` → Registro PRISMA. Siete cifras: identificados, duplicados,
cribados, excluidos en cribado, textos completos evaluados, excluidos en elegibilidad e
incluidos. Vienen con números de ejemplo — **reemplácelos por los suyos** cuando termine la
búsqueda real.

---

## 10. Si algo falla

| Lo que ve | Por qué pasa | Cómo se soluciona |
|---|---|---|
| «No se puede acceder a este sitio» | El sistema está apagado | Ejecute las dos líneas de la sección 1 |
| `That port is already in use` | Ya hay una copia encendida | Use la que corre, o `manage.py runserver 8001` |
| IRR = 0, «Índice anulado» | Una dimensión quedó en nivel 0 | No es error. Vea qué indicador está bajo su corte c1 |
| «Sin datos suficientes» | El período no tiene mediciones | Cárguelas desde el Admin (sección 3, paso 3) |
| La evaluación no está en el historial | Se calculó pero no se guardó | Pulse **Guardar evaluación** |
| «Aún no hay un modelo de RNA entrenado» | Nunca se entrenó | Módulo RNA → Entrenar |
| Quiere empezar de cero | — | Borre `db.sqlite3`, luego `manage.py migrate` y `manage.py cargar_framework` |

**Comprobar que todo sigue sano** tras cualquier cambio:

```
.venv\Scripts\python.exe manage.py test
```

Debe terminar con `OK` y 58 pruebas. Si dice `FAILED`, algo que se cambió alteró el
comportamiento del cálculo.
