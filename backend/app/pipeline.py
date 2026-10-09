"""Orquestación del flujo de una PQR: clasificar -> competencia (RAG) -> enrutar -> borrador.

Cuando los servicios de Azure AI no están configurados, cada paso cae a una heurística
determinista que reproduce el comportamiento del prototipo (datos del seed), de modo que
el backend es ejecutable y verificable sin nube.
"""
from __future__ import annotations

from . import ai, config
from .models import Caso, Clasificacion, Competencia, Borrador, Analisis
from .search import recuperar_reglas
from .store import store

# Enrutamiento mock (reemplaza al CRM real): entidad/tipología -> equipo + SLA
_RUTEO: dict[str, tuple[str, int]] = {
    "Conducta de intermediario": ("Conducta de Mercado · Intermediarios", 48),
    "Copia de expediente disciplinario": ("Secretaría General", 72),
    "Información general sobre inversión": ("Atención al Inversionista", 24),
}
_RUTEO_EXTERNO = ("Traslado a entidad externa", 48)


def _clasificar(caso: Caso) -> Clasificacion:
    out = ai.clasificar(caso.texto)
    if out:
        return Clasificacion(**out)
    # respaldo: usa valores del seed si existen
    return Clasificacion(
        tipo=caso.tipo or "Consulta",
        tipologia=caso.tipologia or "Sin clasificar",
        asunto=caso.asunto or caso.texto[:80],
        confianza=caso.confClasificacion or 60,
    )


def _competencia(caso: Caso, cls: Clasificacion) -> Competencia:
    reglas = [r.model_dump() for r in store.list_reglas()]
    recuperadas = recuperar_reglas(f"{cls.asunto} {caso.texto}", reglas)
    out = ai.determinar_competencia(caso.texto, recuperadas)
    if out:
        regla = store.get_regla(out.get("reglaId", ""))
        return Competencia(
            entidad=out.get("entidad", ""),
            reglaId=out.get("reglaId", ""),
            reglaTexto=regla.texto if regla else "",
            confianza=int(out.get("confianza", 0)),
        )
    # respaldo: regla top del ranking local
    top = recuperadas[0] if recuperadas else {"id": caso.reglaId, "entidad": caso.entidad, "texto": ""}
    return Competencia(
        entidad=caso.entidad or top.get("entidad", ""),
        reglaId=caso.reglaId or top.get("id", ""),
        reglaTexto=top.get("texto", ""),
        confianza=caso.confCompetencia or 60,
    )


def _enrutar(comp: Competencia, cls: Clasificacion) -> tuple[str, int]:
    if comp.entidad and comp.entidad != "AMV":
        return _RUTEO_EXTERNO
    return _RUTEO.get(cls.tipologia, ("Atención al Inversionista", 48))


def _borrador(caso: Caso, comp: Competencia) -> Borrador:
    regla = store.get_regla(comp.reglaId)
    out = ai.redactar_borrador(caso.texto, comp.entidad, regla.model_dump() if regla else None)
    if out:
        return Borrador(**out)
    citas = [comp.reglaId] if comp.reglaId else []
    return Borrador(
        texto=(
            f"Estimado(a) {caso.remitente or 'ciudadano'}: hemos recibido su "
            f"{(caso.tipo or 'solicitud').lower()} relacionada con «{caso.asunto or comp.reglaId}». "
            f"La entidad competente es {comp.entidad}. Con fundamento en la regla "
            f"{comp.reglaId}, su caso ha sido enrutado para su atención dentro del plazo definido. "
            "Esta es una respuesta preliminar sujeta a revisión."
        ),
        citas=citas,
        groundedness=85,
    )


def analizar(caso: Caso) -> Analisis:
    cls = _clasificar(caso)
    comp = _competencia(caso, cls)
    equipo, sla = _enrutar(comp, cls)
    borrador = _borrador(caso, comp)

    requiere_revision = min(cls.confianza, comp.confianza) < config.CONFIANZA_MIN

    # persistir el estado derivado en el caso
    caso.tipo = cls.tipo
    caso.tipologia = cls.tipologia
    caso.asunto = cls.asunto
    caso.confClasificacion = cls.confianza
    caso.entidad = comp.entidad
    caso.reglaId = comp.reglaId
    caso.confCompetencia = comp.confianza
    caso.equipo = equipo if not requiere_revision else "Pendiente asignación (confianza baja)"
    caso.slaHoras = sla
    caso.estado = "Pendiente revisión" if requiere_revision else "Borrador generado"
    store.upsert_caso(caso)

    return Analisis(
        caso=caso, clasificacion=cls, competencia=comp,
        borrador=borrador, requiereRevision=requiere_revision,
    )
