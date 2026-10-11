# Sistema de Rentabilidad Regenerativa · Guía para la usuaria

Esta guía explica, paso a paso y sin términos técnicos, cómo usar el sistema en el día a día.

---

## 1. Encender el sistema

1. Abra **PowerShell** (menú Inicio → escriba «PowerShell» → Enter).
2. Copie y pegue estas dos líneas, presionando Enter después de cada una:

   ```
   cd C:\Users\59398\proyectos_tecnologicos\rentabilidad-regenerativa
   .venv\Scripts\python.exe manage.py runserver
   ```

3. Cuando aparezca el mensaje `Starting development server at http://127.0.0.1:8000/`, abra el
   navegador (Chrome o Edge) y entre a: **http://127.0.0.1:8000/**

> **Importante:** no cierre la ventana de PowerShell mientras use el sistema. Para apagarlo,
> presione `Ctrl + C` en esa ventana o ciérrela. Sus datos no se pierden al apagarlo.

---

## 2. Iniciar sesión

- Para **consultar** el tablero, los emprendimientos y los análisis no necesita iniciar sesión.
- Para **administrar** (usuarios, roles, configuración, auditoría o exportar datos) pulse
  **Ingresar**, arriba a la derecha, y escriba su usuario y contraseña.
- Para cerrar sesión, pulse su inicial (el círculo arriba a la derecha) → **Cerrar sesión**.

> **Primera vez:** cambie la contraseña que se le entregó. Para hacerlo, pulse su inicial →
> **Cambiar contraseña**.

---

## 3. Cómo está organizado

El menú de la izquierda agrupa las secciones:

| Sección | Para qué sirve |
|---|---|
| **Inicio** | Tablero ejecutivo con las cifras clave |
| **Emprendimientos** | Lista de casos: buscar, filtrar, ver detalle y evaluar |
| **Framework e indicadores** | Las 4 dimensiones y los 17 indicadores con sus cortes |
| **Escenarios y sensibilidad** | Simulación optimista, esperada y pesimista |
| **Red neuronal (RNA)** | Entrenamiento del modelo y predicción del índice |
| **Validación Delphi** | Expertos, cuestionario y resultados de consenso |
| **Bibliometría** | Matriz bibliográfica y flujo PRISMA |
| **Administración** | Usuarios, roles, configuración y auditoría (solo si tiene permiso) |
| **Editor de datos** | Donde se registran y editan emprendimientos, períodos y mediciones |

En el celular o la tablet, el menú se abre con el botón **☰** de la esquina superior izquierda.

**Buscador superior:** escriba el nombre, el RUC o la ciudad de un emprendimiento y presione Enter.

---

## 4. Tareas frecuentes

### Revisar el desempeño general (Inicio)
1. Elija el **Ejercicio** (año) y, si quiere, el sector, la provincia o el origen de los datos.
2. Pulse **Aplicar**.
3. Lea las tarjetas: ingresos, costos, resultado operativo, margen, punto de equilibrio,
   emprendimientos rentables y emprendimientos con alertas.
4. Más abajo, la tabla **Emprendimientos con alertas** muestra primero los casos más débiles.
   Pulse **Evaluar** para analizar uno.

### Consultar un emprendimiento
1. Menú **Emprendimientos** → busque por nombre o RUC → pulse **Ver**.
2. Ahí encontrará sus períodos (años), ventas, punto de equilibrio y mediciones.
3. El enlace de la columna **Fuente** abre el registro público que respalda los datos.

### Calcular el Índice de Rentabilidad Regenerativa (IRR)
1. En la lista o en el detalle, pulse **Evaluar** en el año que quiera analizar.
2. Revise el resultado y, si desea conservarlo en el historial, pulse **Guardar evaluación**.

### Simular escenarios
1. Desde la evaluación, pulse **Simular escenarios**.
2. Ajuste los factores (por ejemplo, 1,15 equivale a «15 % mejor») y pulse **Recalcular y guardar**.

### Registrar un emprendimiento nuevo
1. Menú **Emprendimientos** → **Registrar emprendimiento**.
2. Complete los datos generales y, en **Períodos**, el año, las ventas, los costos fijos y los
   costos variables.
3. Para cargar indicadores: abra el período y añada las **Mediciones**, una fila por indicador.
   No hace falta cargar los 17 indicadores a la vez.

### Exportar a Excel
En **Emprendimientos**, aplique los filtros que necesite y pulse **Exportar CSV**. El archivo se
abre directamente en Excel.

---

## 5. Cómo leer los resultados

| Lo que ve | Qué significa |
|---|---|
| **IRR** (de 0 a 1) | Resume las cuatro dimensiones. Sirve para **comparar y ordenar** emprendimientos |
| **Mínimo dimensional** | Nivel de la dimensión más débil. **Es el que califica**: si es menor a 3, el emprendimiento no es regenerativo |
| **Cuello de botella** | La dimensión que frena al conjunto: ahí conviene intervenir |
| **Evaluación incompleta** | Faltan mediciones en alguna dimensión, normalmente la social o la ambiental. No es un resultado negativo: indica que falta información |
| **Índice anulado** | Una dimensión quedó en nivel 0. Es una regla del modelo, no un error |
| **Resultado operativo** | Ventas menos costos. No es la utilidad neta, porque no descuenta impuestos |

**Escala de niveles:** 0 Degenerativo · 1 Mitigado · 2 Neutro · 3 Restaurativo · 4 Regenerativo.

---

## 6. Administración (solo personas con permiso)

### Crear un usuario
**Administración → Usuarios → Nuevo usuario.** Complete el nombre, el correo y una contraseña
inicial, y marque los **roles** que necesita esa persona. Entréguele la contraseña por un medio
seguro.

### Desactivar un usuario
En **Usuarios**, pulse **Desactivar** y confirme. La persona ya no podrá ingresar, pero su
historial se conserva. Puede reactivarla cuando quiera.

### Roles y permisos
**Administración → Roles y permisos.** Cree un rol (por ejemplo «Consulta» o «Analista») y marque
en la tabla lo que puede hacer en cada módulo: consultar, crear, editar o eliminar. Conceda solo
lo necesario.

### Configuración
Aquí se definen el nombre de la institución, la moneda, los impuestos de referencia, el umbral de
alerta y la cantidad de filas por página. Cada cambio queda registrado.

### Auditoría
Muestra quién hizo qué y cuándo: inicios de sesión, cambios de usuarios, permisos, configuración
y exportaciones. Use los filtros por operación, usuario o fecha.

> El sistema **no permite** quedarse sin administrador: no podrá desactivar su propia cuenta ni
> la del último administrador activo.

---

## 7. Respaldo de la información

Todos los datos están en un solo archivo:

```
C:\Users\59398\proyectos_tecnologicos\rentabilidad-regenerativa\db.sqlite3
```

**Cópielo a una memoria USB o a la nube con regularidad**, sobre todo antes de cargar o cambiar
datos importantes. Para restaurar, apague el sistema y reemplace ese archivo por la copia.

---

## 8. Sobre los datos cargados

- **120 emprendimientos ecuatorianos reales**, tomados de fuentes públicas: el directorio de
  Empresas B (B Lab) y el ranking de la Superintendencia de Compañías (SCVS). Cada uno tiene su
  enlace de verificación.
- Los datos económicos proceden de los estados financieros publicados por la SCVS.
- Los datos **sociales y ambientales no son públicos**, por eso esos casos aparecen como
  «Evaluación incompleta». Para que un emprendimiento pueda calificar, esas mediciones deben
  levantarse en campo y cargarse en el sistema.
- Raíz Andina, Textiles Sisa y Ecoservicios del Austro son **casos de demostración**, no empresas
  reales.

---

## 9. Si algo no funciona

| Lo que ve | Qué hacer |
|---|---|
| «No se puede acceder a este sitio» | El sistema está apagado: repita el paso 1 |
| «That port is already in use» | Ya hay una copia encendida: use esa ventana del navegador |
| «Usuario o contraseña incorrectos» | Revise mayúsculas y minúsculas. Si la olvidó, pida a quien administra el sistema que la restablezca |
| «Acceso denegado» (403) | Su usuario no tiene permiso para esa sección: solicítelo a quien administra el sistema |
| No aparece el menú Administración | Su cuenta no tiene rol de administración |
| «Sin datos suficientes» en una evaluación | Ese período no tiene mediciones: cárguelas en el Editor de datos |

**Soporte técnico:** ___________________ · Teléfono / correo: ___________________
