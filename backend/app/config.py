"""Configuración por variables de entorno. Sin secretos en código: todo por Managed Identity."""
import os


def _clean(v: str | None) -> str:
    return (v or "").strip()


# Azure AI (Foundry / AI Services) — endpoints AAD-only (disableLocalAuth=true)
AI_SERVICES_ENDPOINT = _clean(os.getenv("AI_SERVICES_ENDPOINT"))          # https://<cuenta>.openai.azure.com
AI_INFERENCE_ENDPOINT = _clean(os.getenv("AI_INFERENCE_ENDPOINT"))        # https://<cuenta>.services.ai.azure.com/models
OPENAI_API_VERSION = _clean(os.getenv("OPENAI_API_VERSION")) or "2024-10-21"

# Deployment names (parametrizados para poder cambiar de modelo sin tocar código)
DEPLOY_CLASSIFY = _clean(os.getenv("DEPLOY_CLASSIFY")) or "gpt-4o"
DEPLOY_COMPETENCE = _clean(os.getenv("DEPLOY_COMPETENCE")) or "mai-thinking-1"
DEPLOY_DRAFT = _clean(os.getenv("DEPLOY_DRAFT")) or "mai-thinking-1"
DEPLOY_EMBEDDINGS = _clean(os.getenv("DEPLOY_EMBEDDINGS")) or "text-embedding-3-large"

# Azure AI Search (índice de reglas de jurisdicción)
SEARCH_ENDPOINT = _clean(os.getenv("SEARCH_ENDPOINT"))
SEARCH_INDEX = _clean(os.getenv("SEARCH_INDEX")) or "reglas-idx"

# Storage (Tables para casos/auditoría, Blob para adjuntos) — identity-based
STORAGE_ACCOUNT = _clean(os.getenv("STORAGE_ACCOUNT"))
TABLE_CASOS = _clean(os.getenv("TABLE_CASOS")) or "casos"
TABLE_AUDITORIA = _clean(os.getenv("TABLE_AUDITORIA")) or "auditoria"
TABLE_REGLAS = _clean(os.getenv("TABLE_REGLAS")) or "reglas"

# Umbral de confianza: por debajo => revisión manual obligatoria antes de enrutar/responder
CONFIANZA_MIN = int(_clean(os.getenv("CONFIANZA_MIN")) or "70")

CORS_ORIGINS = _clean(os.getenv("CORS_ORIGINS")) or "*"


def ai_enabled() -> bool:
    return bool(AI_SERVICES_ENDPOINT or AI_INFERENCE_ENDPOINT)


def storage_enabled() -> bool:
    return bool(STORAGE_ACCOUNT)


def search_enabled() -> bool:
    return bool(SEARCH_ENDPOINT)
