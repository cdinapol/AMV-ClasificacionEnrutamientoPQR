from __future__ import annotations
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from . import config, pipeline
from .models import Caso, Regla, Decision
from .store import store, audit

app = FastAPI(title="AMV · Clasificación y Enrutamiento de PQR", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in config.CORS_ORIGINS.split(",")],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "ai": config.ai_enabled(),
        "storage": config.storage_enabled(),
        "search": config.search_enabled(),
        "store": type(store).__name__,
    }


@app.get("/api/kpis")
def kpis() -> dict:
    casos = store.list_casos()
    por_estado: dict[str, int] = {}
    por_tipo: dict[str, int] = {}
    baja_confianza = 0
    for c in casos:
        por_estado[c.estado] = por_estado.get(c.estado, 0) + 1
        if c.tipo:
            por_tipo[c.tipo] = por_tipo.get(c.tipo, 0) + 1
        if min(c.confClasificacion or 0, c.confCompetencia or 0) < config.CONFIANZA_MIN:
            baja_confianza += 1
    return {
        "total": len(casos),
        "porEstado": por_estado,
        "porTipo": por_tipo,
        "bajaConfianza": baja_confianza,
        "umbral": config.CONFIANZA_MIN,
    }


@app.get("/api/casos")
def list_casos(tipo: str | None = None, canal: str | None = None,
               estado: str | None = None, q: str | None = None) -> list[Caso]:
    casos = store.list_casos()
    if tipo:
        casos = [c for c in casos if c.tipo == tipo]
    if canal:
        casos = [c for c in casos if c.canal == canal]
    if estado:
        casos = [c for c in casos if c.estado == estado]
    if q:
        ql = q.lower()
        casos = [c for c in casos if ql in (c.texto + c.asunto + c.id).lower()]
    audit("busqueda", detalle=f"tipo={tipo} canal={canal} estado={estado} q={q}")
    return casos


@app.get("/api/casos/{caso_id}")
def get_caso(caso_id: str) -> Caso:
    c = store.get_caso(caso_id)
    if not c:
        raise HTTPException(404, "Caso no encontrado")
    audit("apertura", caso_id)
    return c


@app.post("/api/casos")
def crear_caso(caso: Caso) -> Caso:
    store.upsert_caso(caso)
    audit("alta_caso", caso.id)
    return caso


@app.delete("/api/casos/{caso_id}")
def borrar_caso(caso_id: str) -> dict:
    store.delete_caso(caso_id)
    audit("baja_caso", caso_id)
    return {"ok": True}


@app.post("/api/casos/{caso_id}/analizar")
def analizar(caso_id: str) -> dict:
    c = store.get_caso(caso_id)
    if not c:
        raise HTTPException(404, "Caso no encontrado")
    res = pipeline.analizar(c)
    audit("analisis", caso_id,
          f"clf={res.clasificacion.confianza} comp={res.competencia.confianza} "
          f"revision={res.requiereRevision}")
    return res.model_dump()


@app.post("/api/casos/{caso_id}/decision")
def decision(caso_id: str, dec: Decision) -> Caso:
    c = store.get_caso(caso_id)
    if not c:
        raise HTTPException(404, "Caso no encontrado")
    c.estado = dec.estado
    store.upsert_caso(c)
    audit("decision", caso_id, f"{dec.estado} por {dec.revisadoPor}: {dec.comentario}")
    return c


@app.get("/api/reglas")
def list_reglas() -> list[Regla]:
    return store.list_reglas()


@app.post("/api/reglas")
def crear_regla(regla: Regla) -> Regla:
    store.upsert_regla(regla)
    audit("alta_regla", detalle=regla.id)
    return regla


@app.delete("/api/reglas/{regla_id}")
def borrar_regla(regla_id: str) -> dict:
    store.delete_regla(regla_id)
    audit("baja_regla", detalle=regla_id)
    return {"ok": True}


@app.get("/api/audit")
def list_audit() -> list[dict]:
    return [a.model_dump() for a in store.list_audit()]
