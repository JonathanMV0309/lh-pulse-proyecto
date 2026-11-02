"""CHAIN OF RESPONSIBILITY: las reglas que debe cumplir una meta antes de guardarse.

Problema: una meta se valida en pasos que dependen unos de otros: primero que vengan los datos, luego
que el periodo y el valor tengan sentido, después que la tienda exista y, al final, que no haya otra
meta igual. Un solo método con todos los if crece sin control, y no se puede reutilizar una regla
(la de duplicados solo aplica al crear).

Cada eslabón revisa una regla y, si está bien, pasa al siguiente; el primero que encuentra un
problema corta la cadena con un mensaje claro y el código HTTP que corresponde. La cadena se arma
distinta para crear y para ajustar. Complejidad: el orden de los eslabones importa.
"""
from datetime import date

VALOR_MAXIMO = 10_000_000_000      # 10 mil millones: más que eso es un error de digitación


class ErrorValidacion(Exception):

    def __init__(self, mensaje, campo=None, estado_http=400):
        super().__init__(mensaje)
        self.mensaje, self.campo, self.estado_http = mensaje, campo, estado_http


class Validador:

    def __init__(self):
        self._siguiente = None

    def luego(self, siguiente):
        """Encadena y devuelve el siguiente, para escribir a.luego(b).luego(c)."""
        self._siguiente = siguiente
        return siguiente

    def validar(self, entrada, contexto):
        self.revisar(entrada, contexto)
        if self._siguiente:
            self._siguiente.validar(entrada, contexto)

    def revisar(self, entrada, contexto):
        raise NotImplementedError


class CamposObligatorios(Validador):
    def revisar(self, entrada, contexto):
        nombres = {"tienda_id": "la tienda", "anio": "el año", "mes": "el mes", "valor": "el valor de la meta"}
        for campo, texto in nombres.items():
            if contexto.get("ajuste") and campo in ("tienda_id", "anio", "mes"):
                continue                    # al ajustar solo se cambia el valor y la nota
            if getattr(entrada, campo) is None:
                hay_algo = entrada.crudo.get(campo) not in (None, "")
                raise ErrorValidacion(f"{texto.capitalize()} {'no es un número válido' if hay_algo else 'es obligatorio'}.", campo)


class PeriodoValido(Validador):
    def revisar(self, entrada, contexto):
        if contexto.get("ajuste"):
            return
        if not 1 <= entrada.mes <= 12:
            raise ErrorValidacion("El mes debe estar entre 1 y 12.", "mes")
        hoy = contexto.get("hoy") or date.today()
        if not 2020 <= entrada.anio <= hoy.year + 1:
            raise ErrorValidacion(f"El año debe estar entre 2020 y {hoy.year + 1}.", "anio")
        if (entrada.anio, entrada.mes) < (hoy.year, hoy.month) and not contexto.get("permitir_pasado"):
            raise ErrorValidacion("No se pueden crear metas de meses que ya pasaron.", "mes")


class ValorValido(Validador):
    def revisar(self, entrada, contexto):
        if entrada.valor <= 0:
            raise ErrorValidacion("El valor de la meta debe ser mayor que cero.", "valor")
        if entrada.valor > VALOR_MAXIMO:
            raise ErrorValidacion("El valor de la meta es demasiado alto: revisa los ceros.", "valor")


class TiendaActiva(Validador):
    def __init__(self, tienda_dao):
        super().__init__()
        self.tienda_dao = tienda_dao

    def revisar(self, entrada, contexto):
        if contexto.get("ajuste"):
            return
        if self.tienda_dao.obtener(entrada.tienda_id) is None:
            raise ErrorValidacion("La tienda no existe o no está activa.", "tienda_id", 404)


class SinDuplicado(Validador):
    def __init__(self, meta_dao):
        super().__init__()
        self.meta_dao = meta_dao

    def revisar(self, entrada, contexto):
        existente = self.meta_dao.buscar(entrada.tienda_id, entrada.anio, entrada.mes)
        if existente:
            raise ErrorValidacion(f"Esa tienda ya tiene meta para {entrada.mes:02d}/{entrada.anio} "
                                  f"(id {existente.id}): ajústala en lugar de crear otra.", "mes", 409)


def cadena_para_crear(tienda_dao, meta_dao):
    inicio = CamposObligatorios()
    inicio.luego(PeriodoValido()).luego(ValorValido()).luego(TiendaActiva(tienda_dao)).luego(SinDuplicado(meta_dao))
    return inicio


def cadena_para_ajustar():
    inicio = CamposObligatorios()
    inicio.luego(ValorValido())
    return inicio
