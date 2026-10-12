# Diagrama de Azure — artefactos desplegados (AMV · Clasificación y Enrutamiento de PQR)

> Grupo de recursos **`rg-amv-pqr`** · Región **East US 2** (AI Search en **East US**) ·
> Suscripción `bd70db0b-5ee5-488d-89c8-83cdd803614a`.
> Estado verificado el 2026-10-12 con `az resource list`.

## Arquitectura desplegada

```mermaid
flowchart TB
    user(["👤 Analista / revisor<br/>(navegador)"])

    subgraph RG["Resource group · rg-amv-pqr (East US 2)"]
        direction TB

        subgraph FRONT["Frontend"]
            SWA["🌐 Static Web App<br/>amvpqr-web-…<br/><small>index.html · modo live/demo</small>"]
        end

        subgraph COMPUTE["Cómputo (backend)"]
            CAE["📦 Container Apps Environment<br/>amvpqr-cae-…"]
            ACA["🚀 Container App · API FastAPI<br/>amvpqr-api-…<br/><small>pipeline PQR · 1 réplica</small>"]
            ACR["📥 Container Registry<br/>amvpqracr…<br/><small>imagen del backend</small>"]
            CAE --- ACA
            ACR -. pull imagen .-> ACA
        end

        MI["🔑 Managed Identity (user-assigned)<br/>amvpqr-id-…<br/><small>AAD · sin claves</small>"]

        subgraph AI["Azure AI"]
            COG["🧠 Azure AI Services (Foundry)<br/>amvpqr-ai-…"]
            M1["gpt-4o · clasificación"]
            M2["MAI-Thinking-1 · competencia + borrador"]
            M3["text-embedding-3-large"]
            COG --- M1
            COG --- M2
            COG --- M3
            SRCH["🔎 Azure AI Search<br/>amvpqr-srch-…<br/><small>índice reglas-idx (RAG)</small>"]
        end

        subgraph DATA["Datos / mensajería (provisionado)"]
            STG["💾 Storage Account<br/>amvpqrst…<br/><small>Tables/Blob · bloqueado por política</small>"]
            EG["⚡ Event Grid System Topic<br/><small>del Storage</small>"]
            SB["📨 Service Bus<br/>amvpqr-sb-…<br/><small>cola pqr-ingesta (v2)</small>"]
            STG -. eventos .-> EG
        end

        subgraph OBS["Observabilidad"]
            APPI["📈 Application Insights<br/>amvpqr-appi-…"]
            LOGS["📊 Log Analytics<br/>amvpqr-logs-…"]
            APPI --- LOGS
        end
    end

    user -->|HTTPS| SWA
    SWA -->|fetch /api| ACA

    ACA -->|clasifica| M1
    ACA -->|competencia + borrador| M2
    ACA -->|embeddings| M3
    ACA -->|RAG reglas| SRCH
    ACA -. in-memory fallback .-> STG

    ACA -. usa .-> MI
    MI -->|Cognitive Services OpenAI User| COG
    MI -->|Search Index/Service Contributor| SRCH
    MI -->|AcrPull| ACR
    MI -->|Table/Blob Data Contributor| STG
    MI -->|Service Bus Data Sender/Receiver| SB

    ACA -->|telemetría| APPI

    classDef active fill:#cff3e9,stroke:#1f9d77,stroke-width:2px,color:#0b3d2e;
    classDef infra fill:#dceefb,stroke:#2e75b6,stroke-width:1.5px,color:#143a5a;
    classDef idle fill:#f1efea,stroke:#8a8474,stroke-width:1.5px,color:#4a4433;
    classDef gov fill:#e5dff5,stroke:#6a4fb6,stroke-width:1.5px,color:#3b2a63;

    class SWA,ACA,COG,M1,M2,M3,SRCH active;
    class CAE,ACR,APPI,LOGS infra;
    class STG,EG,SB idle;
    class MI gov;
```

**Leyenda de color**

| Color | Significado |
|---|---|
| 🟢 Verde | En uso activo en el flujo de la PQR (frontend, backend, modelos, búsqueda) |
| 🔵 Azul | Infraestructura de soporte (entorno ACA, registry, observabilidad) |
| 🟣 Morado | Identidad y seguridad (Managed Identity + RBAC, sin claves) |
| ⚪ Gris | Provisionado pero **no** en el camino activo (Storage bloqueado por política → el backend usa memoria; Service Bus y Event Grid quedan para v2) |

## Mapeo recurso → función

| Recurso Azure | Nombre | Rol en la app |
|---|---|---|
| Static Web App | `amvpqr-web-…` | Sirve `index.html` (modo live o `?demo=1`) |
| Container Apps Environment | `amvpqr-cae-…` | Entorno de ejecución del backend |
| Container App | `amvpqr-api-…` | API FastAPI: orquesta clasificar → competencia (RAG) → enrutar → borrador |
| Container Registry | `amvpqracr…` | Imagen del backend (build remoto, sin Docker local) |
| Managed Identity | `amvpqr-id-…` | Autenticación AAD a todos los servicios (sin claves) |
| Azure AI Services (Foundry) | `amvpqr-ai-…` | Despliegues `gpt-4o`, `MAI-Thinking-1`, `text-embedding-3-large` |
| Azure AI Search | `amvpqr-srch-…` | Índice `reglas-idx` para el RAG de competencia |
| Storage Account | `amvpqrst…` | Tables/Blob previstos; **bloqueado por política** (public access disabled) → backend en memoria |
| Event Grid System Topic | (del storage) | Eventos del Storage (creado automáticamente) |
| Service Bus | `amvpqr-sb-…` | Cola `pqr-ingesta` para ingesta desacoplada (v2) |
| Application Insights | `amvpqr-appi-…` | Telemetría/trazas del backend |
| Log Analytics | `amvpqr-logs-…` | Backend de logs (ACA + App Insights) |

> **Nota de gobernanza:** la política MCAP fuerza `publicNetworkAccess=Disabled` en el Storage,
> por lo que el Container App (sin VNet) no lo alcanza y el backend persiste en memoria. La
> persistencia duradera requeriría **VNet + Private Endpoint** (v2).
