import requests
from bs4 import BeautifulSoup
import urllib3
import time
import ssl
import re
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context
from inpi_parser import parse_inpi_detail

# Desabilitar avisos de SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

CIPHERS = (
    'ECDHE-RSA-AES256-GCM-SHA384:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-SHA384:'
    'ECDHE-ECDSA-AES256-SHA384:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-SHA256:'
    'AES256-GCM-SHA384:AES128-GCM-SHA256:AES256-SHA256:AES128-SHA256:AES256-SHA:AES128-SHA'
)

class TlsAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        context = create_urllib3_context(ciphers=CIPHERS)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        kwargs['ssl_context'] = context
        return super(TlsAdapter, self).init_poolmanager(*args, **kwargs)

    def proxy_manager_for(self, *args, **kwargs):
        context = create_urllib3_context(ciphers=CIPHERS)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        kwargs['ssl_context'] = context
        return super(TlsAdapter, self).proxy_manager_for(*args, **kwargs)

class INPIEngine:
    def __init__(self):
        self.session = requests.Session()
        self.session.mount('https://', TlsAdapter())
        self.base_url = "https://busca.inpi.gov.br/pePI/servlet/MarcasServletController"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Origin': 'https://busca.inpi.gov.br',
            'Referer': 'https://busca.inpi.gov.br/pePI/jsp/marcas/Pesquisa_num_processo.jsp',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Content-Type': 'application/x-www-form-urlencoded',
        }

    def initialize_session(self):
        try:
            login_url = "https://busca.inpi.gov.br/pePI/servlet/LoginController?action=login"
            self.session.get(login_url, verify=False, timeout=15)
            return True
        except Exception as e:
            print(f"Erro ao inicializar sessão: {e}")
            return False

    def get_details(self, process_id):
        payload = {
            'Action': 'searchMarca',
            'NumPedido': str(process_id),
            'tipoPesquisa': 'BY_NUM_PROC'
        }
        
        for attempt in range(3):
            try:
                response = self.session.post(self.base_url, headers=self.headers, data=payload, verify=False, timeout=20)
                
                if response.status_code == 200:
                    html = response.text
                    
                    # 1. Verificar se há link de detalhes (Action=detail)
                    # O link pode estar no formato: MarcasServletController?Action=detail&CodPedido=XXXX
                    match = re.search(r'Action=detail&CodPedido=(\d+)', html)
                    if match:
                        cod_pedido = match.group(1)
                        detail_url = f"https://busca.inpi.gov.br/pePI/servlet/MarcasServletController?Action=detail&CodPedido={cod_pedido}"
                        
                        res_detail = self.session.get(detail_url, headers=self.headers, verify=False, timeout=20)
                        if res_detail.status_code == 200:
                            result = parse_inpi_detail(res_detail.text)
                            result["ID_Pesquisado"] = process_id
                            return result
                    
                    # 2. Verificar se já caiu na página de detalhes
                    if "Nº do Processo:" in html or "Marca:" in html:
                        result = parse_inpi_detail(html)
                        result["ID_Pesquisado"] = process_id
                        if result.get("numero_processo"):
                            return result
                        
                    # 3. Verificar se não encontrou nada
                    if "não foram encontrados" in html.lower() or "nenhum processo" in html.lower():
                        return {"ID_Pesquisado": process_id, "Erro": "Processo não encontrado"}

                time.sleep(1)
            except Exception as e:
                if attempt == 2:
                    return {"ID_Pesquisado": process_id, "Erro": f"Erro de Conexão: {str(e)}"}
                time.sleep(2)
        
        return {"ID_Pesquisado": process_id, "Erro": "Falha na extração ou tempo esgotado"}

if __name__ == "__main__":
    engine = INPIEngine()
    if engine.initialize_session():
        print(engine.get_details("905879660"))
