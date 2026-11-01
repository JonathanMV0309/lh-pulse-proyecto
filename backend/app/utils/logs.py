"""
Mensajes de depuración de L&H PULSE.

Antes el código usaba print() en cada ruta y servicio, lo que llenaba la
consola y hacía más lento cada clic. Ahora esos mensajes pasan por
log_debug(), que NO imprime nada a menos que se active el modo depuración.

Para verlos otra vez (solo cuando estés revisando un problema):

    En PowerShell, antes de iniciar el servidor:
        $env:LH_DEBUG = "1"

    O agrega esta línea al archivo .env:
        LH_DEBUG=1

Los mensajes de error (los que están dentro de un "except") siguen
mostrándose siempre con print().
"""
import os
import sys

_ACTIVO = os.getenv("LH_DEBUG", "").strip().lower() in ("1", "true", "si", "sí", "yes")


def depuracion_activa():
    return _ACTIVO


def log_debug(*args, sep=" ", end="\n", file=None, flush=False):
    """Igual que print(), pero solo imprime si LH_DEBUG=1."""
    if not _ACTIVO:
        return
    print(*args, sep=sep, end=end, file=file or sys.stdout, flush=flush)
