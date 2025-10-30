import json
from pathlib import Path
from utils.logger import log

class ColetorDeAtivos:
    """
    Carrega a lista de ativos do arquivo de dados centralizado.
    Agora lê de 'ativos_sentimentos.json' na pasta 'data'.
    """
    def __init__(self):
        """
        Inicializa o coletor, definindo o caminho correto para o arquivo de ativos.
        """
        try:
            # Constrói o caminho correto e robusto a partir da localização deste script
            # .../estrategia/ -> .../backend/ -> .../backend/data/ativos_sentimentos.json
            self.caminho_arquivo = Path(__file__).resolve().parent.parent / "data" / "ativos_sentimentos.json"
            log.info(f"Coletor de Ativos inicializado. Usando lista de: {self.caminho_arquivo}")
        except Exception as e:
            log.error(f"Erro ao determinar o caminho do arquivo de ativos: {e}")
            self.caminho_arquivo = None

    def carregar_ativos(self) -> list[dict]:
        """
        Lê o arquivo JSON e retorna a lista de ativos contida nele.
        """
        if not self.caminho_arquivo or not self.caminho_arquivo.exists():
            log.critical(f"ARQUIVO DE ATIVOS NÃO ENCONTRADO EM: '{self.caminho_arquivo}'. Verifique se o arquivo está na pasta 'backend/data/'.")
            return []
        
        log.info(f"Carregando lista de ativos do arquivo '{self.caminho_arquivo.name}'...")
        try:
            with open(self.caminho_arquivo, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if isinstance(data, dict):
                ativos = data.get("ativos", [])
            elif isinstance(data, list):
                ativos = data
            else:
                log.error(f"Formato de dados inesperado em '{self.caminho_arquivo}'. Esperado dict ou list.")
                return []
            
            if not ativos:
                 log.warning(f"Nenhum ativo encontrado dentro do arquivo JSON '{self.caminho_arquivo.name}'.")
                 return []
                 
            log.info(f"Carregamento concluído. {len(ativos)} ativos encontrados.")
            return ativos
            
        except json.JSONDecodeError:
            log.critical(f"ERRO DE SINTAXE NO JSON: O arquivo '{self.caminho_arquivo}' não pôde ser lido.")
            return []
        except Exception as e:
            log.critical(f"Um erro inesperado ocorreu ao carregar os ativos: {e}", exc_info=True)
            return []

