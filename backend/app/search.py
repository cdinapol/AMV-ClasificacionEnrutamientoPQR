"""Recuperación de reglas de jurisdicción (RAG).

Usa Azure AI Search cuando SEARCH_ENDPOINT está configurado; si no, hace un ranking
simple por solapamiento de términos sobre las reglas del store (respaldo local).
"""
from __future__ import annotations
import re
from functools import lru_cache

from . import config


@lru_cache(maxsize=1)
def _search_client():
    from azure.search.documents import SearchClient
    from azure.identity import DefaultAzureCredential
    return SearchClient(
        endpoint=config.SEARCH_ENDPOINT,
        index_name=config.SEARCH_INDEX,
        credential=DefaultAzureCredential(),
    )


def ensure_index() -> bool:
    """Crea el índice de reglas si no existe. Best-effort; devuelve True si quedó listo."""
    if not config.search_enabled():
        return False
    try:
        from azure.identity import DefaultAzureCredential
        from azure.search.documents.indexes import SearchIndexClient
        from azure.search.documents.indexes.models import (
            SearchIndex, SimpleField, SearchableField, SearchFieldDataType,
        )
        client = SearchIndexClient(config.SEARCH_ENDPOINT, DefaultAzureCredential())
        existing = {i.name for i in client.list_indexes()}
        if config.SEARCH_INDEX not in existing:
            index = SearchIndex(
                name=config.SEARCH_INDEX,
                fields=[
                    SimpleField(name="id", type=SearchFieldDataType.String, key=True),
                    SearchableField(name="entidad", type=SearchFieldDataType.String, filterable=True),
                    SearchableField(name="texto", type=SearchFieldDataType.String),
                    SimpleField(name="vigente", type=SearchFieldDataType.Boolean, filterable=True),
                ],
            )
            client.create_index(index)
        return True
    except Exception as exc:
        print(f"[search] no se pudo crear el índice ({exc}).")
        return False


def sync_reglas(reglas: list[dict]) -> None:
    """Sincroniza las reglas al índice (best-effort)."""
    if not config.search_enabled():
        return
    try:
        if not ensure_index():
            return
        docs = [
            {"id": r["id"], "entidad": r.get("entidad", ""),
             "texto": r.get("texto", ""), "vigente": bool(r.get("vigente", True))}
            for r in reglas
        ]
        if docs:
            _search_client().merge_or_upload_documents(docs)
    except Exception as exc:
        print(f"[search] no se pudo sincronizar reglas ({exc}).")


def _tokens(s: str) -> set[str]:
    return {t for t in re.findall(r"\w+", s.lower()) if len(t) > 3}


def recuperar_reglas(texto: str, reglas_locales: list[dict], k: int = 3) -> list[dict]:
    if config.search_enabled():
        try:
            results = _search_client().search(search_text=texto, top=k)
            out = []
            for r in results:
                out.append({
                    "id": r.get("id", ""),
                    "entidad": r.get("entidad", ""),
                    "texto": r.get("texto", ""),
                })
            if out:
                return out
        except Exception as exc:
            print(f"[search] no disponible ({exc}); usando ranking local.")

    q = _tokens(texto)
    ranked = sorted(
        reglas_locales,
        key=lambda r: len(q & _tokens(r["texto"] + " " + r["entidad"])),
        reverse=True,
    )
    return ranked[:k]
