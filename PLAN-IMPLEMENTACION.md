# Plan de implementación en Azure — Clasificación y Enrutamiento de PQR (AMV)

> MVP funcional end-to-end de **una ruta** basado en la arquitectura de referencia de
> [ARQUITECTURA.md](ARQUITECTURA.md). Lleva el prototipo estático ([index.html](index.html),
> hoy con `localStorage`) a un despliegue real en Azure.

## Contexto

- **Repo:** AMV-ClasificacionEnrutamientoPQR (hoy solo prototipo estático: ARQUITECTURA.md, FUNCIONAMIENTO.md, index.html con localStorage).
- **Suscripción destino:** `bd70db0b-5ee5-488d-89c8-83cdd803614a` (entorno gobernado `ME-MngEnvMCAP008935`).
- **Región:** `eastus2`.
- **Resource group nuevo:** `rg-amv-pqr` (prefijo de recursos `amv-pqr`). No se reutiliza `rg-amv-vigilancia-demo`.

## Verificación previa (2026-10-09, `az` sobre la suscripción)

| Elemento | Resultado | Impacto |
|---|---|---|
| Acceso a la suscripción | OK (`ME-MngEnvMCAP008935-cdinapol-1`, tenant `8d734a5f-…`) | — |
| `MAI-1` en catálogo `eastus2` | **NO existe** | Usar **MAI-Thinking-1** (GlobalStandard, cuota 500, usados 20) |
| `MAI-DS-R1` | No aparece en la lista de modelos, pero la cuota `AIServices.GlobalStandard.MAI-DS-R1` = 1000 existe | Intentar despliegue; si falla → MAI-Thinking-1 |
| `gpt-4o` (2024-11-20) | Standard cuota 150 (usados 20); GlobalStandard 1350 (usados 730) | Fallback / tareas de clasificación estructurada |
| `text-embedding-3-large` | Standard cuota 350 (usados 50) | Embeddings de reglas |
| `gpt-4.1`, `gpt-4.1-mini` | Disponibles (Standard) | Alternativa para clasificación barata |
| Azure Policy visible | Solo asignaciones Defender/ASC en la suscripción; las restricciones de KV/Cosmos vienen de la gobernanza MCAP (verificadas en proyectos previos) | Ver gotchas |
| Recursos existentes reutilizables | `cog-amv-vig-demo` ya tiene gpt-4o, embeddings y MAI-Thinking-1 (otro proyecto) | No compartir; crear cuenta propia para aislar cuota y RBAC |

## Decisiones

- **Alcance:** MVP funcional end-to-end de UNA ruta (ingesta → OCR → clasificación MAI-1 → competencia RAG/MAI-DS-R1 → borrador → revisión humana).
- **Frontend:** desplegar `index.html` tal cual como Azure Static Web App, conectado a una API real.
- **Backend:** Foundry Agent Service como orquestador principal; Azure Functions solo como *tools*.
- **Modelos (ajustado tras la verificación):**
  - Clasificación y borrador: **MAI-Thinking-1** (MAI-1 no existe en el catálogo). Como la clasificación requiere JSON estricto y alto volumen, se evalúa en paralelo contra **gpt-4o** (structured outputs) y se elige con el conjunto dorado.
  - Competencia (RAG): **MAI-DS-R1** si el despliegue funciona; si no, **MAI-Thinking-1**.
  - Embeddings: `text-embedding-3-large`.
  - Cada tool usa una variable de entorno de *deployment name* para poder cambiar de modelo sin tocar código.
- **CRM / persistencia:** mock **sin Cosmos DB** (en esta suscripción la política fuerza `publicNetworkAccess=Disabled` en Cosmos y lo deja inutilizable sin VNet + private endpoint). Se usa **Azure Table Storage** (casos, estado, auditoría) + Blob (adjuntos), ambos con Managed Identity. Cosmos + private endpoint queda como opción v2.
- **OCR (Document Intelligence):** **INCLUIDO** en el MVP; preprocesa adjuntos antes de clasificar.
- **Ingesta MVP:** solo Service Bus + un canal web/API. Correo (Graph/Exchange) queda para v2.

## Gotchas del entorno gobernado (verificados en proyectos previos)

- Azure Policy fuerza Key Vault `publicNetworkAccess=Disabled` → **NO** usar KV con acceso público. Usar **Managed Identity** + secrets nativos del recurso.
- Cosmos DB: `publicNetworkAccess=Disabled` forzado por policy (ignora `--public-network-access ENABLED`) → no usarlo en el MVP.
- Azure AI Services: `disableLocalAuth=true` → **sin API keys**, todo por Entra ID / Managed Identity (roles `Cognitive Services OpenAI User` y `Cognitive Services User`).
- Azure AI Search sí admite keys (`apiKeyOnly`); preferible RBAC (`Search Index Data Reader/Contributor`) con MI y guardar la query key solo si hace falta como secret nativo.
- Storage: puede venir con shared key deshabilitada → usar `DefaultAzureCredential` en todo y `AzureWebJobsStorage__accountName` (identity-based) en Functions.
- Python local es 3.14: fijar `pydantic>=2.12` y `httpx<0.28` si se usa `openai` 1.54; en Functions usar runtime Python 3.11/3.12.
- Modelo `MAI-1` plano no existe; el identificador real es `MAI-Thinking-1` (endpoint `https://<cuenta>.services.ai.azure.com/models`, paquete `azure-ai-inference`).
- Foundry agent hosted: setear `AZURE_AI_MODEL_DEPLOYMENT_NAME` o crashea *"Model is required"*.
- Sin Docker local → si se usa contenedor, `azd` con `remoteBuild:true` (ACR Tasks). Azure Functions no lo requiere.

## Arquitectura MVP (subconjunto de la de referencia)

```
Static Web App (index.html)
  → API (Functions)
    → Foundry Agent Service (orquestador RAG)
       ├─ tool preprocess  → Document Intelligence (OCR de adjuntos desde Blob)
       ├─ tool classify    → MAI-Thinking-1 / gpt-4o (tipo/tipología/asunto, structured output)
       ├─ tool competence  → AI Search (RAG reglas) + MAI-DS-R1 (o MAI-Thinking-1)
       ├─ tool route       → Table Storage (mock CRM: equipo/cola/SLA)
       └─ tool draft       → MAI-Thinking-1 (borrador citado + groundedness)
```

- **Service Bus** (`pqr-ingesta`) desacopla la ingesta.
- **Table Storage** guarda casos, estado y auditoría (reemplaza a Cosmos por la política de red).
- **AI Search** aloja el índice vectorial de reglas de jurisdicción.
- **Foundry evaluations** mide groundedness / exactitud.

## Fases

### Fase 0 — Prerrequisitos y verificación (bloquea todo)

- ✅ Acceso a la suscripción y región `eastus2` confirmados; catálogo y cuotas verificados (ver tabla arriba).
- Pendiente: probar el despliegue de **MAI-DS-R1** en la cuenta nueva (`az cognitiveservices account deployment create`); si falla, fijar MAI-Thinking-1.
- Pendiente: decidir residencia de datos (PQR contienen datos personales; `eastus2` vs. región LATAM) con el área legal de AMV.
- Crear proyecto `azd` (`infra/` Bicep + `azure.yaml`, env `amv-pqr`, `AZURE_SUBSCRIPTION_ID=bd70db0b-…`, `AZURE_LOCATION=eastus2`). Reusar patrón de `anthropic-mcp-foundry`.

### Fase 1 — Provisión de infraestructura (`azd up`)

- Resource group `rg-amv-pqr` (eastus2).
- Azure AI Foundry: cuenta `AIServices` (`cog-amv-pqr`, `disableLocalAuth=true`) + project.
- Model deployments: `mai-thinking-1` (GlobalStandard, ~20), `mai-ds-r1` (si disponible), `gpt-4o` (Standard ~20, comparación/fallback), `text-embedding-3-large` (Standard ~50).
- Azure AI Search (SKU Basic) para el índice de reglas, con RBAC por MI.
- Storage account (Tables `casos`, `auditoria`, `reglas`; Blob `adjuntos`) con shared key deshabilitada.
- Azure AI Document Intelligence (OCR; puede ser la misma cuenta AIServices) para adjuntos en Blob.
- Service Bus namespace + queue `pqr-ingesta`.
- Azure Functions (Flex Consumption) + Storage.
- Static Web App (linked backend a Functions).
- Managed Identity + RBAC (Functions → `Cognitive Services OpenAI User` + `Cognitive Services User` en la cuenta AI, `Search Index Data Contributor`, `Storage Table Data Contributor`, `Storage Blob Data Contributor`, `Azure Service Bus Data Receiver/Sender`). Sin KV público.
- Log Analytics + Application Insights (trazas de agente, latencia y costo por PQR).
- Plan B de cómputo: si Functions Flex Consumption choca con la gobernanza (storage identity-based), usar **Azure Container Apps** + `az acr build` (patrón ya probado en `AMV-VigilanciadeMercado`).

### Fase 2 — Datos y conocimiento

- Cargar reglas de jurisdicción (seed del prototipo) en AI Search con embeddings (índice vectorial versionado).
- Sembrar casos PQR de ejemplo en Table Storage (migrar seed de index.html).

### Fase 3 — Agente + tools

- Definir el agente RAG en Foundry Agent Service (instrucciones, umbral de confianza, HITL).
- Functions *tools*:
  - `preprocess` → Document Intelligence: OCR de adjuntos desde Blob + normaliza texto (paso previo a classify).
  - `classify` → MAI-Thinking-1 (o gpt-4o): tipo/tipología/asunto (structured output JSON schema) + confianza.
  - `competence` → AI Search RAG + MAI-DS-R1 (o MAI-Thinking-1 si no disponible): entidad + regla citada + confianza.
  - `route` → Table Storage: asigna equipo/cola/SLA (mock CRM).
  - `draft` → MAI-Thinking-1: borrador citado + groundedness.
- Ingesta: Function trigger de Service Bus que arranca el flujo del agente.

### Fase 4 — Integración frontend

- Adaptar `index.html`: reemplazar `localStorage` por llamadas a la API (`fetch` a Functions).
- Mantener búsqueda/filtros/detalle/borrador/auditoría; datos desde la API (Table Storage).
- Auth Entra ID (Static Web App built-in auth) para analistas.

### Fase 5 — Gobierno, evaluación y seguridad

- Foundry evaluations: exactitud de clasificación + groundedness (conjunto dorado anotado por AMV).
- Umbrales de confianza → derivación automática a revisión manual.
- HITL obligatorio antes de enrutar/responder.
- Auditoría integral en Table Storage (tabla `auditoria`, append-only).
- (Microsoft Purview fuera del MVP; documentado como siguiente paso.)

### Fase 6 — Verificación

- `azd up` sin errores; recursos *healthy*.
- Prueba e2e: encolar PQR con adjunto → OCR → clasificación → competencia con regla citada → enrutado → borrador → aprobación.
- Validar structured outputs y citas.
- Revisar RBAC / Managed Identity (sin secrets en código).

## Riesgos abiertos

| Riesgo | Mitigación |
|---|---|
| MAI-1 / MAI-DS-R1 no disponibles como se nombran en el documento fuente | Deployment names parametrizados; fallback documentado a MAI-Thinking-1 / gpt-4o |
| Competencia = decisión de mayor riesgo | Conjunto dorado de AMV + umbral de confianza + HITL antes de enrutar |
| Datos personales en PQR y residencia de datos | Decisión legal previa; Purview en v2; sin PII en logs |
| Políticas MCAP bloquean recursos (KV, Cosmos, posiblemente otros) | Todo por MI + red pública de servicios permitidos; Plan B ACA |
| Cuota compartida con otros proyectos de la suscripción (gpt-4o GlobalStandard 730/1350 usados) | Usar Standard dedicado y monitorear uso |

## Orden de ejecución sugerido

1. Fase 0 → 1: `azd provision` (Bicep) y validación de deployments.
2. Fase 2: índice de reglas + seed.
3. Fase 3: tools + agente; prueba por consola (sin UI).
4. Fase 4: conectar `index.html` a la API y desplegar a Static Web App.
5. Fase 5 → 6: evaluaciones, umbrales, prueba e2e y cierre.
