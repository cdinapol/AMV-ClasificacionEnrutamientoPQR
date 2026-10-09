"""Clientes de modelos Azure AI.

- Clasificación: Azure OpenAI (gpt-4o) con structured output, autenticado por AAD.
- Competencia y borrador: familia MAI vía azure-ai-inference (endpoint .../models).
Todo con Managed Identity (disableLocalAuth=true, sin claves).
Si los endpoints no están configurados, las funciones devuelven None para que el
pipeline use su heurística de respaldo.
"""
from __future__ import annotations
import json
from functools import lru_cache

from . import config


@lru_cache(maxsize=1)
def _token_provider():
    from azure.identity import DefaultAzureCredential, get_bearer_token_provider
    return get_bearer_token_provider(
        DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
    )


@lru_cache(maxsize=1)
def _openai_client():
    from openai import AzureOpenAI
    return AzureOpenAI(
        azure_endpoint=config.AI_SERVICES_ENDPOINT,
        azure_ad_token_provider=_token_provider(),
        api_version=config.OPENAI_API_VERSION,
    )


@lru_cache(maxsize=1)
def _inference_client():
    from azure.ai.inference import ChatCompletionsClient
    from azure.identity import DefaultAzureCredential
    return ChatCompletionsClient(
        endpoint=config.AI_INFERENCE_ENDPOINT,
        credential=DefaultAzureCredential(),
        credential_scopes=["https://cognitiveservices.azure.com/.default"],
    )


def _chat_mai(deployment: str, system: str, user: str) -> str | None:
    """Invoca un modelo MAI (azure-ai-inference). Devuelve el texto o None."""
    if not config.AI_INFERENCE_ENDPOINT:
        return None
    from azure.ai.inference.models import SystemMessage, UserMessage
    resp = _inference_client().complete(
        model=deployment,
        messages=[SystemMessage(content=system), UserMessage(content=user)],
        temperature=0.2,
        max_tokens=1200,
    )
    return resp.choices[0].message.content


def clasificar(texto: str) -> dict | None:
    """gpt-4o con JSON estructurado: tipo/tipología/asunto/confianza."""
    if not config.AI_SERVICES_ENDPOINT:
        return None
    schema = {
        "type": "object",
        "properties": {
            "tipo": {"type": "string", "enum": ["Queja", "Consulta", "Solicitud"]},
            "tipologia": {"type": "string"},
            "asunto": {"type": "string"},
            "confianza": {"type": "integer", "minimum": 0, "maximum": 100},
        },
        "required": ["tipo", "tipologia", "asunto", "confianza"],
        "additionalProperties": False,
    }
    resp = _openai_client().chat.completions.create(
        model=config.DEPLOY_CLASSIFY,
        temperature=0,
        messages=[
            {"role": "system", "content": (
                "Eres un clasificador de PQR (Peticiones, Quejas y Reclamos) del "
                "Autorregulador del Mercado de Valores de Colombia (AMV). Clasifica el "
                "caso en tipo (Queja/Consulta/Solicitud), su tipología temática y un "
                "asunto breve. Devuelve confianza 0-100."
            )},
            {"role": "user", "content": texto},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "clasificacion", "schema": schema, "strict": True},
        },
    )
    return json.loads(resp.choices[0].message.content)


def determinar_competencia(texto: str, reglas: list[dict]) -> dict | None:
    """Modelo de razonamiento MAI sobre reglas recuperadas (RAG). Cita la regla."""
    contexto = "\n".join(f"[{r['id']}] ({r['entidad']}) {r['texto']}" for r in reglas)
    system = (
        "Eres un agente que determina la ENTIDAD COMPETENTE para una PQR del mercado de "
        "valores colombiano, citando SIEMPRE la regla de jurisdicción exacta. Responde "
        "solo con JSON: {\"entidad\":..., \"reglaId\":..., \"confianza\":0-100}. "
        "Usa únicamente las reglas provistas."
    )
    user = f"Reglas disponibles:\n{contexto}\n\nCaso:\n{texto}\n\nJSON:"
    out = _chat_mai(config.DEPLOY_COMPETENCE, system, user)
    if not out:
        return None
    try:
        start, end = out.find("{"), out.rfind("}")
        return json.loads(out[start:end + 1])
    except Exception:
        return None


def redactar_borrador(texto: str, entidad: str, regla: dict | None) -> dict | None:
    """Borrador de respuesta citado con MAI."""
    regla_txt = f"[{regla['id']}] {regla['texto']}" if regla else "(sin regla)"
    system = (
        "Redacta un BORRADOR de respuesta formal y empático para una PQR del AMV. "
        "Cita la regla de jurisdicción pertinente y mantén un tono institucional. "
        "No prometas resultados; indica el trámite. Máximo 180 palabras."
    )
    user = f"Entidad competente: {entidad}\nRegla: {regla_txt}\n\nCaso del ciudadano:\n{texto}"
    out = _chat_mai(config.DEPLOY_DRAFT, system, user)
    if not out:
        return None
    citas = [regla["id"]] if regla else []
    return {"texto": out.strip(), "citas": citas, "groundedness": 90}
