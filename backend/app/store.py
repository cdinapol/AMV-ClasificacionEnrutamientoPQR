"""Almacenamiento de casos, reglas y auditoría.

Usa Azure Table Storage con Managed Identity cuando STORAGE_ACCOUNT está configurado;
si no, cae a un almacén en memoria (útil para desarrollo local y validación del scaffold).
"""
from __future__ import annotations
import json
from collections import deque
from datetime import datetime, timezone

from . import config
from .models import Caso, Regla, AuditEntry
from .seed import SEED_CASOS, SEED_REGLAS

_PK = "pqr"  # partición única para el MVP


class _MemoryStore:
    def __init__(self) -> None:
        self._casos: dict[str, Caso] = {c.id: c.model_copy(deep=True) for c in SEED_CASOS}
        self._reglas: dict[str, Regla] = {r.id: r.model_copy(deep=True) for r in SEED_REGLAS}
        self._audit: deque[AuditEntry] = deque(maxlen=500)

    # casos
    def list_casos(self) -> list[Caso]:
        return [c.model_copy(deep=True) for c in self._casos.values()]

    def get_caso(self, cid: str) -> Caso | None:
        c = self._casos.get(cid)
        return c.model_copy(deep=True) if c else None

    def upsert_caso(self, caso: Caso) -> Caso:
        self._casos[caso.id] = caso.model_copy(deep=True)
        return caso

    def delete_caso(self, cid: str) -> None:
        self._casos.pop(cid, None)

    # reglas
    def list_reglas(self) -> list[Regla]:
        return [r.model_copy(deep=True) for r in self._reglas.values()]

    def get_regla(self, rid: str) -> Regla | None:
        r = self._reglas.get(rid)
        return r.model_copy(deep=True) if r else None

    def upsert_regla(self, regla: Regla) -> Regla:
        self._reglas[regla.id] = regla.model_copy(deep=True)
        return regla

    def delete_regla(self, rid: str) -> None:
        self._reglas.pop(rid, None)

    # auditoría
    def add_audit(self, entry: AuditEntry) -> None:
        self._audit.appendleft(entry)

    def list_audit(self) -> list[AuditEntry]:
        return list(self._audit)

    # estado completo (para paridad con el modo local)
    def replace_all(self, casos: list[Caso], reglas: list[Regla]) -> None:
        self._casos = {c.id: c.model_copy(deep=True) for c in casos}
        self._reglas = {r.id: r.model_copy(deep=True) for r in reglas}

    def reset(self) -> None:
        self._casos = {c.id: c.model_copy(deep=True) for c in SEED_CASOS}
        self._reglas = {r.id: r.model_copy(deep=True) for r in SEED_REGLAS}
        self._audit.clear()


class _TableStore:
    """Persistencia en Azure Table Storage (identity-based, sin claves)."""

    def __init__(self) -> None:
        from azure.data.tables import TableServiceClient
        from azure.identity import DefaultAzureCredential

        endpoint = f"https://{config.STORAGE_ACCOUNT}.table.core.windows.net"
        self._svc = TableServiceClient(endpoint=endpoint, credential=DefaultAzureCredential())
        self._t_casos = self._svc.create_table_if_not_exists(config.TABLE_CASOS)
        self._t_reglas = self._svc.create_table_if_not_exists(config.TABLE_REGLAS)
        self._t_audit = self._svc.create_table_if_not_exists(config.TABLE_AUDITORIA)
        self._seed_if_empty()

    def _seed_if_empty(self) -> None:
        if not any(True for _ in self._t_casos.list_entities()):
            for c in SEED_CASOS:
                self.upsert_caso(c)
        if not any(True for _ in self._t_reglas.list_entities()):
            for r in SEED_REGLAS:
                self.upsert_regla(r)

    @staticmethod
    def _to_entity(model, key: str) -> dict:
        d = model.model_dump()
        return {"PartitionKey": _PK, "RowKey": key, "payload": json.dumps(d, ensure_ascii=False)}

    # casos
    def list_casos(self) -> list[Caso]:
        return [Caso(**json.loads(e["payload"])) for e in self._t_casos.list_entities()]

    def get_caso(self, cid: str) -> Caso | None:
        from azure.core.exceptions import ResourceNotFoundError
        try:
            e = self._t_casos.get_entity(_PK, cid)
            return Caso(**json.loads(e["payload"]))
        except ResourceNotFoundError:
            return None

    def upsert_caso(self, caso: Caso) -> Caso:
        self._t_casos.upsert_entity(self._to_entity(caso, caso.id))
        return caso

    def delete_caso(self, cid: str) -> None:
        self._t_casos.delete_entity(_PK, cid)

    # reglas
    def list_reglas(self) -> list[Regla]:
        return [Regla(**json.loads(e["payload"])) for e in self._t_reglas.list_entities()]

    def get_regla(self, rid: str) -> Regla | None:
        from azure.core.exceptions import ResourceNotFoundError
        try:
            e = self._t_reglas.get_entity(_PK, rid)
            return Regla(**json.loads(e["payload"]))
        except ResourceNotFoundError:
            return None

    def upsert_regla(self, regla: Regla) -> Regla:
        self._t_reglas.upsert_entity(self._to_entity(regla, regla.id))
        return regla

    def delete_regla(self, rid: str) -> None:
        self._t_reglas.delete_entity(_PK, rid)

    # auditoría
    def add_audit(self, entry: AuditEntry) -> None:
        rk = f"{entry.ts}-{entry.accion}"
        self._t_audit.upsert_entity(self._to_entity(entry, rk))

    def list_audit(self) -> list[AuditEntry]:
        rows = [AuditEntry(**json.loads(e["payload"])) for e in self._t_audit.list_entities()]
        return sorted(rows, key=lambda a: a.ts, reverse=True)[:200]

    # estado completo (para paridad con el modo local)
    def replace_all(self, casos: list[Caso], reglas: list[Regla]) -> None:
        for c in list(self.list_casos()):
            self.delete_caso(c.id)
        for r in list(self.list_reglas()):
            self.delete_regla(r.id)
        for c in casos:
            self.upsert_caso(c)
        for r in reglas:
            self.upsert_regla(r)

    def reset(self) -> None:
        self.replace_all(list(SEED_CASOS), list(SEED_REGLAS))


def _build_store():
    if config.storage_enabled():
        try:
            return _TableStore()
        except Exception as exc:  # degradación controlada si Storage no está accesible
            print(f"[store] Table Storage no disponible ({exc}); usando memoria.")
    return _MemoryStore()


store = _build_store()


def audit(accion: str, caso_id: str = "", detalle: str = "") -> None:
    store.add_audit(AuditEntry(
        ts=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        accion=accion, casoId=caso_id, detalle=detalle,
    ))
