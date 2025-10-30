# /backend/noticias/noticias.py

import requests
from bs4 import BeautifulSoup
import logging
import json
from pathlib import Path
from datetime import datetime, timezone

# --- Configuração do Logger e Caminhos ---
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] (Noticias) %(message)s')
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

URL_CALENDARIO = "https://www.myfxbook.com/pt/forex-economic-calendar"

def salvar_noticias(eventos: list):
    """
    Salva a lista de notícias coletadas em um arquivo JSON na pasta de dados.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    file_path = DATA_DIR / "noticias.json"
    now_utc = datetime.now(timezone.utc)

    output_data = {
        "metadata": {
            "ultima_coleta_em": now_utc.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "fonte": URL_CALENDARIO
        },
        "eventos_economicos": eventos
    }

    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=4, ensure_ascii=False)
        logging.info(f"Notícias salvas com sucesso em '{file_path}'. Total de {len(eventos)} eventos coletados.")
    except IOError as e:
        logging.error(f"Não foi possível salvar as notícias no arquivo '{file_path}': {e}")


def traduzir_impacto(titulo_impacto):
    mapeamento = {"Alto": "Alta Volatilidade", "Médio": "Moderada Volatilidade", "Baixo": "Baixa Volatilidade", "Feriado": "Feriado"}
    return mapeamento.get(titulo_impacto, "Indefinido")

def _encontrar_tabela_relevante(soup):
    for table in soup.find_all('table'):
        headers = [th.get_text(strip=True).lower() for th in table.find_all('th')]
        if any(k in " ".join(headers) for k in ('hora', 'moeda', 'evento')):
            return table
    return None

def coletar_e_salvar_noticias():
    """
    Coleta as notícias do calendário econômico, incluindo o país,
    e salva o resultado em um arquivo JSON.
    """
    logging.info("Iniciando coleta de notícias do calendário econômico...")
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(URL_CALENDARIO, headers=headers, timeout=20)
        response.raise_for_status()
    except requests.RequestException as e:
        logging.error(f"Erro de rede ao buscar notícias: {e}")
        return

    soup = BeautifulSoup(response.text, 'lxml')
    tabela = soup.find('table', id='economicCalendar') or _encontrar_tabela_relevante(soup)

    if not tabela:
        logging.warning("Nenhuma tabela de eventos econômicos encontrada na página.")
        return

    eventos_coletados = []
    tbody = tabela.find('tbody') or tabela
    
    def encontrar_linhas_de_evento(tag):
        return tag.name == 'tr' and tag.has_attr('class') and any('economicCalendarRow' in c for c in tag['class'])

    linhas = tbody.find_all(encontrar_linhas_de_evento)

    for linha in linhas:
        try:
            cols = linha.find_all('td')
            
            hora = cols[1].get_text(strip=True) if len(cols) > 1 else ""
            
            # --- ATUALIZAÇÃO: Coleta de País e Moeda ---
            moeda_td = cols[2] if len(cols) > 2 else None
            moeda = ""
            pais = ""
            if moeda_td:
                moeda = moeda_td.get_text(strip=True)
                img_tag = moeda_td.find('img')
                if img_tag and img_tag.has_attr('title'):
                    # --- CORREÇÃO APLICADA AQUI ---
                    # Garante que o valor de 'title' seja sempre uma string antes de usar .strip()
                    title_attr = img_tag.get('title', '')
                    if isinstance(title_attr, list):
                        pais_raw = title_attr[0] if title_attr else ''
                    else:
                        pais_raw = title_attr or ''
                    pais = pais_raw.strip()
            
            evento = cols[4].get_text(strip=True) if len(cols) > 4 else ""
            anterior = cols[5].get_text(strip=True) if len(cols) > 5 else "N/A"
            previsao = cols[6].get_text(strip=True) if len(cols) > 6 else "N/A"
            atual = cols[7].get_text(strip=True) if len(cols) > 7 else "N/A"

            impacto_td = cols[3] if len(cols) > 3 else None
            impacto_str = "Indefinido"
            if impacto_td:
                impacto_title_raw = impacto_td.get('title', '')
                impacto_title_str = ""
                if isinstance(impacto_title_raw, list):
                    impacto_title_str = impacto_title_raw[0] if impacto_title_raw else ''
                else:
                    impacto_title_str = impacto_title_raw or "" 

                impacto_title = impacto_title_str.replace('Impacto ', '')
                impacto_str = traduzir_impacto(impacto_title)

            if evento:
                 eventos_coletados.append({
                    "hora": hora,
                    "pais": pais,
                    "moeda": moeda, 
                    "impacto": impacto_str, 
                    "evento": evento,
                    "anterior": anterior,
                    "previsao": previsao,
                    "atual": atual
                })
        except IndexError:
            logging.warning("Linha da tabela com formato inesperado. Pulando.")
            continue

    if not eventos_coletados:
        logging.info("Nenhum evento econômico encontrado para coleta.")
    
    salvar_noticias(eventos_coletados)

# Para permitir a execução manual do script
if __name__ == "__main__":
    coletar_e_salvar_noticias()

