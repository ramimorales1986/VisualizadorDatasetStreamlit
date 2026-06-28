import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(
    page_title="Visualizador Universal",
    page_icon="📈",
    layout="wide",
)

st.markdown(
    """
    <style>
    .main-title {font-size: 2.35rem; font-weight: 800; margin-bottom: 0.2rem;}
    .subtitle {color: #5f6368; font-size: 1.05rem; margin-bottom: 1rem;}
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="main-title">Visualizador Universal de Datasets</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="subtitle">Construye gráficos interactivos para cualquier dataset y aplica filtros sin programar desde la interfaz.</div>',
    unsafe_allow_html=True,
)

@st.cache_data(show_spinner=False)
def load_demo():
    return pd.read_csv("data/dataset_demo.csv", parse_dates=["fecha"])

@st.cache_data(show_spinner=False)
def load_file(uploaded_file, separator, decimal):
    name = uploaded_file.name.lower()
    if name.endswith(".csv"):
        if separator == "Automático":
            try:
                return pd.read_csv(uploaded_file, sep=None, engine="python", decimal=decimal)
            except Exception:
                uploaded_file.seek(0)
                return pd.read_csv(uploaded_file, decimal=decimal)
        return pd.read_csv(uploaded_file, sep=separator, decimal=decimal)
    if name.endswith((".xlsx", ".xls")):
        return pd.read_excel(uploaded_file)
    raise ValueError("Formato no soportado.")

def detect_dates(df):
    result = df.copy()
    for col in result.columns:
        if result[col].dtype == "object":
            converted = pd.to_datetime(result[col], errors="coerce", dayfirst=True)
            if converted.notna().mean() >= 0.75:
                result[col] = converted
    return result

def apply_filters(df, categorical_cols, numeric_cols):
    filtered = df.copy()
    st.sidebar.header("Filtros")

    for col in categorical_cols[:8]:
        values = sorted([str(v) for v in filtered[col].dropna().unique()])
        if 1 < len(values) <= 80:
            selected = st.sidebar.multiselect(f"{col}", values, default=values)
            filtered = filtered[filtered[col].astype(str).isin(selected)]

    for col in numeric_cols[:8]:
        series = filtered[col].dropna()
        if not series.empty:
            min_val = float(series.min())
            max_val = float(series.max())
            if min_val < max_val:
                selected_range = st.sidebar.slider(
                    f"Rango {col}",
                    min_value=min_val,
                    max_value=max_val,
                    value=(min_val, max_val),
                )
                filtered = filtered[filtered[col].between(selected_range[0], selected_range[1])]

    return filtered

with st.sidebar:
    st.header("Dataset")
    uploaded = st.file_uploader("Sube un archivo", type=["csv", "xlsx", "xls"])
    usar_demo = st.checkbox("Usar dataset demo", value=uploaded is None)
    separator = st.selectbox("Separador CSV", ["Automático", ",", ";", "|", "\\t"])
    decimal = st.selectbox("Decimal", [".", ","], index=0)
    parse_dates = st.checkbox("Detectar fechas", value=True)

try:
    if uploaded is not None:
        df = load_file(uploaded, separator=separator, decimal=decimal)
    elif usar_demo:
        df = load_demo()
    else:
        st.warning("Carga un archivo o activa el dataset demo.")
        st.stop()
except Exception as e:
    st.error(f"No se pudo cargar el dataset: {e}")
    st.stop()

if parse_dates:
    df = detect_dates(df)

numeric_cols = df.select_dtypes(include=np.number).columns.tolist()
categorical_cols = df.select_dtypes(include=["object", "category", "bool"]).columns.tolist()
date_cols = df.select_dtypes(include=["datetime64[ns]", "datetimetz"]).columns.tolist()
all_cols = df.columns.tolist()

filtered = apply_filters(df, categorical_cols, numeric_cols)

c1, c2, c3 = st.columns(3)
c1.metric("Filas originales", f"{len(df):,}")
c2.metric("Filas filtradas", f"{len(filtered):,}")
c3.metric("Columnas", f"{df.shape[1]:,}")

with st.expander("Vista previa del dataset filtrado", expanded=False):
    st.dataframe(filtered.head(200), use_container_width=True)

st.markdown("## Constructor de gráficos")

chart_type = st.selectbox(
    "Selecciona el tipo de visualización",
    [
        "Barras agregadas",
        "Línea temporal",
        "Dispersión",
        "Histograma",
        "Boxplot",
        "Pastel",
        "Matriz de correlación",
    ],
)

if filtered.empty:
    st.warning("No hay datos después de aplicar los filtros.")
    st.stop()

if chart_type == "Barras agregadas":
    if not all_cols:
        st.stop()
    x = st.selectbox("Categoría / Eje X", all_cols)
    metric_options = ["Conteo"] + numeric_cols
    y = st.selectbox("Métrica", metric_options)
    agg = st.selectbox("Agregación", ["sum", "mean", "median", "min", "max"], disabled=(y == "Conteo"))

    if y == "Conteo":
        plot_df = filtered[x].astype(str).value_counts().head(30).reset_index()
        plot_df.columns = [x, "conteo"]
        fig = px.bar(plot_df, x=x, y="conteo", title=f"Conteo por {x}")
    else:
        plot_df = getattr(filtered.groupby(x, dropna=False)[y], agg)().reset_index()
        plot_df = plot_df.sort_values(y, ascending=False).head(30)
        fig = px.bar(plot_df, x=x, y=y, title=f"{agg} de {y} por {x}")

    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(plot_df, use_container_width=True)

elif chart_type == "Línea temporal":
    if date_cols and numeric_cols:
        x = st.selectbox("Fecha", date_cols)
        y = st.selectbox("Métrica numérica", numeric_cols)
        freq = st.selectbox("Frecuencia", ["Día", "Mes", "Trimestre", "Año"])
        freq_map = {"Día": "D", "Mes": "M", "Trimestre": "Q", "Año": "Y"}
        temp = filtered[[x, y]].dropna().copy()
        temp = temp.set_index(x).resample(freq_map[freq])[y].sum().reset_index()
        fig = px.line(temp, x=x, y=y, markers=True, title=f"Evolución de {y} por {freq.lower()}")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(temp, use_container_width=True)
    else:
        st.info("Se requiere una columna de fecha y una columna numérica.")

elif chart_type == "Dispersión":
    if len(numeric_cols) >= 2:
        x = st.selectbox("Eje X", numeric_cols)
        y = st.selectbox("Eje Y", numeric_cols, index=1)
        color = st.selectbox("Color", ["Ninguno"] + categorical_cols + date_cols)
        size = st.selectbox("Tamaño", ["Ninguno"] + numeric_cols)
        fig = px.scatter(
            filtered,
            x=x,
            y=y,
            color=None if color == "Ninguno" else color,
            size=None if size == "Ninguno" else size,
            title=f"{y} vs {x}",
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Se requieren dos columnas numéricas.")

elif chart_type == "Histograma":
    if numeric_cols:
        x = st.selectbox("Variable", numeric_cols)
        color = st.selectbox("Segmentar por", ["Ninguno"] + categorical_cols)
        bins = st.slider("Número de intervalos", 5, 80, 30)
        fig = px.histogram(
            filtered,
            x=x,
            color=None if color == "Ninguno" else color,
            nbins=bins,
            title=f"Distribución de {x}",
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Se requiere una columna numérica.")

elif chart_type == "Boxplot":
    if numeric_cols:
        y = st.selectbox("Variable numérica", numeric_cols)
        x = st.selectbox("Agrupar por", ["Ninguno"] + categorical_cols)
        fig = px.box(
            filtered,
            x=None if x == "Ninguno" else x,
            y=y,
            points="outliers",
            title=f"Distribución de {y}",
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Se requiere una columna numérica.")

elif chart_type == "Pastel":
    if categorical_cols:
        names = st.selectbox("Categoría", categorical_cols)
        values = st.selectbox("Valores", ["Conteo"] + numeric_cols)
        if values == "Conteo":
            plot_df = filtered[names].astype(str).value_counts().head(10).reset_index()
            plot_df.columns = [names, "conteo"]
            fig = px.pie(plot_df, names=names, values="conteo", title=f"Participación por {names}")
        else:
            plot_df = filtered.groupby(names, dropna=False)[values].sum().reset_index().sort_values(values, ascending=False).head(10)
            fig = px.pie(plot_df, names=names, values=values, title=f"Participación de {values} por {names}")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(plot_df, use_container_width=True)
    else:
        st.info("Se requiere una columna categórica.")

elif chart_type == "Matriz de correlación":
    if len(numeric_cols) >= 2:
        selected = st.multiselect("Variables", numeric_cols, default=numeric_cols[:6])
        if len(selected) >= 2:
            corr = filtered[selected].corr(numeric_only=True)
            fig = px.imshow(corr, text_auto=True, title="Matriz de correlación")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Selecciona al menos dos variables.")
    else:
        st.info("Se requieren al menos dos columnas numéricas.")

st.markdown("## Descarga")
st.download_button(
    "Descargar dataset filtrado",
    data=filtered.to_csv(index=False).encode("utf-8"),
    file_name="dataset_filtrado.csv",
    mime="text/csv",
)
