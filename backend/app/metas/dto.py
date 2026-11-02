"""DTO (Data Transfer Object): lo que entra y sale de la API de metas.

No son las entidades de la base de datos:
- MetaEntradaDTO trae solo lo que la pantalla puede mandar (no trae id, fechas ni quién la cambió) y
  guarda los valores tal como llegaron, para que las validaciones digan qué está mal.
- MetaDTO y TiendaMetaDTO salen con datos que no están en la tabla metas_tienda: el código y nombre
  de la tienda, la venta del mes, el cumplimiento y el semáforo.
Así la pantalla no depende de cómo están guardadas las tablas, y la API nunca expone columnas internas.
"""
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Optional


def _entero(valor):
    try:
        if isinstance(valor, bool):
            return None
        return int(str(valor).strip())
    except (TypeError, ValueError):
        return None


def _numero(valor):
    try:
        if isinstance(valor, bool):
            return None
        return float(str(valor).replace(" ", "").replace("$", "").replace(".", "").replace(",", "."))
    except (TypeError, ValueError):
        return None


@dataclass
class MetaEntradaDTO:
    """Datos para crear o ajustar una meta (formulario de HU-06)."""
    tienda_id: Optional[int]
    anio: Optional[int]
    mes: Optional[int]
    valor: Optional[float]
    nota: str = ""
    crudo: dict = field(default_factory=dict, repr=False)

    @classmethod
    def desde_json(cls, datos):
        datos = datos if isinstance(datos, dict) else {}
        valor = datos.get("valor")
        return cls(
            tienda_id=_entero(datos.get("tienda_id")),
            anio=_entero(datos.get("anio")),
            mes=_entero(datos.get("mes")),
            valor=float(valor) if isinstance(valor, (int, float)) and not isinstance(valor, bool) else _numero(valor),
            nota=str(datos.get("nota") or "").strip()[:255],
            crudo=dict(datos),
        )


@dataclass
class TiendaDTO:
    id: int
    codigo: str
    nombre: str
    ciudad: str = ""

    def a_dict(self):
        return asdict(self)


@dataclass
class MetaDTO:
    id: int
    tienda_id: int
    anio: int
    mes: int
    valor: float
    nota: str = ""
    actualizado_por: str = ""
    actualizado_en: Optional[datetime] = None
    tienda_codigo: str = ""
    tienda_nombre: str = ""

    def a_dict(self):
        d = asdict(self)
        d["actualizado_en"] = self.actualizado_en.isoformat(timespec="minutes") if self.actualizado_en else None
        return d


@dataclass
class VentaMesDTO:
    """Venta acumulada de una tienda en un mes, hasta el día de corte del último informe."""
    valor: float
    dia_corte: int


@dataclass
class TiendaMetaDTO:
    """Una fila de la consulta de HU-05: la tienda con su meta, su venta y cómo va."""
    tienda_id: int
    tienda_codigo: str
    tienda_nombre: str
    ciudad: str
    anio: int
    mes: int
    meta_id: Optional[int]
    meta: Optional[float]
    venta: float
    dia_corte: Optional[int]
    meta_al_corte: Optional[float]
    cumplimiento_pct: Optional[float]
    semaforo: str
    estado: str

    def a_dict(self):
        return asdict(self)


@dataclass
class HistorialDTO:
    accion: str
    valor_anterior: Optional[float]
    valor_nuevo: Optional[float]
    usuario: str
    fecha: datetime

    def a_dict(self):
        d = asdict(self)
        d["fecha"] = self.fecha.isoformat(timespec="minutes") if self.fecha else None
        return d
