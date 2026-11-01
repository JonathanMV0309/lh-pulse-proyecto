# Dashboard administrativo V2

Esta carpeta contiene la capa visual principal del dashboard administrativo.

## Seguridad

- No cambia consultas, modelos, migraciones ni cálculos.
- `dashboard.html` permanece intacto como respaldo.
- La versión V2 es la vista predeterminada.
- La versión V2 se abre con `/dashboard` o `/dashboard?vista=v2`.
- Para volver temporalmente a la versión clásica usa `/dashboard?vista=clasica`.

## Archivos

- `dashboard_v2.html`: hereda el dashboard actual y carga la capa V2.
- `dashboard-v2.css`: diseño visual aislado bajo la clase `dashboard-v2`.
- `dashboard-v2.js`: recrea únicamente las gráficas y añade controles de interacción.

## Reversibilidad

La V2 fue aprobada como predeterminada. La vista clásica permanece disponible
como respaldo y no es necesario modificar la base de datos.
