
import os
from pathlib import Path
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Costing Flow Dashboard", page_icon="📊", layout="wide")

DEFAULT_OUTPUT_PATH = "/content/drive/MyDrive/colab_costing_flow/output"

st.sidebar.title("⚙️ Configurazione")
output_path = st.sidebar.text_input("Cartella output del flow", value=DEFAULT_OUTPUT_PATH)
output_dir = Path(output_path)

product_file = output_dir / "costing_product_level_summary.xlsx"
scores_file = output_dir / "method_scores.xlsx"
run_log_file = output_dir / "run_log.xlsx"
memo_file = output_dir / "memo_costing_corrected_no_duplicates.docx"

@st.cache_data
def load_excel(path):
    return pd.read_excel(path)

st.title("📊 Costing Flow Dashboard")
st.caption("Dashboard Streamlit collegata agli output del flow Colab.")

if not output_dir.exists():
    st.error(f"Cartella non trovata: {output_dir}")
    st.stop()

missing = [p.name for p in [product_file, scores_file] if not p.exists()]
if missing:
    st.error("File mancanti: " + ", ".join(missing))
    st.info("Esegui prima il flow Colab completo.")
    st.stop()

df = load_excel(product_file)
scores = load_excel(scores_file)
run_log = load_excel(run_log_file) if run_log_file.exists() else None

id_candidates = ["product_id", "record_id", "id"]
id_col = next((c for c in id_candidates if c in df.columns), df.columns[0])

risk_col = "risk_prob" if "risk_prob" in df.columns else None
anom_col = "anomaly_score_raw" if "anomaly_score_raw" in df.columns else None
range_col = "alloc_range" if "alloc_range" in df.columns else None
sat_col = "sat_abs_delta" if "sat_abs_delta" in df.columns else None
alloc_cols = [c for c in ["alloc_M1", "alloc_M2", "alloc_M3", "alloc_M3_AUTO", "alloc_SAT"] if c in df.columns]

st.sidebar.title("🔎 Filtri")
products = sorted(df[id_col].astype(str).unique().tolist())
selected_products = st.sidebar.multiselect("Prodotti", products, default=products)
df_view = df[df[id_col].astype(str).isin(selected_products)].copy()

if df_view.empty:
    st.warning("Nessun prodotto selezionato.")
    st.stop()

st.subheader("Executive Summary")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Prodotti analizzati", len(df_view))
c2.metric("Rischio medio", f"{df_view[risk_col].mean():.3f}" if risk_col else "n.d.")
c3.metric("Anomaly medio", f"{df_view[anom_col].mean():.3f}" if anom_col else "n.d.")
c4.metric("Sensibilità media", f"{df_view[range_col].mean():.2f}" if range_col else "n.d.")

st.subheader("🏆 Ranking metodi del Decision Engine")
if {"method", "decision_score"}.issubset(scores.columns):
    scores_sorted = scores.sort_values("decision_score", ascending=False)
    st.metric("Metodo consigliato", scores_sorted.iloc[0]["method"])
    fig = px.bar(scores_sorted, x="method", y="decision_score", text_auto=".3f",
                 title="Decision score per metodo")
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(scores_sorted, use_container_width=True)
else:
    st.warning("method_scores.xlsx non contiene method/decision_score.")

st.subheader("⚠️ Rischio e anomalie")
tab1, tab2 = st.tabs(["Top prodotti critici", "Distribuzioni"])

with tab1:
    sort_col = risk_col or anom_col or range_col
    if sort_col:
        top = df_view.sort_values(sort_col, ascending=False).head(10)
        show_cols = [id_col] + [c for c in [risk_col, anom_col, range_col, sat_col] if c]
        st.dataframe(top[show_cols], use_container_width=True)

with tab2:
    cc1, cc2 = st.columns(2)
    with cc1:
        if risk_col:
            st.plotly_chart(px.histogram(df_view, x=risk_col, nbins=20, title="Distribuzione rischio"),
                            use_container_width=True)
    with cc2:
        if anom_col:
            st.plotly_chart(px.histogram(df_view, x=anom_col, nbins=20, title="Distribuzione anomaly score"),
                            use_container_width=True)

st.subheader("📌 Analisi allocazioni")
tab1, tab2, tab3 = st.tabs(["Confronto metodi", "Sensibilità", "SAT"])

with tab1:
    if alloc_cols:
        df_long = df_view.melt(id_vars=id_col, value_vars=alloc_cols,
                               var_name="Metodo", value_name="Allocazione")
        fig = px.bar(df_long, x=id_col, y="Allocazione", color="Metodo",
                     barmode="group", title="Confronto allocazioni per prodotto")
        st.plotly_chart(fig, use_container_width=True)

with tab2:
    if range_col:
        fig = px.bar(df_view.sort_values(range_col, ascending=False), x=id_col, y=range_col,
                     text_auto=".2f", title="Sensibilità allocazione per prodotto")
        st.plotly_chart(fig, use_container_width=True)

with tab3:
    if sat_col and df_view[sat_col].sum() > 0:
        fig = px.bar(df_view.sort_values(sat_col, ascending=False), x=id_col, y=sat_col,
                     text_auto=".2f", title="Impatto SAT per prodotto")
        st.plotly_chart(fig, use_container_width=True)
    elif sat_col:
        st.info("Il layer SAT non ha generato rettifiche significative.")

if any(c in df_view.columns for c in ["topology_coherence_score", "structural_anomaly_score"]):
    st.subheader("🕸️ Topology Intelligence")
    tc1, tc2 = st.columns(2)
    if "topology_coherence_score" in df_view.columns:
        with tc1:
            fig = px.bar(df_view.sort_values("topology_coherence_score"), x=id_col,
                         y="topology_coherence_score", title="Topology coherence score")
            st.plotly_chart(fig, use_container_width=True)
    if "structural_anomaly_score" in df_view.columns:
        with tc2:
            fig = px.bar(df_view.sort_values("structural_anomaly_score", ascending=False), x=id_col,
                         y="structural_anomaly_score", title="Structural anomaly score")
            st.plotly_chart(fig, use_container_width=True)

if run_log is not None:
    st.subheader("📜 Run log")
    st.dataframe(run_log, use_container_width=True)

st.subheader("📥 Download output")
d1, d2, d3, d4 = st.columns(4)

with d1:
    with open(product_file, "rb") as f:
        st.download_button("Summary prodotto", data=f, file_name="costing_product_level_summary.xlsx")

with d2:
    with open(scores_file, "rb") as f:
        st.download_button("Method scores", data=f, file_name="method_scores.xlsx")

with d3:
    if run_log_file.exists():
        with open(run_log_file, "rb") as f:
            st.download_button("Run log", data=f, file_name="run_log.xlsx")

with d4:
    if memo_file.exists():
        with open(memo_file, "rb") as f:
            st.download_button("Memo Word", data=f, file_name="memo_costing_corrected_no_duplicates.docx")

with st.expander("📄 Dataset prodotto"):
    st.dataframe(df_view, use_container_width=True)
