# AMV — Clasificación y Enrutamiento de PQR (Azure AI Foundry)

Aplicación de referencia que clasifica PQR (Peticiones, Quejas y Reclamos), determina la
**entidad competente** citando la regla de jurisdicción, enruta el caso y genera un
**borrador de respuesta** con revisión humana obligatoria. Parte del prototipo estático
([index.html](index.html)) y lo lleva a un despliegue real en Azure.

- **Arquitectura de referencia:** [ARQUITECTURA.md](ARQUITECTURA.md)
- **Funcionamiento del prototipo:** [FUNCIONAMIENTO.md](FUNCIONAMIENTO.md)
- **Plan de implementación en Azure:** [PLAN-IMPLEMENTACION.md](PLAN-IMPLEMENTACION.md)

## Estructura

```
index.html              Prototipo estático original (modo demo, localStorage)
web/                    Frontend desplegable (Static Web App) conectado a la API
  index.html            Igual al prototipo + capa de API (modo live)
  config.js             Define window.AMV_API_BASE (vacío = demo)
backend/                API FastAPI (Azure Container Apps)
  app/
    main.py             Endpoints REST
    pipeline.py         Orquestación: clasificar → competencia (RAG) → enrutar → borrador
    ai.py               Clientes de modelos (gpt-4o + MAI vía azure-ai-inference)
    search.py           RAG de reglas (Azure AI Search, con respaldo local)
    store.py            Table Storage (con respaldo en memoria)
    seed.py, models.py, config.py
  Dockerfile
infra/                  Bicep (azd): AI Services, AI Search, Storage, Service Bus, ACA, SWA
azure.yaml              Configuración de Azure Developer CLI
```

> La orquestación vive hoy en el backend. Migrarla a **Foundry Agent Service** (agente RAG
> con tools) es un paso posterior descrito en el plan.

## Modelos (verificado en `eastus2`, sub `bd70db0b-…`)

| Tarea | Deployment | Notas |
|---|---|---|
| Clasificación (JSON estricto) | `gpt-4o` | `MAI-1` no existe en el catálogo |
| Competencia (razonamiento/RAG) | `mai-thinking-1` (o `mai-ds-r1` si disponible) | `deployMaiDsR1=true` en Bicep para intentarlo |
| Borrador de respuesta | `mai-thinking-1` | |
| Embeddings | `text-embedding-3-large` | |

Los nombres de deployment son variables de entorno, por lo que se puede cambiar de modelo
sin tocar código.

## Ejecutar en local (modo demo, sin Azure)

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
```

Sin variables de entorno, el backend usa un almacén en memoria y una heurística de respaldo
en el pipeline (datos del seed), por lo que funciona sin nube. El frontend `web/index.html`
funciona offline en modo demo; para apuntarlo a la API local abrir
`web/index.html?api=http://localhost:8000`.

## Desplegar en Azure (azd)

Requiere [Azure Developer CLI](https://aka.ms/azd) y acceso a la suscripción destino.

```powershell
azd auth login
azd env new amv-pqr
azd env set AZURE_SUBSCRIPTION_ID bd70db0b-5ee5-488d-89c8-83cdd803614a
azd env set AZURE_LOCATION eastus2
azd up
```

`azd up` crea el grupo `rg-amv-pqr`, provisiona la infraestructura (Bicep), construye la
imagen del backend con ACR remoto (sin Docker local) y publica el frontend. Autenticación
por **Managed Identity**; sin claves ni Key Vault (requisito del entorno gobernado).

Tras el despliegue, poner la URL de la API (`API_URI` en los outputs) en `web/config.js`
(`__API_BASE__`) o abrir el sitio con `?api=<API_URI>` para activar el modo live.

## Endpoints principales

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/health` | Estado y servicios activos |
| GET | `/api/kpis` | Totales por estado/tipo y casos de baja confianza |
| GET | `/api/casos` | Lista con filtros `tipo`, `canal`, `estado`, `q` |
| GET | `/api/casos/{id}` | Detalle de un caso |
| POST | `/api/casos/{id}/analizar` | Ejecuta el pipeline y devuelve clasificación, competencia y borrador |
| POST | `/api/casos/{id}/decision` | Registra la decisión humana (estado) |
| GET | `/api/reglas` | Reglas de jurisdicción |
| GET | `/api/audit` | Registro de auditoría |

## Seguridad y gobierno

- Managed Identity + RBAC para todos los servicios (AI, Search, Storage, Service Bus).
- `disableLocalAuth=true` en AI Services y Storage (sin claves).
- Umbral de confianza configurable (`CONFIANZA_MIN`); por debajo, el caso se deriva a
  revisión manual antes de enrutar o responder.
- Auditoría append-only de cada decisión.
