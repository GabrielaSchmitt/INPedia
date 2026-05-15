import streamlit as st
import pandas as pd
import time
from inpi_engine import INPIEngine
import io

# ─── Page Config ───
st.set_page_config(
    page_title="INPédia – Consulta de Marcas INPI",
    page_icon="🔎",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─── Session State Init ───
if "df_results" not in st.session_state:
    st.session_state.df_results = None
if "query_done" not in st.session_state:
    st.session_state.query_done = False
if "reset_counter" not in st.session_state:
    st.session_state.reset_counter = 0

# ─── Status Semaphore Function ───
def get_status_indicator(situacao):
    """Returns a semaphore emoji based on the situação field."""
    if not situacao or not isinstance(situacao, str):
        return "⚪"
    sit_lower = situacao.lower()
    if "indeferid" in sit_lower:
        return "❌"
    elif "em vigor" in sit_lower:
        return "®️"
    elif "aguardando" in sit_lower:
        return "✅"
    elif "extint" in sit_lower or "arquivad" in sit_lower or "nulidade" in sit_lower:
        return "❌"
    elif "deferido" in sit_lower and "indeferid" not in sit_lower:
        return "✅"
    elif "oposição" in sit_lower or "sobrestado" in sit_lower:
        return "🟡"
    else:
        return "⚪"

# ─── Custom CSS ───
st.markdown("""
<style>
/* ── Google Fonts ── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

/* ── Root variables ── */
:root {
    --azul-petroleo: #0F4C81;
    --azul-claro: #4DA8DA;
    --branco: #FFFFFF;
    --cinza-suave: #F3F6F9;
    --cinza-borda: #E2E8F0;
    --texto-escuro: #1E293B;
    --texto-medio: #64748B;
    --sucesso: #10B981;
    --alerta: #F59E0B;
    --erro: #EF4444;
}

/* ── Global ── */
html, body, [class*="css"] {
    font-family: 'Inter', sans-serif !important;
}

.stApp {
    background-color: var(--cinza-suave) !important;
}

/* ── Hide default Streamlit elements ── */
#MainMenu {visibility: hidden;}
header {visibility: hidden;}
footer {visibility: hidden;}

/* ── Remove ALL top padding/white space ── */
.block-container {
    padding-top: 0 !important;
    margin-top: 0 !important;
    max-width: 100% !important;
}

div[data-testid="stAppViewBlockContainer"] {
    padding-top: 0 !important;
    margin-top: 0 !important;
}

section[data-testid="stMain"] {
    padding-top: 0 !important;
}

div[data-testid="stMainBlockContainer"] {
    padding-top: 0 !important;
    margin-top: 0 !important;
}

.stApp > div:first-child {
    padding-top: 0 !important;
}

/* Force remove any top spacing */
.main .block-container {
    padding-top: 0 !important;
    margin-top: -1rem !important;
}

/* ── Hero Header ── */
.hero-header {
    background: linear-gradient(135deg, #0F4C81 0%, #1a6bb5 50%, #4DA8DA 100%);
    padding: 2.5rem 2rem;
    border-radius: 0 0 24px 24px;
    margin: -1rem -1rem 2rem -1rem;
    text-align: center;
    box-shadow: 0 4px 20px rgba(15, 76, 129, 0.25);
    position: relative;
    overflow: hidden;
}

.hero-header::before {
    content: '';
    position: absolute;
    top: -50%;
    right: -20%;
    width: 400px;
    height: 400px;
    background: radial-gradient(circle, rgba(255,255,255,0.08) 0%, transparent 70%);
    border-radius: 50%;
}

.hero-header::after {
    content: '';
    position: absolute;
    bottom: -30%;
    left: -10%;
    width: 300px;
    height: 300px;
    background: radial-gradient(circle, rgba(255,255,255,0.05) 0%, transparent 70%);
    border-radius: 50%;
}

.hero-title {
    font-size: 2.8rem;
    font-weight: 800;
    color: white;
    margin: 0;
    letter-spacing: -0.5px;
    position: relative;
    z-index: 1;
}

.hero-subtitle {
    font-size: 1.1rem;
    color: rgba(255, 255, 255, 0.85);
    margin-top: 0.5rem;
    font-weight: 400;
    position: relative;
    z-index: 1;
}

.hero-badge {
    display: inline-block;
    background: rgba(255,255,255,0.15);
    backdrop-filter: blur(10px);
    border: 1px solid rgba(255,255,255,0.2);
    padding: 0.3rem 1rem;
    border-radius: 50px;
    color: white;
    font-size: 0.8rem;
    font-weight: 500;
    margin-top: 1rem;
    position: relative;
    z-index: 1;
}

/* ── Cards ── */
.card {
    background: white;
    border-radius: 16px;
    padding: 1.8rem;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04);
    border: 1px solid var(--cinza-borda);
    margin-bottom: 1rem;
    transition: box-shadow 0.2s ease;
}

.card:hover {
    box-shadow: 0 4px 12px rgba(0,0,0,0.08);
}

.card-title {
    font-size: 1.1rem;
    font-weight: 700;
    color: var(--azul-petroleo);
    margin-bottom: 0.3rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.card-description {
    font-size: 0.85rem;
    color: var(--texto-medio);
    margin-bottom: 1rem;
}

/* ── Stats Row ── */
.stats-container {
    display: flex;
    gap: 1rem;
    margin-bottom: 1.5rem;
    padding: 0 1rem;
}

.stat-card {
    flex: 1;
    background: white;
    border-radius: 12px;
    padding: 1.2rem 1.5rem;
    border: 1px solid var(--cinza-borda);
    text-align: center;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}

.stat-number {
    font-size: 2rem;
    font-weight: 800;
    color: var(--azul-petroleo);
    line-height: 1;
}

.stat-label {
    font-size: 0.75rem;
    color: var(--texto-medio);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-top: 0.3rem;
    font-weight: 600;
}

/* ── Tabs styling (outline like download buttons) ── */
.stTabs [data-baseweb="tab-list"] {
    gap: 0.5rem;
    background: transparent;
    border-radius: 0;
    padding: 0;
    border: none;
    justify-content: center;
}

.stTabs [data-baseweb="tab"] {
    border-radius: 10px !important;
    padding: 0.7rem 2rem !important;
    font-weight: 600 !important;
    font-size: 0.95rem !important;
    color: #0F4C81 !important;
    background: white !important;
    border: 2px solid #0F4C81 !important;
    transition: all 0.2s ease !important;
}

.stTabs [data-baseweb="tab"]:hover {
    background: #0F4C81 !important;
    color: white !important;
}

.stTabs [aria-selected="true"] {
    background: #0F4C81 !important;
    color: white !important;
    border: 2px solid #0F4C81 !important;
}

.stTabs [data-baseweb="tab-highlight"] {
    display: none !important;
}

.stTabs [data-baseweb="tab-border"] {
    display: none !important;
}

/* ── Buttons ── */
.stButton > button {
    background: linear-gradient(135deg, #0F4C81, #1a6bb5) !important;
    color: white !important;
    border: none !important;
    border-radius: 12px !important;
    padding: 0.7rem 2rem !important;
    font-weight: 600 !important;
    font-size: 1rem !important;
    letter-spacing: 0.3px;
    transition: all 0.3s ease !important;
    box-shadow: 0 2px 8px rgba(15, 76, 129, 0.3) !important;
}

.stButton > button:hover {
    background: linear-gradient(135deg, #0d3f6b, #155a9a) !important;
    box-shadow: 0 4px 16px rgba(15, 76, 129, 0.4) !important;
    transform: translateY(-1px);
}

.stButton > button:active {
    transform: translateY(0);
}

/* ── Download buttons ── */
.stDownloadButton > button {
    background: white !important;
    color: #0F4C81 !important;
    border: 2px solid #0F4C81 !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    transition: all 0.2s ease !important;
}

.stDownloadButton > button:hover {
    background: #0F4C81 !important;
    color: white !important;
}

/* ── Progress bar ── */
.stProgress > div > div > div > div {
    background: linear-gradient(90deg, #0F4C81, #4DA8DA) !important;
    border-radius: 10px;
}

.stProgress > div > div > div {
    background: var(--cinza-borda) !important;
    border-radius: 10px;
}

/* ── File uploader ── */
.stFileUploader > div {
    border-radius: 12px !important;
    border: 2px dashed var(--azul-claro) !important;
    background: rgba(77, 168, 218, 0.04) !important;
}

/* ── Text area ── */
.stTextArea textarea {
    border-radius: 12px !important;
    border: 1px solid var(--cinza-borda) !important;
    font-family: 'Inter', monospace !important;
    font-size: 0.9rem !important;
}

.stTextArea textarea:focus {
    border-color: var(--azul-claro) !important;
    box-shadow: 0 0 0 3px rgba(77, 168, 218, 0.15) !important;
}

/* ── Selectbox ── */
.stSelectbox > div > div {
    border-radius: 10px !important;
}

/* ── Slider ── */
.stSlider > div > div > div > div {
    background: var(--azul-petroleo) !important;
}

/* ── Dataframe ── */
.stDataFrame {
    border-radius: 12px;
    overflow: hidden;
    border: 1px solid var(--cinza-borda);
}

/* ── Alerts ── */
.stAlert {
    border-radius: 12px !important;
}

/* ── Divider ── */
hr {
    border-color: var(--cinza-borda) !important;
    margin: 1.5rem 0 !important;
}

/* ── Footer ── */
.footer {
    text-align: center;
    padding: 2rem 0 1rem 0;
    color: var(--texto-medio);
    font-size: 0.8rem;
    border-top: 1px solid var(--cinza-borda);
    margin-top: 3rem;
}

.footer a {
    color: var(--azul-petroleo);
    text-decoration: none;
    font-weight: 600;
}

/* ── Legend ── */
.legend-container {
    display: flex;
    gap: 1.5rem;
    justify-content: center;
    flex-wrap: wrap;
    margin: 0.5rem 0 1rem 0;
    font-size: 0.8rem;
    color: #64748B;
}

.legend-item {
    display: flex;
    align-items: center;
    gap: 0.3rem;
}

/* ── Responsive adjustments ── */
@media (max-width: 768px) {
    .hero-title { font-size: 2rem; }
    .stats-container { flex-direction: column; }
}
</style>
""", unsafe_allow_html=True)

# ─── Hero Header ───
st.markdown("""
<div class="hero-header">
    <div class="hero-title">🔎 INPédia</div>
    <div class="hero-subtitle">Consulta inteligente de marcas no INPI — rápida, organizada e em lote</div>
    <div class="hero-badge">⚡ Pesquisa Pública de Marcas • INPI Brasil</div>
</div>
""", unsafe_allow_html=True)

# ─── How it works section ───
st.markdown("""
<div class="stats-container">
    <div class="stat-card">
        <div class="stat-number">1️⃣</div>
        <div class="stat-label">Importe seus processos</div>
    </div>
    <div class="stat-card">
        <div class="stat-number">2️⃣</div>
        <div class="stat-label">Clique em consultar</div>
    </div>
    <div class="stat-card">
        <div class="stat-number">3️⃣</div>
        <div class="stat-label">Exporte os resultados</div>
    </div>
</div>
""", unsafe_allow_html=True)

# ─── Input Section ───
st.markdown("""
<div class="card">
    <div class="card-title">📥 Entrada de Dados</div>
    <div class="card-description">Escolha como deseja fornecer os números dos processos de marca para consulta.</div>
</div>
""", unsafe_allow_html=True)

tab1, tab2 = st.tabs(["📄 UPLOAD EXCEL", "📋 COLAR LISTA DE PROCESSOS"])

process_ids = []

with tab1:
    st.markdown("")
    uploaded_file = st.file_uploader(
        "Arraste ou selecione seu arquivo Excel (.xlsx)",
        type=["xlsx"],
        help="O arquivo deve conter uma coluna com os números dos processos de marca.",
        key=f"file_uploader_{st.session_state.reset_counter}"
    )
    if uploaded_file:
        try:
            df_input = pd.read_excel(uploaded_file)
            st.success(f"✅ Arquivo carregado com sucesso! **{len(df_input)} linhas** encontradas.")
            column_name = st.selectbox(
                "Selecione a coluna que contém os números dos processos:",
                df_input.columns,
                help="Escolha a coluna que contém os números de processo do INPI."
            )
            for val in df_input[column_name].dropna():
                clean_id = "".join(filter(str.isdigit, str(val)))
                if clean_id:
                    process_ids.append(clean_id)
            if process_ids:
                st.info(f"🔢 **{len(process_ids)} processos** identificados na coluna selecionada.")
        except Exception as e:
            st.error(f"❌ Erro ao ler o arquivo Excel: {e}")

with tab2:
    st.markdown("")
    text_input = st.text_area(
        "Cole abaixo a lista de processos (um por linha):",
        height=200,
        placeholder="Cole aqui os números dos processos, um por linha:\n\n932062393\n932062598\n932062717\n...",
        help="Você pode copiar diretamente de uma planilha Excel — cole os valores aqui.",
        key=f"text_area_{st.session_state.reset_counter}"
    )
    if text_input:
        lines = text_input.split("\n")
        for line in lines:
            clean_id = "".join(filter(str.isdigit, line.strip()))
            if clean_id:
                process_ids.append(clean_id)
        if process_ids:
            st.info(f"🔢 **{len(process_ids)} processos** identificados na lista.")

# ─── Query Section ───
if process_ids:
    st.markdown("---")

    # Compact config row
    col_cfg1, col_cfg2, col_cfg3 = st.columns([2, 1, 2])
    with col_cfg1:
        delay = st.slider(
            "Delay entre consultas (seg)",
            0.0, 5.0, 0.5, 0.1,
            help="Tempo de espera entre cada consulta ao INPI."
        )
    with col_cfg2:
        st.markdown(f"""
        <div style="text-align: center; padding-top: 0.5rem;">
            <div style="font-size: 1.8rem; font-weight: 800; color: #0F4C81;">{len(process_ids)}</div>
            <div style="font-size: 0.7rem; color: #64748B; text-transform: uppercase; font-weight: 600;">processos</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("")

    if st.button("CONSULTAR PROCESSOS", use_container_width=True, type="primary"):
        # Progress section
        progress_bar = st.progress(0)
        status_text = st.empty()

        results = []
        engine = INPIEngine()

        status_text.info("🔄 Inicializando sessão segura no INPI...")
        if engine.initialize_session():
            total = len(process_ids)
            for i, pid in enumerate(process_ids):
                status_text.info(f"🔍 Consultando **{i+1}/{total}**: Processo `{pid}`")
                detail = engine.get_details(pid)

                if "ID_Pesquisado" in detail:
                    del detail["ID_Pesquisado"]

                results.append(detail)
                progress_bar.progress((i + 1) / total)
                if i < total - 1:
                    time.sleep(delay)

            progress_bar.progress(1.0)
            status_text.success(f"✅ Consulta finalizada com sucesso! **{len(results)} processos** processados.")

            df_final = pd.DataFrame(results)

            # ─── Add semaphore status column ───
            if "situacao" in df_final.columns:
                df_final.insert(
                    df_final.columns.get_loc("situacao") + 1,
                    "status",
                    df_final["situacao"].apply(get_status_indicator)
                )

            # Store in session state so downloads don't clear the page
            st.session_state.df_results = df_final
            st.session_state.query_done = True

        else:
            st.error("❌ **Erro crítico:** Não foi possível conectar ao INPI. Tente novamente em alguns instantes.")

# ─── Display Results (from session state, persists across reruns) ───
if st.session_state.query_done and st.session_state.df_results is not None:
    df_final = st.session_state.df_results

    # ─── Export Section ───
    st.markdown("---")
    st.markdown("""
    <div class="card">
        <div class="card-title">📥 Exportar Resultados</div>
        <div class="card-description">Baixe os dados consultados no formato de sua preferência.</div>
    </div>
    """, unsafe_allow_html=True)

    col_exp1, col_exp2 = st.columns(2)

    with col_exp1:
        df_export = df_final.drop(columns=["status"], errors="ignore")
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_export.to_excel(writer, index=False, sheet_name='Resultados INPI')
        st.download_button(
            label="📊 Baixar Excel (.xlsx)",
            data=output.getvalue(),
            file_name="inpedia_resultados.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

    with col_exp2:
        df_export = df_final.drop(columns=["status"], errors="ignore")
        csv = df_export.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📄 Baixar CSV",
            data=csv,
            file_name="inpedia_resultados.csv",
            mime="text/csv",
            use_container_width=True
        )

    # ─── Results Table ───
    st.markdown("")
    st.markdown("""
    <div class="card">
        <div class="card-title">📋 Resultados da Consulta</div>
        <div class="card-description">Visualize todos os dados retornados pelo INPI. Clique nas colunas para ordenar.</div>
    </div>
    """, unsafe_allow_html=True)

    # Legend
    st.markdown("""
    <div class="legend-container">
        <div class="legend-item">✅ Aguardando exame / Deferido</div>
        <div class="legend-item">®️ Registro em vigor</div>
        <div class="legend-item">❌ Indeferido / Extinto</div>
        <div class="legend-item">🟡 Oposição / Sobrestado</div>
        <div class="legend-item">⚪ Outro</div>
    </div>
    """, unsafe_allow_html=True)

    st.dataframe(
        df_final,
        use_container_width=True,
        height=400,
    )

    # ─── New Query Button ───
    st.markdown("")
    st.markdown("")
    col_new1, col_new2, col_new3 = st.columns([1, 2, 1])
    with col_new2:
        if st.button("🔄 Realizar nova consulta", use_container_width=True):
            st.session_state.df_results = None
            st.session_state.query_done = False
            st.session_state.reset_counter += 1
            st.rerun()

# ─── Empty state ───
if not process_ids and not st.session_state.query_done:
    st.markdown("")
    st.markdown("""
    <div style="text-align: center; padding: 3rem 1rem; color: #64748B;">
        <div style="font-size: 3rem; margin-bottom: 1rem;">📭</div>
        <div style="font-size: 1.1rem; font-weight: 600; color: #1E293B;">Nenhum processo carregado</div>
        <div style="font-size: 0.9rem; margin-top: 0.5rem;">
            Faça upload de um arquivo Excel ou cole a lista de processos acima para começar.
        </div>
    </div>
    """, unsafe_allow_html=True)

# ─── Footer ───
st.markdown("""
<div class="footer">
    <strong>INPédia</strong> — Ferramenta de automação para consulta pública de marcas<br>
    Dados obtidos da <a href="https://busca.inpi.gov.br" target="_blank">Pesquisa Pública do INPI</a> • Brasil 🇧🇷
</div>
""", unsafe_allow_html=True)
