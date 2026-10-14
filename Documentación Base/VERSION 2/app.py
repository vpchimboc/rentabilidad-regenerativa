import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from sklearn.neural_network import MLPRegressor

# ---------------------------------------------------------
# CONFIGURACIÓN DE PÁGINA Y TÍTULO
# ---------------------------------------------------------
st.set_page_config(
    page_title="Framework FRR - Rentabilidad Regenerativa",
    page_icon="🌱",
    layout="wide"
)

st.title("🌱 Framework de Rentabilidad Regenerativa (FRR)")
st.markdown("""
**Evaluación de Emprendimientos de Triple Impacto más allá del Break-even**  
*Sistema Integrado: Datos Reales (D1 Financiera) + Simulación Monte Carlo (D2, D3, D4) + Red Neuronal Artificial (ANN)*
""")

# ---------------------------------------------------------
# 1. CARGA DE DATOS Y REFERENCIAS
# ---------------------------------------------------------
@st.cache_data
def cargar_datos():
    df_ref = pd.read_csv("FRR_matriz_referencias_ENTREGA_CONTROLADA_v1.csv", sep=";")
    df_emp = pd.read_csv("emprendimientos_ecuador.csv")
    return df_ref, df_emp

try:
    df_ref, df_emp = cargar_datos()
except Exception as e:
    st.error(f"Error al cargar archivos locales: {e}")
    st.stop()

# ---------------------------------------------------------
# 2. FUNCIONES DE NORMALIZACIÓN Y SIMULACIÓN
# ---------------------------------------------------------
def normalizar_kpi(valor, L, U, sentido):
    if pd.isna(valor) or pd.isna(L) or pd.isna(U) or U <= L:
        return np.nan
    if sentido == 'BEN':
        z = (valor - L) / (U - L)
    elif sentido == 'COS':
        z = (U - valor) / (U - L)
    else:  # OBJ
        z = (valor - L) / (U - L)
    return float(np.clip(z, 0.0, 1.0))

def generar_vector_simulado(empresa_row, df_ref, escenario='Esperado', seed=42):
    np.random.seed(seed)
    
    # Parámetros de distribución Beta para simulación según escenario
    if escenario == 'Pesimista':
        a, b = 2, 6  # Sesgado a valores bajos (~0.25)
    elif escenario == 'Esperado':
        a, b = 5, 5  # Centrado (~0.50)
    else: # Optimista
        a, b = 6, 2  # Sesgado a valores altos (~0.75)
        
    kpi_valores = []
    detalles = []
    
    for idx, kpi in df_ref.iterrows():
        cod = kpi['codigo']
        dim = kpi['dimension']
        sentido = kpi['sentido']
        
        # Verificar si existe el dato real en D1
        es_real = False
        val_z = np.nan
        
        if dim == 'D1' and cod in empresa_row and not pd.isna(empresa_row[cod]):
            val_bruto = float(empresa_row[cod])
            try:
                L_val = float(str(kpi['L']).replace(',', '.')) if not pd.isna(kpi['L']) else None
                U_val = float(str(kpi['U']).replace(',', '.')) if not pd.isna(kpi['U']) else None
            except:
                L_val, U_val = None, None
                
            z_calc = normalizar_kpi(val_bruto, L_val, U_val, sentido)
            if not pd.isna(z_calc):
                val_z = z_calc
                es_real = True
                origen = "Real (Plataforma SCVS)"
        
        # Si es D2, D3, D4 o faltó el dato en D1, se simula
        if pd.isna(val_z):
            val_z = float(np.random.beta(a, b))
            origen = f"Simulado ({escenario} - Monte Carlo)"
            
        kpi_valores.append(val_z)
        detalles.append({
            'Código': cod,
            'Dimensión': dim,
            'Indicador': kpi['indicador'],
            'Puntuación Normalizada (z_i)': round(val_z, 4),
            'Origen del Dato': origen
        })
        
    return np.array(kpi_valores), pd.DataFrame(detalles)

# ---------------------------------------------------------
# 3. ENTRENAMIENTO MODO CACHÉ DE LA RED NEURONAL (ANN)
# ---------------------------------------------------------
@st.cache_resource
def entrenar_modelo_ann():
    np.random.seed(42)
    # Sintetizar base de entrenamiento multivariable (200 muestras x 42 KPI)
    X_train = np.random.uniform(0, 1, size=(300, 42))
    # Definir pesos por dimensión D1=0.25, D2=0.25, D3=0.25, D4=0.25
    y_train = np.mean(X_train, axis=1) * 100.0  # Target IRR %
    
    ann = MLPRegressor(
        hidden_layer_sizes=(32, 16),
        activation='relu',
        max_iter=500,
        random_state=42
    )
    ann.fit(X_train, y_train)
    return ann

ann_model = entrenar_modelo_ann()

# ---------------------------------------------------------
# 4. BARRA LATERAL (PANEL DE CONTROL)
# ---------------------------------------------------------
st.sidebar.header("⚙️ Configuración del Análisis")

# Selector de Empresa Real
nombres_empresas = df_emp['nombre'].tolist()
empresa_sel = st.sidebar.selectbox("Seleccione la Empresa (Base Real n=92):", nombres_empresas)
empresa_row = df_emp[df_emp['nombre'] == empresa_sel].iloc[0]

# Informacion basica en sidebar
st.sidebar.subheader("Información de la Empresa")
st.sidebar.text(f"RUC: {empresa_row['ruc']}")
st.sidebar.text(f"Sector: {empresa_row['sector']}")
st.sidebar.text(f"Empleados: {empresa_row['empleados']}")
st.sidebar.text(f"Ventas: ${empresa_row['ventas']:,.2f}")

# Selector de Escenario Operativo
escenario_sel = st.sidebar.radio(
    "Seleccione el Escenario a Simular (D2, D3, D4):",
    ['Pesimista', 'Esperado', 'Optimista'],
    index=1
)

# ---------------------------------------------------------
# 5. GENERACIÓN Y CÁLCULOS
# ---------------------------------------------------------
vec_actual, df_detalles = generar_vector_simulado(empresa_row, df_ref, escenario_sel)

# Ponderación por Dimensión para Gráfico de Radar
df_detalles['Dim_Nombre'] = df_detalles['Dimensión'].map({
    'D1': 'D1. Financiera',
    'D2': 'D2. Ambiental',
    'D3': 'D3. Social',
    'D4': 'D4. Operacional'
})
promedios_dim = df_detalles.groupby('Dim_Nombre')['Puntuación Normalizada (z_i)'].mean() * 100

# Predicción con la ANN
irr_predicho = ann_model.predict([vec_actual])[0]

# Generar vectores para los 3 escenarios (para comparación en Radar)
vec_pes, _ = generar_vector_simulado(empresa_row, df_ref, 'Pesimista')
vec_esp, _ = generar_vector_simulado(empresa_row, df_ref, 'Esperado')
vec_opt, _ = generar_vector_simulado(empresa_row, df_ref, 'Optimista')

prom_pes = pd.DataFrame({'Dim': df_detalles['Dim_Nombre'], 'Val': vec_pes}).groupby('Dim').mean() * 100
prom_esp = pd.DataFrame({'Dim': df_detalles['Dim_Nombre'], 'Val': vec_esp}).groupby('Dim').mean() * 100
prom_opt = pd.DataFrame({'Dim': df_detalles['Dim_Nombre'], 'Val': vec_opt}).groupby('Dim').mean() * 100

# ---------------------------------------------------------
# 6. DASHBOARD PRINCIPAL DE RESULTADOS
# ---------------------------------------------------------
col1, col2, col3 = st.columns([1, 1, 1])

with col1:
    st.metric(
        label="Índice Rentabilidad Regenerativa (IRR)",
        value=f"{irr_predicho:.2f}%",
        delta=f"Escenario: {escenario_sel}"
    )

with col2:
    estado = "REGENERATIVO ALTO" if irr_predicho > 70 else ("SUSTENTABLE MODERADO" if irr_predicho > 45 else "RIESGO TRADICIONAL")
    st.metric(label="Diagnóstico de Impacto", value=estado)

with col3:
    cobertura_real = (df_detalles['Origen del Dato'].str.contains('Real').sum() / 42) * 100
    st.metric(label="Cobertura de Datos Reales", value=f"{cobertura_real:.1f}%", delta="Base SCVS 2025")

st.divider()

# Layout en dos columnas: Radar + Resumen por Dimensiones
c_left, c_right = st.columns([1.2, 1])

with c_left:
    st.subheader("🕸️ Perfil Multidimensional (Gráfico Radar Comparativo)")
    
    categories = ['D1. Financiera', 'D2. Ambiental', 'D3. Social', 'D4. Operacional']
    
    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=[prom_pes.loc[c, 'Val'] for c in categories],
        theta=categories,
        fill='toself',
        name='Pesimista',
        line_color='red',
        opacity=0.3
    ))
    fig.add_trace(go.Scatterpolar(
        r=[prom_esp.loc[c, 'Val'] for c in categories],
        theta=categories,
        fill='toself',
        name='Esperado',
        line_color='blue',
        opacity=0.4
    ))
    fig.add_trace(go.Scatterpolar(
        r=[prom_opt.loc[c, 'Val'] for c in categories],
        theta=categories,
        fill='toself',
        name='Optimista',
        line_color='green',
        opacity=0.3
    ))
    
    fig.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
        showlegend=True,
        height=400,
        margin=dict(l=20, r=20, t=30, b=20)
    )
    st.plotly_chart(fig, use_container_width=True)

with c_right:
    st.subheader("📊 Desempeño por Dimensión (Escenario Activo)")
    for dim, val in promedios_dim.items():
        st.write(f"**{dim}**")
        st.progress(int(val))
        st.caption(f"Puntuación: {val:.2f} / 100")

# ---------------------------------------------------------
# 7. TABLA DE TRAZABILIDAD DE LOS 42 KPIS
# ---------------------------------------------------------
st.divider()
st.subheader("📋 Trazabilidad Detallada de los 42 KPI del Framework")

st.dataframe(
    df_detalles[['Código', 'Dimensión', 'Indicador', 'Puntuación Normalizada (z_i)', 'Origen del Dato']],
    use_container_width=True,
    height=350
)

# Pie de página
st.caption("Framework FRR v1.0 | Protocolo de Investigación - Universidad Católica de Cuenca | Desarrollo de Plataforma 2026")