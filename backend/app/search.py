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
