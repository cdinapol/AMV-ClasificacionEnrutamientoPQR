"""Datos semilla migrados del prototipo index.html (localStorage -> backend)."""
from .models import Caso, Regla

SEED_REGLAS: list[Regla] = [
    Regla(id="REG-002", entidad="AMV", texto="Registro Nacional de Profesionales del Mercado de Valores — verificación de autorización de asesores y operadores."),
    Regla(id="REG-014", entidad="AMV", texto="Reglamento AMV, Libro III — Conductas de intermediarios de valores: deber de información y mejor ejecución."),
    Regla(id="REG-021", entidad="AMV", texto="Reglamento de Procedimiento Sancionatorio AMV — acceso y copia de expedientes disciplinarios por parte interesada."),
    Regla(id="REG-033", entidad="Superintendencia Financiera de Colombia", texto="Régimen de protección al consumidor financiero — reclamaciones sobre productos y servicios de entidades vigiladas por la SFC."),
    Regla(id="REG-041", entidad="Bolsa de Valores de Colombia (bvc)", texto="Reglamento de la Bolsa de Valores de Colombia — funcionamiento operativo de la plataforma de negociación."),
]

SEED_CASOS: list[Caso] = [
    Caso(
        id="PQR-2026-0143", canal="Correo", fecha="16/09/2026", hora="09:12",
        remitente="Inversionista persona natural",
        texto="Escribo para quejarme porque mi comisionista ejecutó una operación de compra de acciones sin explicarme previamente el riesgo ni las condiciones de la operación, a pesar de haberlo solicitado por escrito.",
        tipo="Queja", tipologia="Conducta de intermediario",
        asunto="Posible incumplimiento del deber de información previo a una operación",
        confClasificacion=91, entidad="AMV", reglaId="REG-014", confCompetencia=94,
        equipo="Conducta de Mercado · Intermediarios", estado="Enrutado", slaHoras=48,
    ),
    Caso(
        id="PQR-2026-0144", canal="Formulario web", fecha="16/09/2026", hora="10:35",
        remitente="Ciudadano",
        texto="Quisiera saber cómo puedo verificar si un asesor de inversión que me contactó por redes sociales está realmente autorizado para operar en el mercado de valores.",
        tipo="Consulta", tipologia="Información general sobre inversión",
        asunto="Verificación de autorización de un asesor de inversión",
        confClasificacion=88, entidad="AMV", reglaId="REG-002", confCompetencia=90,
        equipo="Atención al Inversionista", estado="Borrador generado", slaHoras=24,
    ),
    Caso(
        id="PQR-2026-0145", canal="Correo", fecha="15/09/2026", hora="16:04",
        remitente="Apoderado de intermediario sancionado",
        texto="Solicito copia completa del expediente disciplinario y de la resolución sancionatoria proferida contra mi representado, para efectos de interponer los recursos de ley.",
        tipo="Solicitud", tipologia="Copia de expediente disciplinario",
        asunto="Solicitud de copia de resolución sancionatoria",
        confClasificacion=95, entidad="AMV", reglaId="REG-021", confCompetencia=97,
        equipo="Secretaría General", estado="Pendiente revisión", slaHoras=72,
    ),
    Caso(
        id="PQR-2026-0146", canal="Formulario web", fecha="14/09/2026", hora="08:47",
        remitente="Cliente de entidad bancaria",
        texto="Me están cobrando una cuota de manejo que nunca autoricé en mi cuenta de ahorros y el banco no me ha dado respuesta clara.",
        tipo="Queja", tipologia="Producto o servicio bancario",
        asunto="Cobro indebido en cuenta de ahorros",
        confClasificacion=82, entidad="Superintendencia Financiera de Colombia", reglaId="REG-033", confCompetencia=89,
        equipo="Traslado a entidad externa", estado="Cerrado", slaHoras=48,
    ),
    Caso(
        id="PQR-2026-0147", canal="Otro", fecha="16/09/2026", hora="13:58",
        remitente="Cliente (canal de chat)",
        texto="Un cliente me comentó que un operador estaría inflando artificialmente el precio de una acción antes de la apertura, pero no tengo más detalles ni evidencia.",
        tipo="Queja", tipologia="Conducta de intermediario",
        asunto="Presunta manipulación de precio reportada por un cliente",
        confClasificacion=68, entidad="AMV", reglaId="REG-014", confCompetencia=59,
        equipo="Pendiente asignación (confianza baja)", estado="Nuevo", slaHoras=24,
    ),
]
