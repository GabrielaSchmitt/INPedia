from bs4 import BeautifulSoup
import re

def parse_inpi_detail(html_content):
    """
    Extrai dados detalhados do processo de marca do HTML do INPI.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    data = {}
    
    # Função auxiliar para pegar texto de labels
    def get_text_by_label(label_text):
        element = soup.find(string=re.compile(re.escape(label_text), re.IGNORECASE))
        if element:
            parent_td = element.find_parent('td')
            if parent_td:
                next_td = parent_td.find_next_sibling('td')
                if next_td:
                    return next_td.get_text(strip=True)
                text = parent_td.get_text(strip=True)
                if ":" in text:
                    return text.split(":", 1)[1].strip()
        return ""

    # 1. Dados Básicos
    data["numero_processo"] = get_text_by_label("Nº do Processo:")
    data["marca"] = get_text_by_label("Marca:")
    data["situacao"] = get_text_by_label("Situação:")
    data["apresentacao"] = get_text_by_label("Apresentação:")
    data["natureza"] = get_text_by_label("Natureza:")
    
    # 2. Titulares
    titular = ""
    titulares_label = soup.find(string=re.compile("Titular\(1\):", re.IGNORECASE))
    if titulares_label:
        td = titulares_label.find_parent('td')
        if td:
            next_td = td.find_next_sibling('td')
            if next_td:
                titular = next_td.get_text(strip=True)
    data["titular"] = titular

    # 2b. Procurador
    procurador = ""
    procurador_label = soup.find(string=re.compile(r"Procurador", re.IGNORECASE))
    if procurador_label:
        td = procurador_label.find_parent('td')
        if td:
            next_td = td.find_next_sibling('td')
            if next_td:
                procurador = next_td.get_text(strip=True)
            else:
                text = td.get_text(strip=True)
                if ":" in text:
                    procurador = text.split(":", 1)[1].strip()
    data["procurador"] = procurador

    # 3. Datas e Prioridade (Busca em todas as tabelas)
    deposito = ""
    concessao = ""
    vigencia = ""
    prioridade = ""
    
    for table in soup.find_all("table"):
        text = table.get_text(strip=True)
        
        # Datas
        if "Data de Depósito" in text and not deposito:
            for row in table.find_all("tr"):
                cols = row.find_all(["td", "th"])
                row_text = "".join([c.get_text() for c in cols])
                if re.search(r'\d{2}/\d{2}/\d{4}', row_text):
                    if len(cols) >= 1: deposito = cols[0].get_text(strip=True)
                    if len(cols) >= 2: concessao = cols[1].get_text(strip=True)
                    if len(cols) >= 3: vigencia = cols[2].get_text(strip=True)
                    break
        
        # Prioridade
        if "Prioridade Unionista" in text and not prioridade:
            # Tenta pegar o valor após o label
            prio_match = re.search(r'Prioridade Unionista:?\s*(.*)', text, re.IGNORECASE)
            if prio_match:
                prioridade = prio_match.group(1).strip()
                # Limpar se vier com outros labels grudados
                prioridade = prioridade.split("Classe")[0].split("Apresentação")[0].strip()

    data["data_deposito"] = deposito
    data["data_concessao"] = concessao if concessao and concessao != "-" else ""
    data["data_vigencia"] = vigencia if vigencia and vigencia != "-" else ""
    data["prioridade"] = prioridade

    # 4. Classe de Nice e Especificação
    classe = ""
    especificacao = ""
    for table in soup.find_all("table"):
        text = table.get_text(strip=True)
        if "Classe de Nice" in text:
            for row in table.find_all("tr"):
                cols = row.find_all(["td", "th"])
                if len(cols) >= 3 and "NCL" in cols[0].get_text():
                    classe = cols[0].get_text(strip=True)
                    especificacao = cols[2].get_text(strip=True)
                    break
            if classe: break
    
    data["classe_nice"] = classe
    data["especificacao"] = especificacao

    # 5. Último Despacho (Publicações)
    ultimo_rpi = ""
    ultimo_data = ""
    ultimo_despacho = ""
    for table in soup.find_all("table"):
        text = table.get_text(strip=True)
        if "RPI" in text and "Data RPI" in text and "Despacho" in text:
            for row in table.find_all("tr"):
                cols = row.find_all(["td", "th"])
                if len(cols) >= 3:
                    rpi_val = cols[0].get_text(strip=True)
                    if rpi_val.isdigit():
                        ultimo_rpi = rpi_val
                        ultimo_data = cols[1].get_text(strip=True)
                        ultimo_despacho = cols[2].get_text(strip=True)
                        break
            if ultimo_rpi: break
    
    data["ultimo_despacho_rpi"] = ultimo_rpi
    data["ultimo_despacho_data"] = ultimo_data
    data["ultimo_despacho_titulo"] = ultimo_despacho

    return data
