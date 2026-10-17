"""
Motor de consulta v2: conexão direta quando possível; relay em São Paulo quando o INPI
bloqueia o servidor (o INPI descarta conexões de IPs fora do Brasil).

Configuração do relay (variáveis de ambiente ou st.secrets):
    INPEDIA_RELAY_URL   ex.: https://<projeto>.supabase.co/functions/v1/inpi-relay
    INPEDIA_RELAY_KEY   chave publicável (anon) do projeto Supabase
"""
import os
import re
import time

import requests

from inpi_parser import parse_inpi_detail

BASE_URL = "https://busca.inpi.gov.br/pePI/servlet/MarcasServletController"
LOGIN_URL = "https://busca.inpi.gov.br/pePI/servlet/LoginController?action=login"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Origin': 'https://busca.inpi.gov.br',
    'Referer': 'https://busca.inpi.gov.br/pePI/jsp/marcas/Pesquisa_num_processo.jsp',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Content-Type': 'application/x-www-form-urlencoded',
}

# Mensagens mostradas ao usuário final, uma por tipo de falha
MENSAGENS = {
    "bloqueio_geografico": "O INPI recusou a conexão deste servidor: o INPI bloqueia acessos vindos de fora do Brasil, e o relay em São Paulo não está configurado.",
    "relay_chave": "O relay recusou a chave de acesso (verifique INPEDIA_RELAY_KEY nos secrets do app).",
    "relay_indisponivel": "O relay em São Paulo não respondeu (o projeto Supabase pode estar pausado por inatividade: reative-o no painel do Supabase).",
    "inpi_timeout": "O INPI não respondeu a tempo (o serviço do INPI está lento ou fora do ar). Tente novamente em alguns minutos.",
    "inpi_conexao": "Falha de conexão com o INPI.",
    "inpi_http": "O INPI respondeu com erro.",
    "nao_encontrado": "Processo não encontrado no INPI.",
    "pagina_inesperada": "A página do INPI veio em formato inesperado (o layout pode ter mudado).",
    "entrada_invalida": "Número de processo inválido.",
}


def _config(nome):
    valor = os.environ.get(nome)
    if valor:
        return valor
    try:
        import streamlit as st
        return st.secrets.get(nome)
    except Exception:
        return None


class INPIEngine:
    def __init__(self, modo="auto", relay_url=None, relay_key=None, regiao="sa-east-1"):
        self.modo_solicitado = modo          # "auto", "direto" ou "relay"
        self.modo = None                     # modo efetivamente em uso após initialize_session
        self.relay_url = relay_url or _config("INPEDIA_RELAY_URL")
        self.relay_key = relay_key or _config("INPEDIA_RELAY_KEY")
        self.regiao = regiao
        self.session = requests.Session()
        self.relay_session = requests.Session()  # keep-alive: evita um handshake HTTPS por processo (~0,35 s)
        self.relay_cookie = ""
        self.last_error = ""
        self.last_error_tipo = ""
        self.diagnostico = []                # passo a passo, para mostrar ao usuário quando algo falha

    # ─── inicialização ───
    def initialize_session(self):
        self.last_error = self.last_error_tipo = ""
        self.diagnostico = []
        if self.modo_solicitado in ("auto", "direto"):
            try:
                self.session.get(LOGIN_URL, headers=HEADERS, timeout=(5, 15))
                self.modo = "direto"
                self.diagnostico.append("Conexão direta com o INPI: ok")
                return True
            except requests.exceptions.ConnectTimeout:
                self.diagnostico.append("Conexão direta com o INPI: recusada (sem resposta em 5 s; bloqueio de IP fora do Brasil)")
                tipo_direto = "bloqueio_geografico"
            except requests.exceptions.ReadTimeout:
                self.diagnostico.append("Conexão direta com o INPI: conectou, mas o INPI não respondeu")
                tipo_direto = "inpi_timeout"
            except requests.exceptions.RequestException as e:
                self.diagnostico.append(f"Conexão direta com o INPI: {type(e).__name__}: {e}")
                tipo_direto = "inpi_conexao"
            if self.modo_solicitado == "direto":
                return self._falha(tipo_direto)
            if not self.relay_url:
                self.diagnostico.append("Relay em São Paulo: não configurado (INPEDIA_RELAY_URL / INPEDIA_RELAY_KEY nos secrets)")
                return self._falha(tipo_direto)
        return self._iniciar_relay()

    def _iniciar_relay(self):
        if not self.relay_url or not self.relay_key:
            self.diagnostico.append("Relay: não configurado (INPEDIA_RELAY_URL / INPEDIA_RELAY_KEY)")
            return self._falha("bloqueio_geografico")
        resp, tipo = self._chamar_relay({"acao": "ping"})
        if tipo:
            return self._falha(tipo, resp.get("erro") if resp else None)
        self.relay_cookie = resp.get("cookie", "")
        self.modo = "relay"
        self.diagnostico.append(f"Relay em {resp.get('regiao')}: ok (INPI respondeu em {resp.get('ms')} ms)")
        return True

    def _falha(self, tipo, detalhe=None):
        self.last_error_tipo = tipo
        self.last_error = MENSAGENS[tipo] + (f" Detalhe: {detalhe}" if detalhe else "")
        return False

    def _chamar_relay(self, corpo):
        """Devolve (json, tipo_de_erro_ou_None)."""
        headers = {"Authorization": f"Bearer {self.relay_key}", "apikey": self.relay_key,
                   "x-region": self.regiao, "Content-Type": "application/json"}
        try:
            r = self.relay_session.post(self.relay_url, json=corpo, headers=headers, timeout=(10, 60))
        except requests.exceptions.RequestException as e:
            self.diagnostico.append(f"Relay: sem resposta ({type(e).__name__})")
            return None, "relay_indisponivel"
        if r.status_code in (401, 403):
            return None, "relay_chave"
        try:
            dados = r.json()
        except ValueError:
            self.diagnostico.append(f"Relay: resposta inválida HTTP {r.status_code}: {r.text[:200]}")
            return None, "relay_indisponivel"
        status = dados.get("status")
        if status in ("ok", "nao_encontrado"):
            return dados, None
        self.diagnostico.append(f"Relay em {dados.get('regiao')}: {status} — {dados.get('erro')}")
        return dados, status if status in MENSAGENS else "inpi_conexao"

    # ─── consulta de um processo ───
    def get_details(self, process_id):
        process_id = str(process_id)
        for tentativa in range(3):
            if self.modo == "relay":
                resultado, repetir = self._via_relay(process_id)
            else:
                resultado, repetir = self._direto(process_id)
            if not repetir or tentativa == 2:
                resultado["ID_Pesquisado"] = process_id
                return resultado
            time.sleep(2)

    def _erro(self, tipo, detalhe=None):
        return {"Erro": MENSAGENS[tipo] + (f" ({detalhe})" if detalhe else "")}

    def _via_relay(self, pid):
        dados, tipo = self._chamar_relay({"processo": pid, "cookie": self.relay_cookie})
        if dados and dados.get("cookie"):
            self.relay_cookie = dados["cookie"]
        if tipo:
            # timeouts e falhas de conexão valem nova tentativa; o resto não muda ao repetir
            return self._erro(tipo, (dados or {}).get("erro")), tipo in ("inpi_timeout", "inpi_conexao", "relay_indisponivel")
        if dados["status"] == "nao_encontrado":
            return self._erro("nao_encontrado"), False
        return self._analisar(dados["html"]), False

    def _direto(self, pid):
        payload = {'Action': 'searchMarca', 'NumPedido': pid, 'tipoPesquisa': 'BY_NUM_PROC'}
        try:
            r = self.session.post(BASE_URL, headers=HEADERS, data=payload, timeout=(5, 20))
            if r.status_code != 200:
                return self._erro("inpi_http", f"HTTP {r.status_code}"), True
            html = r.text
            if "nenhum resultado foi encontrado" in html.lower():
                return self._erro("nao_encontrado"), False
            m = re.search(r'Action=detail&CodPedido=(\d+)', html)
            if m:
                d = self.session.get(f"{BASE_URL}?Action=detail&CodPedido={m.group(1)}", headers=HEADERS, timeout=(5, 20))
                return self._analisar(d.text), False
            if "Marca:" in html:
                return self._analisar(html), False
            return self._erro("pagina_inesperada"), True
        except requests.exceptions.ConnectTimeout:
            # A conexão direta já foi aberta em initialize_session, então o IP não está bloqueado.
            # Sem resposta em 5 s no meio do lote é instabilidade do INPI: vale nova tentativa.
            return self._erro("inpi_timeout", "sem resposta ao conectar"), True
        except requests.exceptions.Timeout:
            return self._erro("inpi_timeout"), True
        except requests.exceptions.RequestException as e:
            return self._erro("inpi_conexao", type(e).__name__), True

    def _analisar(self, html):
        dados = parse_inpi_detail(html)
        if not dados.get("numero_processo") and not dados.get("situacao"):
            return self._erro("pagina_inesperada", "campos não localizados na página de detalhe")
        return dados


if __name__ == "__main__":
    engine = INPIEngine()
    if engine.initialize_session():
        print(f"Modo: {engine.modo}")
        print(engine.get_details("905879660"))
    else:
        print(engine.last_error)
        print("\n".join(engine.diagnostico))
