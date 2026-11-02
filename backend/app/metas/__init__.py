"""Metas mensuales de tienda (Sprint 2: HU-05, HU-06 y HU-07).

Mapa de capas y patrones (cada archivo explica el suyo):

    pantallas (templates/metas_tienda)  ->  api.py (controlador REST, solo HTTP)
        -> servicio.py ......... FACADE: una sola puerta para todo lo de metas
             -> validaciones.py  CHAIN OF RESPONSIBILITY: reglas de una meta, una tras otra
             -> semaforo.py .... STRATEGY: cómo se califica el cumplimiento
             -> builder.py ..... BUILDER: arma el resumen de cada tienda
             -> eventos.py ..... OBSERVER: al guardar o borrar, avisa (historial y registro)
             -> fabrica.py ..... ABSTRACT FACTORY: crea la familia de DAO (base de datos o memoria)
                  -> dao/ ...... DAO: única capa que toca la base de datos
                  -> adaptadores.py  ADAPTER: la tabla heredada «compliance» como VentaDAO
                  -> decoradores.py  DECORATOR: caché sobre el DAO de tiendas
             -> configuracion.py SINGLETON: una sola configuración leída del .env
        -> dto.py .............. DTO: lo que entra y sale de la API
"""
