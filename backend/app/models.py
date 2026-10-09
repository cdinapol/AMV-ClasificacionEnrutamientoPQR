from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field

Tipo = Literal["Queja", "Consulta", "Solicitud"]
Canal = Literal["Correo", "Formulario web", "Otro"]
Estado = Literal[
    "Nuevo", "Clasificado", "Enrutado", "Borrador generado",
    "Pendiente revisión", "Aprobado", "Enviado", "Cerrado",
]


class Regla(BaseModel):
    id: str
    entidad: str
    texto: str
    vigente: bool = True


class Caso(BaseModel):
    id: str
    canal: Canal = "Correo"
    fecha: str = ""
    hora: str = ""
    remitente: str = ""
    texto: str = ""
    tipo: Tipo | None = None
    tipologia: str = ""
    asunto: str = ""
    confClasificacion: int = 0
    entidad: str = ""
    reglaId: str = ""
    confCompetencia: int = 0
    equipo: str = ""
    estado: Estado = "Nuevo"
    slaHoras: int = 48


class Clasificacion(BaseModel):
    tipo: Tipo
    tipologia: str
    asunto: str
    confianza: int = Field(ge=0, le=100)


class Competencia(BaseModel):
    entidad: str
    reglaId: str
    reglaTexto: str = ""
    confianza: int = Field(ge=0, le=100)


class Borrador(BaseModel):
    texto: str
    citas: list[str] = []
    groundedness: int = Field(ge=0, le=100, default=0)


class Analisis(BaseModel):
    caso: Caso
    clasificacion: Clasificacion
    competencia: Competencia
    borrador: Borrador
    requiereRevision: bool


class Decision(BaseModel):
    estado: Estado
    revisadoPor: str = "analista"
    comentario: str = ""


class AuditEntry(BaseModel):
    ts: str
    accion: str
    casoId: str = ""
    detalle: str = ""
