# backend/main.py
from pathlib import Path
import sys
import json
from typing import Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

# --- VERIFICAÇÃO E LOG DE MÓDULOS NA INICIALIZAÇÃO ---
print("="*50)
print("Iniciando verificação e importação de módulos...")
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path: sys.path.insert(0, str(BASE_DIR))

modulos_status = { "chat_router": False, "ClienteBinance": False, "ColetorDeAtivos": False, "Estrategia": False, "AnalistaFinanceiro": False, "coletor_noticias": False, "AnalisadorMercadoCMC": False }

try:
    from api.chat_agent_router import router as chat_router
    modulos_status["chat_router"] = True
    print("[OK] Módulo 'chat_agent_router' carregado.")
except ImportError:
    chat_router = None
    print("[FALHA] Módulo 'chat_agent_router' não encontrado.")
try:
    from api.binance_cliente import ClienteBinance
    modulos_status["ClienteBinance"] = True
    print("[OK] Módulo 'ClienteBinance' carregado.")
except ImportError:
    ClienteBinance = None
    print("[FALHA] Módulo 'ClienteBinance' não encontrado.")
try:
    from estrategia.coletor_dinamico import ColetorDeAtivos
    modulos_status["ColetorDeAtivos"] = True
    print("[OK] Módulo 'ColetorDeAtivos' carregado.")
except ImportError:
    ColetorDeAtivos = None
    print("[FALHA] Módulo 'ColetorDeAtivos' não encontrado.")
try:
    from estrategia.logica_sinal import Estrategia
    modulos_status["Estrategia"] = True
    print("[OK] Módulo 'Estrategia' carregado.")
except ImportError:
    Estrategia = None
    print("[FALHA] Módulo 'Estrategia' não encontrado.")
try:
    from estrategia.analista import AnalistaFinanceiro
    modulos_status["AnalistaFinanceiro"] = True
    print("[OK] Módulo 'AnalistaFinanceiro' carregado.")
except ImportError:
    AnalistaFinanceiro = None
    print("[FALHA] Módulo 'AnalistaFinanceiro' não encontrado.")
try:
    from noticias import noticias as coletor_noticias
    modulos_status["coletor_noticias"] = True
    print("[OK] Módulo 'coletor_noticias' carregado.")
except ImportError:
    coletor_noticias = None
    print("[FALHA] Módulo 'coletor_noticias' não encontrado.")
try:
    from api.analise_mercado import AnalisadorMercadoCMC
    modulos_status["AnalisadorMercadoCMC"] = True
    print("[OK] Módulo 'AnalisadorMercadoCMC' carregado.")
except ImportError:
    AnalisadorMercadoCMC = None
    print("[FALHA] Módulo 'AnalisadorMercadoCMC' não encontrado.")
print("Verificação de módulos concluída.")
print("="*50)
# --- FIM DA VERIFICAÇÃO ---

app = FastAPI(title="Agente Trader Cripto", version="1.6")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

FRONTEND_DIR = BASE_DIR.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static_frontend")
    print(f"[INFO] Servindo arquivos estáticos da pasta: {FRONTEND_DIR}")

if modulos_status["chat_router"] and chat_router:
    app.include_router(chat_router, prefix="/api", tags=["agent"])
    print("[INFO] Router do agente de chat registrado em /api/agent/*")

@app.get("/", response_class=FileResponse, include_in_schema=False)
async def root_index():
    index_path = FRONTEND_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="Arquivo index.html não encontrado.")
    return FileResponse(index_path)

@app.get("/api/noticias")
async def obter_noticias():
    assert coletor_noticias is not None, "Módulo de notícias não carregado."
    caminho_noticias = BASE_DIR / "data" / "noticias.json"
    if not caminho_noticias.exists():
        try:
            print("[INFO] Arquivo noticias.json não encontrado. Tentando coletar agora...")
            coletor_noticias.coletar_e_salvar_noticias()
        except Exception as e:
            print(f"[ERRO] Falha ao coletar notícias sob demanda: {e}")
            raise HTTPException(status_code=500, detail="Falha ao gerar arquivo de notícias.")
    
    if not caminho_noticias.exists():
         raise HTTPException(status_code=404, detail="Arquivo noticias.json não encontrado.")
    try:
        with open(caminho_noticias, "r", encoding="utf-8") as f:
            return JSONResponse(content=json.load(f))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao ler noticias.json: {e}")

@app.get("/api/dados/ativos")
async def listar_ativos():
    assert ColetorDeAtivos is not None, "Módulo ColetorDeAtivos não carregado."
    try:
        coletor = ColetorDeAtivos()
        return JSONResponse(content=coletor.carregar_ativos())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao carregar lista de ativos: {e}")

@app.get("/api/dashboard/{par_ativo}")
def obter_dados_dashboard(par_ativo: str, intervalo: str = "1m"):
    modulos_necessarios = ["ClienteBinance", "ColetorDeAtivos", "Estrategia", "AnalistaFinanceiro", "AnalisadorMercadoCMC"]
    if not all(modulos_status[m] for m in modulos_necessarios):
        raise HTTPException(status_code=501, detail="Um ou mais módulos de análise não foram inicializados.")
    
    assert ClienteBinance and ColetorDeAtivos and Estrategia and AnalistaFinanceiro and AnalisadorMercadoCMC

    try:
        binance_client, coletor_ativos, estrategia, analista_ia, analisador_mercado = \
        ClienteBinance(), ColetorDeAtivos(), Estrategia(), AnalistaFinanceiro(), AnalisadorMercadoCMC()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao instanciar módulos: {e}")

    simbolo_para_api = f"{par_ativo.upper()}USDT"
    info_ativo_base = next((a for a in coletor_ativos.carregar_ativos() if a.get("codigo", "").upper() == par_ativo.upper()), None)
    if not info_ativo_base:
        raise HTTPException(status_code=404, detail=f"Ativo {par_ativo} não encontrado")

    # --- CORREÇÃO DE RESILIÊNCIA ---
    # Garante que a chave 'analise_mercado' sempre exista.
    try:
        dados_sentimento = analisador_mercado.get_asset_data(symbol=par_ativo.upper())
        info_ativo_completa = {**info_ativo_base, "analise_mercado": dados_sentimento}
    except Exception as e:
        print(f"[AVISO] Falha ao buscar dados de sentimento em tempo real: {e}")
        info_ativo_completa = {**info_ativo_base, "analise_mercado": {"error": f"Falha ao buscar dados: {e}"}}

    try:
        maior_periodo = max(v for k, v in estrategia.params.items() if 'period' in k)
        df_klines = binance_client.obter_klines_historicos(par=simbolo_para_api, intervalo=intervalo, limite=maior_periodo + 50)
        dados_tecnicos = estrategia.processar_e_salvar_indicadores(df_klines, simbolo_para_api)
        dados_tecnicos = dados_tecnicos or {}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro nos indicadores: {e}")

    try:
        analise_ia_result = analista_ia.obter_analise(dados_tecnicos, info_ativo_completa)
    except Exception as e:
        analise_ia_result = {"error": "Falha na análise da IA", "detail": str(e)}

    return JSONResponse(content={
        "info_ativo": info_ativo_completa,
        "analise_ia": analise_ia_result,
        "indicadores_tecnicos": dados_tecnicos,
    })

print("\n[INFO] API iniciada. Verifique os logs de carregamento de módulos acima.")

