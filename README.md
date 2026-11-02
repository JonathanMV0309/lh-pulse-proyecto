# L&H PULSE — Proyecto de Ingeniería de Software I (ETITC)

L&H PULSE es la herramienta de gestión comercial de las tiendas de L&H. Muestra el cumplimiento de
metas, los rankings de tiendas y asesoras, y permite cargar los informes de ventas en Excel.

**Equipo:** Santiago León · Camilo Torres · Thaira Hernández · Jonathan Monroy

> Este repositorio es la versión académica del proyecto. No contiene datos reales: no hay ventas,
> correos, contraseñas ni la dirección del servidor. Todos los datos los crea la semilla y son inventados.

## Ejecutar con Docker (API + PostgreSQL)

```bash
cp .env.example .env          # y completar SECRET_KEY, DB_USER, DB_PASSWORD y SEMILLA_ADMIN_CLAVE
docker compose up -d --build
docker compose ps             # db (healthy) y api (healthy)
```

- La aplicación queda en http://127.0.0.1:5075. Se entra con `SEMILLA_ADMIN_CORREO` y `SEMILLA_ADMIN_CLAVE` del `.env`.
- Al arrancar, la API crea las tablas. Si la base está vacía, siembra 10 tiendas de ejemplo con sus ventas y metas del mes.
- Los datos viven en el volumen `lhpulse_datos`, así que sobreviven a `docker compose down`.
  `docker compose down -v` los borra.
- La base no publica puertos: solo la API llega a ella, por la red interna de Docker.
- Las credenciales salen del `.env`, que está en `.gitignore`.

## Sprint 2: metas mensuales de las tiendas

| Historia | Pantalla | API |
|---|---|---|
| HU-05 Consultar las metas del mes con venta, cumplimiento y semáforo | `/metas-tienda/` | `GET /api/v1/metas?anio=&mes=` |
| HU-06 Crear, ajustar o eliminar la meta mensual de una tienda | `/metas-tienda/nueva` y `/metas-tienda/<id>/editar` | `POST /api/v1/metas`, `PUT` y `DELETE /api/v1/metas/<id>` |
| HU-07 Ver el historial de cambios de una meta | botón «Historial» | `GET /api/v1/metas/<id>/historial` |

Todo el módulo está en `backend/app/metas/`. Cada archivo explica qué patrón implementa y por qué:

| Tipo | Patrón | Archivo |
|---|---|---|
| Obligatorio | DAO | `dao/base.py`, `dao/sqlalchemy_dao.py`, `dao/memoria_dao.py` |
| Si aplica | DTO | `dto.py` |
| Creacional | Singleton | `configuracion.py` |
| Creacional | Abstract Factory | `fabrica.py` |
| Creacional | Builder | `builder.py` |
| Estructural | Facade | `servicio.py` |
| Estructural | Adapter | `adaptadores.py` |
| Estructural | Decorator | `decoradores.py` |
| Comportamiento | Strategy | `semaforo.py` |
| Comportamiento | Observer | `eventos.py` |
| Comportamiento | Chain of Responsibility | `validaciones.py` |

Las capas van así: pantallas → `api.py` (solo HTTP) → `servicio.py` (Facade) → DAO → PostgreSQL.
Ni las pantallas ni la API hacen consultas a la base de datos.

### Probar la API (Postman, Thunder Client o curl)

1. `POST /api/auth/login` con `{"correo": "...", "password": "..."}`. Guarda la cookie de sesión.
2. `GET /api/v1/metas?anio=2026&mes=11`
3. `POST /api/v1/metas` con `{"tienda_id": 9, "anio": 2026, "mes": 11, "valor": 50000000, "nota": "..."}`

Los errores responden en JSON: `{"ok": false, "error": "...", "campo": "..."}`. Los códigos son:

| Código | Cuándo |
|---|---|
| 400 | Dato inválido |
| 401 | Sin sesión |
| 403 | No es administración |
| 404 | No existe |
| 409 | Meta duplicada |
| 503 | La base de datos no responde |

## Pruebas

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r backend/requirements.txt pytest
cd backend
../.venv/Scripts/python -m pytest tests/proyecto tests/laboratorio -v
```

Las pruebas usan SQLite en memoria o los DAO en memoria. No necesitan Docker ni un `.env`.
