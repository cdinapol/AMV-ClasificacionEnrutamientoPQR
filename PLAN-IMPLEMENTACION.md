# Plan de implementación en Azure — Clasificación y Enrutamiento de PQR (AMV)

> MVP funcional end-to-end de **una ruta** basado en la arquitectura de referencia de
> [ARQUITECTURA.md](ARQUITECTURA.md). Lleva el prototipo estático ([index.html](index.html),
> hoy con `localStorage`) a un despliegue real en Azure.

## Contexto

- **Repo:** AMV-ClasificacionEnrutamientoPQR (hoy solo prototipo estático: ARQUITECTURA.md, FUNCIONAMIENTO.md, index.html con localStorage).
- **Suscripción destino:** `bd70db0b-5ee5-488d-89c8-83cdd803614a` (entorno gobernado `ME-MngEnvMCAP008935`).
- **Región:** `eastus2`.

## Decisiones

- **Alcance:** MVP funcional end-to-end de UNA ruta (ingesta → OCR → clasificación MAI-1 → competencia RAG/MAI-DS-R1 → borrador → revisión humana).
- **Frontend:** desplegar `index.html` tal cual como Azure Static Web App, conectado a una API real.
- **Backend:** Foundry Agent Service como orquestador principal; Azure Functions solo como *tools*.
- **Modelos:** verificar catálogo MAI-1 / MAI-DS-R1; **fallback a GPT-4o** si NO están disponibles (tanto clasificación/borrador como competencia).
- **CRM:** mock con Cosmos DB; sin CRM real todavía.
- **OCR (Document Intelligence):** **INCLUIDO** en el MVP; preprocesa adjuntos antes de clasificar.
- **Ingesta MVP:** solo Service Bus + un canal web/API. Correo (Graph/Exchange) queda para v2.

## Gotchas del entorno gobernado (verificados en proyectos previos)

- Azure Policy fuerza Key Vault `publicNetworkAccess=Disabled` → **NO** usar KV con acceso público. Usar **Managed Identity** + secrets nativos del recurso.
- Foundry agent hosted: setear `AZURE_AI_MODEL_DEPLOYMENT_NAME` o crashea *"Model is required"*.
- Sin Docker local → si se usa contenedor, `azd` con `remoteBuild:true` (ACR Tasks). Azure Functions no lo requiere.

## Arquitectura MVP (subconjunto de la de referencia)

```
Static Web App (index.html)
  → API (Functions)
    → Foundry Agent Service (orquestador RAG)
       ├─ tool preprocess  → Document Intelligence (OCR de adjuntos desde Blob)
       ├─ tool classify    → MAI-1 (tipo/tipología/asunto, structured output)
       ├─ tool competence  → AI Search (RAG reglas) + MAI-DS-R1 (o GPT-4o)
       ├─ tool route       → Cosmos DB (mock CRM: equipo/cola/SLA)
       └─ tool draft       → MAI-1 (borrador citado + groundedness)
```

- **Service Bus** (`pqr-ingesta`) desacopla la ingesta.
- **Cosmos DB** guarda casos, estado y auditoría.
- **AI Search** aloja el índice vectorial de reglas de jurisdicción.
- **Foundry evaluations** mide groundedness / exactitud.

## Fases

### Fase 0 — Prerrequisitos y verificación (bloquea todo)

- Confirmar acceso a la suscripción y región `eastus2`; `az account set`.
- Verificar catálogo de modelos **MAI-1** y **MAI-DS-R1** en Foundry del tenant (az cli / portal). Definir fallback: **GPT-4o** (clasificación/borrador y competencia) + `text-embedding-3-large` para embeddings.
- Crear proyecto `azd` (`infra/` Bicep + `azure.yaml`). Reusar patrón del proyecto previo.

### Fase 1 — Provisión de infraestructura (`azd up`)

- Azure AI Foundry hub + project (Cognitive Services account).
- Model deployments: clasificación/borrador, competencia (reasoning), embeddings.
- Azure AI Search (SKU básico) para el índice de reglas.
- Cosmos DB (serverless, API SQL) para casos + auditoría (mock CRM).
- Azure AI Document Intelligence (OCR de adjuntos).
- Blob Storage para adjuntos entrantes (input del OCR).
- Service Bus namespace + queue `pqr-ingesta`.
- Azure Functions (Flex Consumption) + Storage.
- Static Web App (linked backend a Functions).
- Managed Identity + RBAC (Functions → Foundry / Search / Cosmos / Service Bus). Sin KV público.

### Fase 2 — Datos y conocimiento

- Cargar reglas de jurisdicción (seed del prototipo) en AI Search con embeddings (índice vectorial versionado).
- Sembrar casos PQR de ejemplo en Cosmos (migrar seed de index.html).

### Fase 3 — Agente + tools

- Definir el agente RAG en Foundry Agent Service (instrucciones, umbral de confianza, HITL).
- Functions *tools*:
  - `preprocess` → Document Intelligence: OCR de adjuntos desde Blob + normaliza texto (paso previo a classify).
  - `classify` → MAI-1: tipo/tipología/asunto (structured output JSON schema) + confianza.
  - `competence` → AI Search RAG + MAI-DS-R1 (o GPT-4o si no disponible): entidad + regla citada + confianza.
  - `route` → Cosmos: asigna equipo/cola/SLA (mock CRM).
  - `draft` → MAI-1: borrador citado + groundedness.
- Ingesta: Function trigger de Service Bus que arranca el flujo del agente.

### Fase 4 — Integración frontend

- Adaptar `index.html`: reemplazar `localStorage` por llamadas a la API (`fetch` a Functions).
- Mantener búsqueda/filtros/detalle/borrador/auditoría; datos desde Cosmos.
- Auth Entra ID (Static Web App built-in auth) para analistas.

### Fase 5 — Gobierno, evaluación y seguridad

- Foundry evaluations: exactitud de clasificación + groundedness (conjunto dorado anotado por AMV).
- Umbrales de confianza → derivación automática a revisión manual.
- HITL obligatorio antes de enrutar/responder.
- Auditoría integral en Cosmos.
- (Microsoft Purview fuera del MVP; documentado como siguiente paso.)

### Fase 6 — Verificación

- `azd up` sin errores; recursos *healthy*.
- Prueba e2e: encolar PQR con adjunto → OCR → clasificación → competencia con regla citada → enrutado → borrador → aprobación.
- Validar structured outputs y citas.
- Revisar RBAC / Managed Identity (sin secrets en código).
