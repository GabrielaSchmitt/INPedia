import json
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import time
from inpi_engine import INPIEngine
from inpi_entrada import preparar_entradas, resumo_entradas
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

# ─── Status (semáforo) ───
# Ícone + nome da categoria, para a coluna se explicar sozinha (dispensa legenda)
STATUS_ANDAMENTO = "✅ Em andamento"
STATUS_VIGOR = "®️ Registro em vigor"
STATUS_ENCERRADO = "❌ Encerrado"
STATUS_ATENCAO = "🟡 Atenção"
STATUS_OUTROS = "⚪ Outros"
STATUS_ERRO = "⚠️ Erro"
STATUS_REPETIDO = "🔁 Repetido"

AJUDA_STATUS = (
    "✅ Em andamento: aguardando exame ou deferido · ®️ Registro em vigor · "
    "❌ Encerrado: indeferido, extinto, arquivado ou nulidade · 🟡 Atenção: oposição ou sobrestado · "
    "⚪ Outros · ⚠️ Erro: de preenchimento ou na consulta (veja a coluna observacao) · "
    "🔁 Repetido: consultado na primeira ocorrência"
)


def get_status_indicator(situacao):
    """Classifica a situação do processo (regras em ordem de prioridade)."""
    if not situacao or not isinstance(situacao, str):
        return STATUS_OUTROS
    sit_lower = situacao.lower()
    if "indeferid" in sit_lower:
        return STATUS_ENCERRADO
    elif "em vigor" in sit_lower:
        return STATUS_VIGOR
    elif "aguardando" in sit_lower:
        return STATUS_ANDAMENTO
    elif "extint" in sit_lower or "arquivad" in sit_lower or "nulidade" in sit_lower:
        return STATUS_ENCERRADO
    elif "deferido" in sit_lower and "indeferid" not in sit_lower:
        return STATUS_ANDAMENTO
    elif "oposição" in sit_lower or "sobrestado" in sit_lower:
        return STATUS_ATENCAO
    else:
        return STATUS_OUTROS


def botao_copiar(texto):
    """Botão que copia o texto para a área de transferência, no mesmo estilo dos botões de download."""
    texto_js = json.dumps(texto).replace("</", "<\\/")
    components.html(f"""
    <style>
      body {{ margin: 0; font-family: 'Inter', 'Source Sans Pro', sans-serif; }}
      button {{ width: 100%; height: 40px; background: white; color: #0F4C81; border: 2px solid #0F4C81;
               border-radius: 10px; font-weight: 600; font-size: 0.95rem; cursor: pointer; transition: all .2s; }}
      button:hover {{ background: #0F4C81; color: white; }}
    </style>
    <button id="copiar">📋 Copiar tabela</button>
    <script>
      const texto = {texto_js};
      const botao = document.getElementById("copiar");
      function avisar(msg) {{ botao.textContent = msg; setTimeout(() => botao.textContent = "📋 Copiar tabela", 2000); }}
      function alternativo() {{
        const area = document.createElement("textarea");
        area.value = texto; document.body.appendChild(area); area.select();
        const ok = document.execCommand("copy"); area.remove();
        avisar(ok ? "✅ Copiado!" : "❌ Não foi possível copiar");
      }}
      botao.addEventListener("click", () => {{
        if (navigator.clipboard && window.isSecureContext) {{
          navigator.clipboard.writeText(texto).then(() => avisar("✅ Copiado!")).catch(alternativo);
        }} else {{ alternativo(); }}
      }});
    </script>
    """, height=44)

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

entradas = []   # pares (linha de origem, valor como foi digitado)

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
            # linha = número da linha no Excel (o cabeçalho ocupa a linha 1)
            entradas = [(idx + 2, val) for idx, val in df_input[column_name].dropna().items()]
        except Exception as e:
            st.error(f"❌ Erro ao ler o arquivo Excel: {e}")

with tab2:
    st.markdown("")
    text_input = st.text_area(
        "Cole abaixo a lista de processos (um por linha):",
        height=200,
        placeholder="Cole aqui os números dos processos, um por linha:\n\n9876541**\n9876542**\n9876543**\n...",
        help="Você pode copiar diretamente de uma planilha Excel. Depois de colar, clique em CONSULTAR PROCESSOS.",
        key=f"text_area_{st.session_state.reset_counter}"
    )
    if text_input:
        entradas = [(i + 1, linha) for i, linha in enumerate(text_input.split("\n"))]

# ─── Verificação das entradas (tipagem e duplicados), antes de qualquer consulta ───
itens = preparar_entradas(entradas)
contagem = resumo_entradas(itens)
process_ids = [it["numero_processo"] for it in itens if it["consultar"]]
if itens:
    aviso = f"🔢 **{contagem['total']} entradas** · para consultar: **{contagem['consultar']}**"
    if contagem["repetidos"] or contagem["invalidos"]:
        aviso += (f" · repetidas: **{contagem['repetidos']}** · com erro de preenchimento: **{contagem['invalidos']}**. "
                  "Repetidas e com erro não são consultadas, mas ficam na planilha de saída, na mesma linha, com o motivo")
    st.info(aviso + ".")

# ─── Intervalo entre processos e estimativa de tempo ───
# Cada processo faz 2 requisições ao INPI (busca + página de detalhe) e o intervalo é aplicado entre processos.
# Mesmo com resposta instantânea, o ritmo fica em no máximo 2 × 60 / intervalo requisições por minuto.
# Com 1 s, o teto é 120/min: o Buscaweb bloqueia quem faz "mais de 120 consultas por minuto"
# (RPI nº 2728, 18/04/2023, Comunicados, "Bloqueio de usuários"). Por isso 1 s é o mínimo.
OPCOES_INTERVALO = [1.0, 1.5, 2.0, 3.0, 5.0]
REQUISICOES_POR_PROCESSO = 2
# Resposta média do INPI por processo, sem contar o intervalo, com o app rodando no computador (conexão direta).
# Medições de 17/10/2026: app local, 200 processos em 8:30 (≈1,56 s); medir_tempos.py, 800 processos (1,50 s).
# No app publicado (relay) a resposta foi mais rápida (≈0,74 s), então a estimativa fica do lado seguro;
# durante a consulta, o tempo restante usa a média real.
RESPOSTA_MEDIA_S = 1.6


AJUDA_INTERVALO = (
    f"Cada processo faz {REQUISICOES_POR_PROCESSO} consultas ao INPI. Com 1 s ou mais entre processos, o ritmo nunca "
    "passa de 120 consultas por minuto, o limite de bloqueio informado pelo INPI na RPI nº 2728. "
    f"O tempo estimado considera cerca de {str(RESPOSTA_MEDIA_S).replace('.', ',')} s de resposta por processo; "
    "em lotes grandes, a demora pode ser maior se o INPI ficar instável."
)


def fmt_num(v):
    return f"{v:g}".replace(".", ",")


def fmt_duracao(segundos):
    if segundos < 60:
        return f"{round(segundos)} s"
    minutos = round(segundos / 60)
    if minutos < 60:
        return f"≈ {minutos} min"
    return f"≈ {minutos // 60} h {minutos % 60:02d} min"


def texto_restante(feitos, total, decorrido):
    """Tempo restante pela média real dos processos já consultados (vale para conexão direta e relay)."""
    if feitos < 5:                      # com menos de 5 processos a média ainda oscila demais
        return " · calculando o tempo restante…"
    return f" · restam **{fmt_duracao(decorrido / feitos * (total - feitos))}**"


def mini_card(valor, rotulo):
    return f"""
        <div style="text-align: center; padding: 0.2rem 0;">
            <div style="font-size: 1.8rem; font-weight: 800; color: #0F4C81; white-space: nowrap;">{valor}</div>
            <div style="font-size: 0.7rem; color: #64748B; text-transform: uppercase; font-weight: 600;">{rotulo}</div>
        </div>
        """


# ─── Query Section ───
# Sempre visível: o texto colado só é registrado quando a caixa perde o foco,
# e clicar no botão já faz isso, então o usuário pode colar e consultar direto.
if not st.session_state.query_done:
    st.markdown("---")

    # Linha de configuração: seletor centralizado em cima, três cartões iguais embaixo
    with st.container(horizontal=True, horizontal_alignment="center"):
        delay = st.segmented_control(
            "Intervalo entre processos",
            OPCOES_INTERVALO, default=1.0, required=True,
            format_func=lambda v: f"**{fmt_num(v)} s**",
            help=AJUDA_INTERVALO,
        ) or OPCOES_INTERVALO[0]
    n_proc = len(process_ids)
    estimativa = n_proc * RESPOSTA_MEDIA_S + max(n_proc - 1, 0) * delay
    card_proc, card_int, card_tempo = st.columns(3, border=True, vertical_alignment="center")
    with card_proc:
        st.markdown(mini_card(n_proc, "processos"), unsafe_allow_html=True)
    with card_int:
        st.markdown(mini_card(f"{fmt_num(delay)} s", "intervalo"), unsafe_allow_html=True)
    with card_tempo:
        st.markdown(mini_card(fmt_duracao(estimativa) if n_proc else "—", "tempo estimado"), unsafe_allow_html=True)

    st.markdown("")

    consultar = st.button("CONSULTAR PROCESSOS", use_container_width=True, type="primary")
    if consultar and not itens:
        st.warning("📋 Cole a lista de processos ou envie uma planilha antes de consultar.")
    elif consultar:
        # Progress section
        progress_bar = st.progress(0)
        status_text = st.empty()

        engine = INPIEngine()
        conectado = True
        if process_ids:   # se nenhuma entrada for válida, não há o que consultar no INPI
            status_text.info("🔄 Conectando ao INPI...")
            conectado = engine.initialize_session()
        if conectado:
            if engine.modo == "relay":
                st.caption("🌎 Conectado via relay em São Paulo: o INPI recusa conexões de servidores fora do Brasil.")
            total = len(process_ids)
            feitos = 0
            inicio_lote = time.monotonic()
            results, tipos = [], []
            # Todas as entradas saem na planilha, na ordem original; só as válidas e inéditas são consultadas
            for it in itens:
                linha = {"linha": it["linha"], "entrada": it["entrada"],
                         "numero_processo": it["numero_processo"], "observacao": it["observacao"]}
                tipo = it["tipo"]
                if it["consultar"]:
                    if feitos:
                        time.sleep(delay)
                    status_text.info(f"🔍 Consultando **{feitos + 1}/{total}**: Processo `{it['numero_processo']}`"
                                     + texto_restante(feitos, total, time.monotonic() - inicio_lote))
                    detail = engine.get_details(it["numero_processo"])
                    detail.pop("ID_Pesquisado", None)
                    detail.pop("numero_processo", None)   # mantém o número verificado na entrada
                    linha["observacao"] = detail.pop("Erro", "")
                    if linha["observacao"]:
                        tipo = "erro_consulta"
                    linha.update(detail)
                    feitos += 1
                    progress_bar.progress(feitos / total)
                results.append(linha)
                tipos.append(tipo)

            progress_bar.progress(1.0)
            n_erro_consulta = tipos.count("erro_consulta")
            n_repetidos, n_invalidos = tipos.count("repetido"), tipos.count("invalido")
            frase = f"consultados com sucesso: **{feitos - n_erro_consulta}**"
            if n_erro_consulta:
                frase += f" · com erro na consulta: **{n_erro_consulta}**"
            if n_repetidos or n_invalidos:
                frase += (f" · não consultadas (repetidas: **{n_repetidos}**, "
                          f"com erro de preenchimento: **{n_invalidos}**)")
            if n_erro_consulta or n_repetidos or n_invalidos:
                status_text.warning(f"⚠️ Consulta finalizada: {frase}. O motivo de cada caso está na coluna **observacao**.")
                erros_consulta = [r["observacao"] for r, t in zip(results, tipos) if t == "erro_consulta"]
                if erros_consulta:
                    resumo = pd.Series(erros_consulta).value_counts()
                    st.markdown("\n".join(f"- **{n}×** {msg}" for msg, n in resumo.items()))
            else:
                status_text.success(f"✅ Consulta finalizada com sucesso! **{feitos}** processos consultados.")

            df_final = pd.DataFrame(results)

            # ─── Coluna de status (semáforo), com marcação própria para erros e repetidos ───
            situacoes = df_final["situacao"] if "situacao" in df_final.columns else pd.Series([None] * len(df_final))
            status = [
                STATUS_REPETIDO if t == "repetido" else STATUS_ERRO if t in ("invalido", "erro_consulta")
                else get_status_indicator(s)
                for t, s in zip(tipos, situacoes)
            ]
            pos = df_final.columns.get_loc("situacao") + 1 if "situacao" in df_final.columns else 4
            df_final.insert(pos, "status", status)

            # Store in session state so downloads don't clear the page
            st.session_state.df_results = df_final
            st.session_state.query_done = True

        else:
            status_text.empty()
            st.error(f"❌ **Não foi possível conectar ao INPI.** {engine.last_error}")
            with st.expander("Diagnóstico da conexão", expanded=True):
                st.markdown("\n".join(f"{i}. {passo}" for i, passo in enumerate(engine.diagnostico, 1)))

# ─── Display Results (from session state, persists across reruns) ───
if st.session_state.query_done and st.session_state.df_results is not None:
    df_final = st.session_state.df_results

    # ─── Resultados: exportação, cópia e tabela no mesmo bloco ───
    st.markdown("---")
    st.markdown("""
    <div class="card">
        <div class="card-title">📋 Resultados</div>
        <div class="card-description">Visualize todos os dados retornados pelo INPI. Clique nas colunas para ordenar.
        Baixe os dados no formato de sua preferência ou copie a tabela para colar direto em uma planilha ou e-mail.</div>
    </div>
    """, unsafe_allow_html=True)

    df_export = df_final
    col_exp1, col_exp2, col_exp3 = st.columns(3)

    with col_exp1:
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
        csv = df_export.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📄 Baixar CSV",
            data=csv,
            file_name="inpedia_resultados.csv",
            mime="text/csv",
            use_container_width=True
        )

    with col_exp3:
        # Copia a tabela como texto separado por tabulação: cola em colunas no Excel ou em um e-mail
        tsv = df_export.fillna("").to_csv(index=False, sep="\t")
        botao_copiar(tsv)

    # Resumo por status: só as categorias presentes (substitui a legenda)
    if "status" in df_final.columns:
        contagem_status = df_final["status"].value_counts()
        st.markdown(
            '<div class="legend-container">'
            + "".join(f'<div class="legend-item"><b>{n}</b>&nbsp;{rotulo}</div>' for rotulo, n in contagem_status.items())
            + "</div>",
            unsafe_allow_html=True,
        )

    st.dataframe(
        df_final,
        hide_index=True,   # a coluna "linha" já identifica cada entrada
        use_container_width=True,
        height=400,
        column_config={"status": st.column_config.TextColumn("status", help=AJUDA_STATUS)},
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
if not itens and not st.session_state.query_done:
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