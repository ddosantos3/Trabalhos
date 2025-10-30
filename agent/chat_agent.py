# backend/agent/chat_agent.py
"""
ChatAgent RAG-ready para agir como Analista Financeiro Sênior.

Atualizações nesta versão:
- Corrige avisos do Pylance relacionados a tipos do cliente `openai.OpenAI`
  (cast de mensagens/resp para `Any` na hora da chamada).
- Mantém persistência de embeddings (pickle), chunking e busca semântica.
"""

from __future__ import annotations
import os
import json
import pickle
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple, cast

import numpy as np

# OpenAI client (versões 1.x+)
try:
    from openai import OpenAI
    # Adicionando os tipos específicos para clareza e correção de tipagem
    from openai.types.create_embedding_response import CreateEmbeddingResponse
    from openai.types.chat import ChatCompletionMessageParam
except Exception as e:
    raise RuntimeError("Erro: biblioteca openai não encontrada. Instale `pip install openai>=1.0.0`.") from e

# Configuráveis por ENV ou config/settings.py
try:
    from config import settings  # type: ignore
    OPENAI_KEY = getattr(settings, "OPENAI_API_KEY", None)
    CHAT_MODEL = getattr(settings, "OPENAI_MODEL", "gpt-4o-mini")
    EMBEDDING_MODEL = getattr(settings, "OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
    TEMPERATURE = float(getattr(settings, "OPENAI_TEMPERATURE", 0.3))
    SYSTEM_PROMPT_BASE = getattr(settings, "PROMPT_ANALISTA_SISTEMA", "Você é um analista financeiro sênior.")
except Exception:
    OPENAI_KEY = os.getenv("OPENAI_API_KEY")
    CHAT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
    TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", "0.3"))
    SYSTEM_PROMPT_BASE = os.getenv("PROMPT_ANALISTA_SISTEMA", "Você é um analista financeiro sênior.")

# instanciar client
_client_kwargs: Dict[str, Any] = {}
if OPENAI_KEY:
    _client_kwargs["api_key"] = OPENAI_KEY
client = OpenAI(**_client_kwargs)  # se api_key não fornecido, usará env var OPENAI_API_KEY

# Persistência
DEFAULT_STORE = Path(__file__).resolve().parents[2] / "data" / "embeddings_store.pkl"  # backend/data/embeddings_store.pkl


@dataclass
class DocChunk:
    text: str
    source: str
    meta: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[np.ndarray] = None

    def to_serializable(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "source": self.source,
            "meta": self.meta,
            "embedding": None if self.embedding is None else self.embedding.astype(np.float32).tolist()
        }

    @staticmethod
    def from_serializable(d: Dict[str, Any]) -> "DocChunk":
        emb = d.get("embedding")
        emb_arr = None if emb is None else np.array(emb, dtype=np.float32)
        return DocChunk(text=d["text"], source=d["source"], meta=d.get("meta", {}), embedding=emb_arr)


def chunk_text(text: str, max_chars: int = 1400) -> List[str]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]
    parts: List[str] = []
    cur = ""
    for line in text.splitlines():
        if len(cur) + len(line) + 1 <= max_chars:
            cur += (line + "\n")
        else:
            parts.append(cur.strip())
            cur = line + "\n"
    if cur.strip():
        parts.append(cur.strip())
    out: List[str] = []
    for p in parts:
        if len(p) <= max_chars:
            out.append(p)
        else:
            for i in range(0, len(p), max_chars):
                out.append(p[i:i + max_chars])
    return out


def cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / ((np.linalg.norm(a) * np.linalg.norm(b)) + 1e-12))


class ChatAgent:
    def __init__(self, data_dir: str | Path, embedding_model: str = EMBEDDING_MODEL, chat_model: str = CHAT_MODEL, store_path: Optional[Path] = None):
        self.data_dir = Path(data_dir)
        if not self.data_dir.exists():
            raise FileNotFoundError(f"data_dir não encontrado: {self.data_dir}")
        self.embedding_model = embedding_model
        self.chat_model = chat_model
        self.chunks: List[DocChunk] = []
        self.store_path = Path(store_path) if store_path else DEFAULT_STORE
        self.manifest: Dict[str, Any] = {}
        if not self._try_load_store():
            self.reload_documents()

    # ----------------------------
    # Document loading & chunking
    # ----------------------------
    def reload_documents(self, force_reembed: bool = False):
        files = sorted([p for p in self.data_dir.glob("*.json")])
        if not files:
            self.chunks = []
            self.manifest = {}
            return

        if self.store_path.exists() and not force_reembed:
            try:
                with open(self.store_path, "rb") as f:
                    store = pickle.load(f)
                stored_manifest = store.get("manifest", {})
                current_manifest = {str(p.name): p.stat().st_mtime for p in files}
                if stored_manifest == current_manifest:
                    print("[ChatAgent] store disponível e manifest idêntico — usando embeddings persistidos.")
                    self._load_chunks_from_store(store)
                    return
                else:
                    print("[ChatAgent] store detectado, mas manifest mudou. Re-embeding será executado.")
            except Exception as e:
                print("[ChatAgent] falha lendo store (será re-embeding):", e)

        new_chunks: List[DocChunk] = []
        for p in files:
            try:
                with open(p, "r", encoding="utf-8") as fh:
                    obj = json.load(fh)
                txt = json.dumps(obj, ensure_ascii=False, indent=2)
                parts = chunk_text(txt, max_chars=1400)
                for i, part in enumerate(parts):
                    new_chunks.append(DocChunk(text=part, source=p.name, meta={"file": p.name, "idx": i}))
            except Exception as e:
                print(f"[ChatAgent] erro lendo {p}: {e}")

        self.chunks = new_chunks
        self._embed_all()
        manifest = {str(p.name): p.stat().st_mtime for p in files}
        self.manifest = manifest
        self.save_store()

    # ----------------------------
    # Embeddings generation & persistence
    # ----------------------------
    def _embed_all(self, batch_size: int = 30):
        texts = [c.text for c in self.chunks]
        if not texts:
            return
        embeddings: List[np.ndarray] = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            try:
                # A resposta da API é um objeto, não um dicionário.
                resp: CreateEmbeddingResponse = client.embeddings.create(model=self.embedding_model, input=batch)
                
                # --- CORREÇÃO APLICADA AQUI ---
                # Iteramos diretamente sobre `resp.data`, que é a lista de embeddings.
                for item in resp.data:
                    emb = self._extract_embedding_from_item(item)
                    embeddings.append(emb)

            except Exception as e:
                # Adicionando o traceback para um debug mais detalhado
                import traceback
                print(traceback.format_exc())
                raise RuntimeError(f"[ChatAgent] erro criando embeddings (batch {i}-{i+batch_size}): {e}")
        
        for c, emb in zip(self.chunks, embeddings):
            c.embedding = emb

    def _extract_embedding_from_item(self, item: Any) -> np.ndarray:
        # O `item` aqui é do tipo `openai.types.embedding.Embedding`
        # que tem um atributo `.embedding`
        emb_raw = getattr(item, "embedding", None)
        if emb_raw is None:
            raise RuntimeError("[ChatAgent] não foi possível extrair embedding do item retornado pela API.")
        return np.array(emb_raw, dtype=np.float32)

    def _embed_query(self, query: str) -> np.ndarray:
        try:
            resp: CreateEmbeddingResponse = client.embeddings.create(model=self.embedding_model, input=[query])
            item = resp.data[0]
            return self._extract_embedding_from_item(item)
        except Exception as e:
            raise RuntimeError(f"[ChatAgent] erro ao criar embedding para consulta: {e}")

    def save_store(self, path: Optional[Path] = None):
        p = Path(path) if path else self.store_path
        try:
            serial = {
                "manifest": self.manifest,
                "created_at": time.time(),
                "chunks": [c.to_serializable() for c in self.chunks]
            }
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "wb") as fh:
                pickle.dump(serial, fh)
            print(f"[ChatAgent] store salvo em {p} (chunks={len(self.chunks)})")
        except Exception as e:
            print(f"[ChatAgent] falha ao salvar store: {e}")

    def _load_chunks_from_store(self, store: Dict[str, Any]):
        loaded_chunks = [DocChunk.from_serializable(d) for d in store.get("chunks", [])]
        self.chunks = loaded_chunks
        self.manifest = store.get("manifest", {})
        print(f"[ChatAgent] carregado {len(self.chunks)} chunks do store.")

    def _try_load_store(self) -> bool:
        p = self.store_path
        if not p.exists():
            return False
        try:
            with open(p, "rb") as fh:
                store = pickle.load(fh)
            if "manifest" not in store or "chunks" not in store:
                return False
            files = sorted([f for f in self.data_dir.glob("*.json")])
            current_manifest = {str(p.name): p.stat().st_mtime for p in files}
            stored_manifest = store.get("manifest", {})
            if stored_manifest == current_manifest:
                self._load_chunks_from_store(store)
                return True
            else:
                return False
        except Exception as e:
            print("[ChatAgent] erro carregando store:", e)
            return False

    # ----------------------------
    # Busca semântica e resposta
    # ----------------------------
    def semantic_search(self, query: str, top_k: int = 6) -> List[Dict[str, Any]]:
        if not self.chunks:
            return []
        qemb = self._embed_query(query)
        scores: List[Tuple[float, DocChunk]] = []
        for c in self.chunks:
            if c.embedding is None:
                continue
            s = cosine_sim(qemb, c.embedding)
            scores.append((s, c))
        scores.sort(key=lambda x: x[0], reverse=True)
        top = scores[:top_k]
        return [{"score": float(s), "text": c.text, "source": c.source, "meta": c.meta} for s, c in top]

    def build_system_prompt(self) -> str:
        sys = SYSTEM_PROMPT_BASE + (
            "\n\nVocê é um Analista Financeiro Sênior — Trader Profissional com anos de experiência. "
            "Responda de forma objetiva, priorizando gestão de risco, clareza e indicando nível de confiança "
            "(baixo/médio/alto). Ao mencionar recomendações, referencie as fontes (arquivos) usadas."
        )
        return sys

    def _extract_chat_text(self, resp_obj: Any) -> str:
        """
        Extrai o texto retornado pela chat completion com múltiplos fallback
        para acomodar estruturas diferentes do client.
        """
        try:
            choices = getattr(resp_obj, "choices", [])
            if not choices: return ""
            first = choices[0]
            if hasattr(first, "message") and hasattr(first.message, "content"):
                return first.message.content or ""
        except Exception:
            pass
        return ""

    def answer(self, user_message: str, top_k: int = 6, dashboard_analysis: Optional[str] = None, max_tokens: int = 500, temperature: Optional[float] = None) -> Dict[str, Any]:
        if temperature is None:
            temperature = TEMPERATURE

        hits = self.semantic_search(user_message, top_k=top_k)

        ctx_parts = []
        for h in hits:
            ctx_parts.append(f"Fonte: {h['source']} (score={h['score']:.3f})\n{h['text']}")
        context_block = "\n\n---\n\n".join(ctx_parts) if ctx_parts else "Nenhuma fonte relevante encontrada."

        system_prompt = self.build_system_prompt()
        user_prompt = f"Contexto recuperado:\n{context_block}\n\n"
        if dashboard_analysis:
            user_prompt += f"Análise do Dashboard:\n{dashboard_analysis}\n\n"
        user_prompt += f"Pergunta do usuário: {user_message}\n\nInstruções: responda como analista sênior; indique nível de confiança e referências."

        # --- CORREÇÃO APLICADA AQUI ---
        # A API espera uma lista de `ChatCompletionMessageParam`, não uma lista de dicionários genéricos.
        # A estrutura dos dicionários está correta, mas a dica de tipo precisa ser a exata.
        messages_param: List[ChatCompletionMessageParam] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        try:
            resp = client.chat.completions.create(
                model=self.chat_model,
                messages=messages_param,
                temperature=float(temperature),
                max_tokens=int(max_tokens)
            )
            text = self._extract_chat_text(resp)
        except Exception as e:
            raise RuntimeError(f"[ChatAgent] erro ao chamar chat completion: {e}")

        return {
            "answer": text,
            "sources": [{"source": h["source"], "score": h["score"]} for h in hits]
        }


# ----------------------------
# CLI / utilitário
# ----------------------------
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="ChatAgent util (rebuild embeddings / info).")
    parser.add_argument("--data-dir", type=str, default=str(Path(__file__).resolve().parents[2] / "data"), help="Pasta com JSONs")
    # --- CORREÇÃO APLICADA AQUI ---
    # Corrigido o erro de digitação de 'add-argument' para 'add_argument'.
    parser.add_argument("--rebuild", action="store_true", help="Forçar rebuild (re-embeding) e salvar store")
    parser.add_argument("--info", action="store_true", help="Mostrar info do store / chunks")
    args = parser.parse_args()

    agent = ChatAgent(data_dir=args.data_dir)
    if args.rebuild:
        print("Forçando rebuild de documentos e embeddings...")
        agent.reload_documents(force_reembed=True)
    if args.info:
        print("Chunks carregados:", len(agent.chunks))
        print("Store_path:", agent.store_path)
        print("Manifest keys:", list(agent.manifest.keys())[:10])
    print("Pronto.")

