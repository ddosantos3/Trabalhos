# Agente Trader Preditivo com IA (Binance)

Este projeto implementa um backend em Python (FastAPI) para an�lise de mercado cripto (Binance), integrando indicadores t�cnicos, coleta de not�cias econ�micas e um agente de IA para gerar recomenda��es de trading apresentadas em um dashboard.

## Vis�o Geral
- Backend em Python com FastAPI.
- Integra��o com Binance para klines e pre�os em tempo real.
- C�lculo de indicadores t�cnicos (EMA, RSI, VWAP e Bandas de VWAP).
- Coleta de not�cias econ�micas (web scraping do calend�rio do MyFxBook).
- Agente de IA (RAG + LLM) que produz recomenda��es estruturadas ("COMPRAR", "VENDER", "MANTER").
- Estrutura pronta para um frontend web simples (HTML/CSS/JS).

## Principais M�dulos
- `api/`: rotas FastAPI (ativos, an�lise, not�cias, sa�de do servi�o).
- `estrategia/`: c�lculo de indicadores e l�gica de decis�o.
- `agent/`: agente de IA, contexto, RAG (arquivos em `data/`).
- `utils/`: helpers (datas, normaliza��o, tradingview widgets, etc.).
- `config/`: configs, vari�veis de ambiente e credenciais (usar `.env`).
- `data/`: bases locais para RAG e artefatos (evitar versionar dados sens�veis).

## Requisitos
- Python 3.10+
- `pip install -r requirements.txt`
- Vari�veis `.env` (exemplos):
  - `BINANCE_API_KEY` e `BINANCE_SECRET_KEY`
  - `OPENAI_API_KEY` (ou provedor compat�vel)
  - `NEWS_REGION` (ex.: BR, US)

## Como Executar
1. Crie e ative seu ambiente virtual (`python -m venv .venv` e ative).
2. Instale depend�ncias: `pip install -r requirements.txt`.
3. Configure `.env` em `backend/` com suas chaves.
4. Rode a API: `uvicorn api.main:app --reload`.
5. Acesse o Swagger: `http://localhost:8000/docs`.

## Fluxo de An�lise (Resumo)
1. O usu�rio seleciona ativo/timeframe e solicita an�lise.
2. A API busca klines recentes na Binance.
3. Os indicadores s�o calculados em `estrategia/`.
4. O agente de IA recebe o contexto (indicadores + sentimento + conhecimento em `data/`).
5. A IA retorna JSON com a��o, confian�a e justificativa.
6. A API consolida e retorna para o frontend renderizar no dashboard.

## Roadmap
- Execu��o de ordens reais/tempo simulado via Binance (trade engine seguro).
- Backtesting com m�tricas (CAGR, MDD, Sharpe) e otimiza��o de par�metros.
- Estrat�gias adicionais (Breakout, Mean Reversion, Momentum multi-timeframe).
- Melhoria do RAG com embeddings e indexa��o vetorial (FAISS/Chroma).
- Alertas por e-mail/Telegram e webhooks personaliz�veis.
- Cache de dados e filas para scraping/integra��es mais robustas.
- Dockerfile e Compose para desenvolvimento e produ��o.

## Boas Pr�ticas e Seguran�a
- Nunca exponha chaves de API no reposit�rio; use `.env`.
- Evite operar em contas reais sem limites e prote��es.
- Valide inputs e trate exce��es nas rotas.
- Fa�a logs estruturados e centralize erros.

## Estrutura (exemplo)
```
backend/
+- api/
+- agent/
+- estrategia/
+- utils/
+- config/
+- data/
+- logs/
+- main.py
+- requirements.txt
```

## Licen�a
Defina a licen�a conforme sua prefer�ncia (ex.: MIT). Caso deseje, adiciono um arquivo `LICENSE`.

---
Criado com foco em clareza, extensibilidade e seguran�a para opera��es de trading algor�tmico.
