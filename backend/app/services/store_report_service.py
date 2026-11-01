"""
Generador del Excel "CHECKLIST DE VISITA A TIENDA".

Reproduce EXACTAMENTE el diseño del archivo de referencia
(Checklist_Visita_Tienda_Agosto_2026.xlsx):
- Mismos títulos, mismas secciones (A-F), mismo orden de filas.
- Mismos colores: encabezado de sección azul marino (#1B2A4A) con texto
  blanco, encabezados de columna azul claro (#C1E4F5), subtítulos del
  checklist (#EEF3F8).
- Mismas fórmulas de Excel (no valores calculados en Python) para que el
  archivo se recalcule solo si alguien edita una celda amarilla.
- Mismo esquema de "celda editable": fuente azul (#0000FF) + relleno
  amarillo (#FFFF00) para los datos que antes se digitaban a mano y que
  ahora se llenan automáticamente con los datos de tu app.
- Mismos anchos de columna (A=45.29, B=16, D=15) y freeze_panes="A4".

Reemplaza a `generar_informe_tienda_excel` en tu servicio actual. Se
apoya en las mismas fuentes de datos que ya usas:
    - obtener_dashboard_tienda_por_id
    - obtener_venta_asesor_aux / obtener_meta_tienda / calcular_metas_asesoras
    - modelos: Store, Advisor, AdvisorPerformance, SalesHistoryLine,
      ConversionDiaria

AJUSTA los bloques marcados con "# AJUSTE:" si algún nombre de campo o
relación en tus modelos es distinto al que asumí aquí.
"""

import calendar
from datetime import datetime
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.formatting.rule import CellIsRule
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.page import PageMargins
from sqlalchemy import func

from app.extensions import db
from app.models import (
    Store, AdvisorPerformance, Advisor, SalesHistoryLine, ConversionDiaria
)
from app.services.dashboard_service import obtener_dashboard_tienda_por_id
from app.services.advisor_goal_service import (
    obtener_venta_asesor_aux,
    obtener_meta_tienda,
    calcular_metas_asesoras
)


def _float(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _int(value):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


# ============================================================
# ESTILOS (calcados de la plantilla original)
# ============================================================
COLOR_NAVY = "1B2A4A"          # encabezado de sección
COLOR_HEADER_BLUE = "C1E4F5"   # encabezado de tabla (Concepto/Valor/...)
COLOR_SUBHEADER = "EEF3F8"     # subtítulos dentro del checklist (F)
COLOR_INPUT_FILL = "FFFF00"    # relleno de celdas editables
COLOR_INPUT_FONT = "0000FF"    # texto azul de celdas editables
COLOR_FORMULA_FONT = "000000"  # texto negro de celdas con fórmula
COLOR_TITLE = "1B2A4A"

FONT_TITLE = Font(name="Arial", size=16, bold=True, color=COLOR_TITLE)
FONT_SECTION = Font(name="Arial", size=12, bold=True, color="FFFFFF")
FONT_TABLE_HEADER = Font(name="Arial", size=10, bold=True, color=COLOR_NAVY)
FONT_LABEL = Font(name="Arial", size=10, bold=True, color=None)
FONT_LABEL_BOLD_TOTAL = Font(name="Arial", size=10, bold=True, color=None)
FONT_NORMAL = Font(name="Arial", size=10, bold=False, color=None)
FONT_INPUT = Font(name="Arial", size=10, bold=False, color=COLOR_INPUT_FONT)
FONT_FORMULA = Font(name="Arial", size=10, bold=False, color=COLOR_FORMULA_FONT)
FONT_FORMULA_BOLD = Font(name="Arial", size=10, bold=True, color=COLOR_FORMULA_FONT)
FONT_SUBHEADER = Font(name="Arial", size=10, bold=True, color=COLOR_NAVY)
FONT_SMALL_NOTE = Font(name="Arial", size=9, bold=False, color=None)

FILL_SECTION = PatternFill(start_color=COLOR_NAVY, end_color=COLOR_NAVY, fill_type="solid")
FILL_TABLE_HEADER = PatternFill(start_color=COLOR_HEADER_BLUE, end_color=COLOR_HEADER_BLUE, fill_type="solid")
FILL_SUBHEADER = PatternFill(start_color=COLOR_SUBHEADER, end_color=COLOR_SUBHEADER, fill_type="solid")
FILL_INPUT = PatternFill(start_color=COLOR_INPUT_FILL, end_color=COLOR_INPUT_FILL, fill_type="solid")
FILL_NONE = PatternFill(fill_type=None)

BORDER_THIN = Border(
    left=Side(style="thin"), right=Side(style="thin"),
    top=Side(style="thin"), bottom=Side(style="thin"),
)

ALIGN_LEFT = Alignment(horizontal="left", vertical="center")
ALIGN_CENTER = Alignment(horizontal="center", vertical="center")
ALIGN_RIGHT = Alignment(horizontal="right", vertical="center")

FMT_MONEY = '\\$#,##0'
FMT_INT = '#,##0'
FMT_PCT = '0.0%'
FMT_DEC2 = '0.00'
FMT_DATE = 'dd/mm/yyyy'


def _input_cell(ws, coord, value, number_format=None, align=ALIGN_RIGHT):
    """Celda editable / dato traído de la app: fuente azul + relleno amarillo."""
    cell = ws[coord]
    cell.value = value
    cell.font = FONT_INPUT
    cell.fill = FILL_INPUT
    cell.border = BORDER_THIN
    cell.alignment = align
    if number_format:
        cell.number_format = number_format
    return cell


def _formula_cell(ws, coord, formula, number_format=None, bold=False, align=ALIGN_RIGHT):
    """Celda calculada por Excel con formato condicional verde/rojo según signo."""
    cell = ws[coord]
    cell.value = formula
    cell.font = FONT_FORMULA_BOLD if bold else FONT_FORMULA
    cell.border = BORDER_THIN
    cell.alignment = align
    if number_format:
        cell.number_format = number_format

    # Formato condicional para resaltar valores positivos/negativos
    ws.conditional_formatting.add(
        coord,
        CellIsRule(operator='greaterThanOrEqual', formula=['0'], font=Font(color='006600'))
    )
    ws.conditional_formatting.add(
        coord,
        CellIsRule(operator='lessThan', formula=['0'], font=Font(color='CC0000'))
    )
    return cell


def _label_cell(ws, coord, text, bold=False, align=ALIGN_LEFT, small=False):
    cell = ws[coord]
    cell.value = text
    cell.font = FONT_SMALL_NOTE if small else (FONT_LABEL if bold else FONT_NORMAL)
    cell.border = BORDER_THIN
    cell.alignment = align
    return cell


def _section_title(ws, row, text, last_col=8):
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=last_col)
    cell = ws.cell(row=row, column=1, value=text)
    cell.font = FONT_SECTION
    cell.fill = FILL_SECTION
    cell.alignment = ALIGN_LEFT
    for c in range(1, last_col + 1):
        ws.cell(row=row, column=c).border = BORDER_THIN
        ws.cell(row=row, column=c).fill = FILL_SECTION
    return row + 1


def _table_header(ws, row, headers, start_col=1):
    for i, h in enumerate(headers, start=start_col):
        cell = ws.cell(row=row, column=i, value=h)
        cell.font = FONT_TABLE_HEADER
        cell.fill = FILL_TABLE_HEADER
        cell.border = BORDER_THIN
        cell.alignment = ALIGN_CENTER if i > start_col else ALIGN_LEFT
    return row + 1


# ============================================================
# FUNCIÓN PRINCIPAL
# ============================================================
def generar_informe_visita_tienda_excel(store_id, anio, mes, dia_corte,
                                         responsable=None, fecha_visita=None):
    """
    Genera el Excel 'CHECKLIST DE VISITA A TIENDA' con el mismo diseño
    del archivo de referencia, poblado con los datos reales de la tienda.
    """
    datos = obtener_dashboard_tienda_por_id(store_id, anio, mes, dia_corte)
    tienda = db.session.get(Store, store_id)
    if not tienda:
        raise ValueError("Tienda no encontrada")

    meta_tienda = _float(obtener_meta_tienda(store_id, anio, mes))
    venta_asesor_aux = _float(obtener_venta_asesor_aux(store_id, anio, mes))
    resultado_metas = calcular_metas_asesoras(store_id, anio, mes, meta_tienda, venta_asesor_aux)
    metas_asesoras = resultado_metas.get("asesoras", [])

    # AJUSTE: si tu AdvisorPerformance no tiene 'venta' como columna propia,
    # cambia esta consulta por la que ya usabas en tu código original.
    performance_rows = (
        db.session.query(
            AdvisorPerformance.advisor_id,
            func.sum(AdvisorPerformance.unidades).label("unidades"),
            func.sum(AdvisorPerformance.facturas).label("facturas")
        )
        .filter(
            AdvisorPerformance.store_id == store_id,
            AdvisorPerformance.anio == anio,
            AdvisorPerformance.mes == mes,
            AdvisorPerformance.activo.is_(True)
        )
        .group_by(AdvisorPerformance.advisor_id)
        .all()
    )
    perf_dict = {row.advisor_id: row for row in performance_rows}

    # --- Tráfico / facturas del año anterior (para la sección B) ---
    conv_actual = (
        db.session.query(
            func.sum(ConversionDiaria.trafico).label("trafico"),
            func.sum(ConversionDiaria.facturas).label("facturas"),
        )
        .filter(
            ConversionDiaria.store_id == store_id,
            ConversionDiaria.anio == anio,
            ConversionDiaria.mes == mes,
            ConversionDiaria.dia <= dia_corte,
            ConversionDiaria.activo.is_(True),
        )
        .first()
    )
    conv_anterior = (
        db.session.query(
            func.sum(ConversionDiaria.trafico).label("trafico"),
            func.sum(ConversionDiaria.facturas).label("facturas"),
        )
        .filter(
            ConversionDiaria.store_id == store_id,
            ConversionDiaria.anio == anio - 1,
            ConversionDiaria.mes == mes,
            ConversionDiaria.dia <= dia_corte,
            ConversionDiaria.activo.is_(True),
        )
        .first()
    )
    trafico_2026 = _int(conv_actual.trafico if conv_actual else 0)
    facturas_2026 = _int(conv_actual.facturas if conv_actual else 0)
    trafico_2025 = _int(conv_anterior.trafico if conv_anterior else 0)
    facturas_2025 = _int(conv_anterior.facturas if conv_anterior else 0)

    # --- Unidades vendidas del año anterior (sección C) ---
    unidades_2026 = _float(datos.get("unidades_asesoras", 0))
    perf_prev = (
        db.session.query(func.sum(AdvisorPerformance.unidades))
        .filter(
            AdvisorPerformance.store_id == store_id,
            AdvisorPerformance.anio == anio - 1,
            AdvisorPerformance.mes == mes,
            AdvisorPerformance.activo.is_(True),
        )
        .scalar()
    )
    unidades_2025 = _float(perf_prev)

    # --- Ventas por línea/categoría con histórico 2025/2026 (sección D) ---
    lineas_datos = datos.get("metas_lineas", [])
    dias_mes = calendar.monthrange(anio, mes)[1]

    # --- Días hábiles del mes (excluyendo domingos) ---
    dias_habiles = sum(
        1 for d in range(1, dias_mes + 1)
        if datetime(anio, mes, d).weekday() != 6  # 6 = domingo
    )

    fecha_visita = fecha_visita or datetime.now()
    responsable = responsable or (tienda.supervisor.nombre if tienda.supervisor else "")

    wb = Workbook()
    ws = wb.active
    ws.title = "Checklist Visita Tienda"
    ws.page_setup.orientation = "landscape"
    ws.page_margins = PageMargins(left=0.5, right=0.5, top=0.5, bottom=0.5)

    # --- Título ---
    ws["A1"] = "CHECKLIST DE VISITA A TIENDA"
    ws["A1"].font = FONT_TITLE
    ws["A1"].alignment = ALIGN_LEFT

    # --- Datos generales de la visita ---
    _label_cell(ws, "A3", "Fecha de visita", bold=True)
    ws.merge_cells("B3:C3")
    _input_cell(ws, "B3", fecha_visita, number_format=FMT_DATE)

    _label_cell(ws, "A4", "Tienda", bold=True)
    ws.merge_cells("B4:C4")
    _input_cell(ws, "B4", tienda.codigo, align=ALIGN_RIGHT)

    _label_cell(ws, "A5", "Responsable de la visita", bold=True)
    ws.merge_cells("B5:C5")
    _input_cell(ws, "B5", responsable, align=ALIGN_RIGHT)

    fila = 7

    # ============================================================
    # A. VENTA TOTAL Y CUMPLIMIENTO DE CUOTA
    # ============================================================
    fila = _section_title(ws, fila, "A. VENTA TOTAL Y CUMPLIMIENTO DE CUOTA", last_col=3)
    fila = _table_header(ws, fila, ["Concepto", "Valor", "Unidad / Fórmula"])

    row_venta_2025 = fila
    _label_cell(ws, f"A{fila}", "Venta 2025 (mismo periodo)")
    _input_cell(ws, f"B{fila}", _float(datos.get("venta_anterior", 0)), FMT_MONEY)
    _label_cell(ws, f"C{fila}", "Dato de venta del año anterior, mismos días", small=True)
    fila += 1

    row_venta_2026 = fila
    _label_cell(ws, f"A{fila}", "Venta 2026 (a la fecha)")
    _input_cell(ws, f"B{fila}", _float(datos.get("ventas", 0)), FMT_INT)
    _label_cell(ws, f"C{fila}", "Dato de venta actual", small=True)
    fila += 1

    row_diferencia = fila
    _label_cell(ws, f"A{fila}", "Diferencia (2026 vs. 2025)")
    _formula_cell(ws, f"B{fila}", f"=B{row_venta_2026}-B{row_venta_2025}", FMT_MONEY)
    _label_cell(ws, f"C{fila}", "Calculada automáticamente", small=True)
    fila += 1

    _label_cell(ws, f"A{fila}", "Variación %")
    _formula_cell(ws, f"B{fila}", f'=IFERROR(B{row_diferencia}/B{row_venta_2025},"")', FMT_PCT)
    _label_cell(ws, f"C{fila}", "Calculada automáticamente", small=True)
    fila += 1

    row_cuota = fila
    _label_cell(ws, f"A{fila}", "Cuota mensual de la tienda")
    _input_cell(ws, f"B{fila}", meta_tienda, FMT_MONEY)
    _label_cell(ws, f"C{fila}", "Dato de la app", small=True)
    fila += 1

    row_dias_habiles = fila
    _label_cell(ws, f"A{fila}", "Días hábiles del mes")
    _input_cell(ws, f"B{fila}", dias_habiles, FMT_INT)
    _label_cell(ws, f"C{fila}", "Calculado por el sistema", small=True)
    fila += 1

    row_dias_transc = fila
    _label_cell(ws, f"A{fila}", "Días transcurridos a la fecha de visita")
    _input_cell(ws, f"B{fila}", dia_corte, FMT_INT)
    _label_cell(ws, f"C{fila}", "Dato de corte seleccionado", small=True)
    fila += 1

    row_cuota_prop = fila
    _label_cell(ws, f"A{fila}", "Cuota proporcional a la fecha")
    _formula_cell(ws, f"B{fila}",
                  f'=IFERROR(B{row_cuota}*(B{row_dias_transc}/B{row_dias_habiles}),"")', FMT_MONEY)
    _label_cell(ws, f"C{fila}", "Calculada automáticamente", small=True)
    fila += 1

    _label_cell(ws, f"A{fila}", "Cumplimiento cuota proporcional %")
    _formula_cell(ws, f"B{fila}", f'=IFERROR(B{row_venta_2026}/B{row_cuota_prop},"")', FMT_PCT)
    _label_cell(ws, f"C{fila}", "Calculada automáticamente", small=True)
    fila += 1

    row_falta_cuota = fila
    _label_cell(ws, f"A{fila}", "Falta para cuota total del mes")
    _formula_cell(ws, f"B{fila}", f"=B{row_cuota}-B{row_venta_2026}", FMT_MONEY)
    _label_cell(ws, f"C{fila}", "Calculada automáticamente", small=True)
    fila += 1

    row_dias_rest = fila
    _label_cell(ws, f"A{fila}", "Días restantes del mes")
    _formula_cell(ws, f"B{fila}", f"=B{row_dias_habiles}-B{row_dias_transc}", FMT_INT)
    _label_cell(ws, f"C{fila}", "Calculada automáticamente", small=True)
    fila += 1

    _label_cell(ws, f"A{fila}", "Meta de venta promedio / día (días restantes)")
    _formula_cell(ws, f"B{fila}", f'=IFERROR(B{row_falta_cuota}/B{row_dias_rest},"")', FMT_MONEY)
    _label_cell(ws, f"C{fila}", "Calculada automáticamente", small=True)
    fila += 2  # fila en blanco entre secciones

    # ============================================================
    # B. TRÁFICO, FACTURACIÓN Y CONVERSIÓN
    # ============================================================
    fila = _section_title(ws, fila, "B. TRÁFICO, FACTURACIÓN Y CONVERSIÓN", last_col=4)
    fila = _table_header(ws, fila, ["Concepto", "2025", "2026", "Diferencia"])

    row_trafico = fila
    _label_cell(ws, f"A{fila}", "Tráfico (visitantes)")
    _input_cell(ws, f"B{fila}", trafico_2025, FMT_INT)
    _input_cell(ws, f"C{fila}", trafico_2026, FMT_INT)
    _formula_cell(ws, f"D{fila}", f"=C{fila}-B{fila}", FMT_INT)
    fila += 1

    row_facturas = fila
    _label_cell(ws, f"A{fila}", "Cantidad de facturas")
    _input_cell(ws, f"B{fila}", facturas_2025, FMT_INT)
    _input_cell(ws, f"C{fila}", facturas_2026, FMT_INT)
    _formula_cell(ws, f"D{fila}", f"=C{fila}-B{fila}", FMT_INT)
    fila += 1

    _label_cell(ws, f"A{fila}", "Conversión (facturas / tráfico)")
    _formula_cell(ws, f"B{fila}", f'=IFERROR(B{row_facturas}/B{row_trafico},"")', FMT_PCT)
    _formula_cell(ws, f"C{fila}", f'=IFERROR(C{row_facturas}/C{row_trafico},"")', FMT_PCT)
    _formula_cell(ws, f"D{fila}", f'=IFERROR(C{fila}-B{fila},"")', FMT_PCT)
    fila += 2

    # ============================================================
    # C. TICKET PROMEDIO
    # ============================================================
    fila = _section_title(ws, fila, "C. TICKET PROMEDIO", last_col=4)
    fila = _table_header(ws, fila, ["Concepto", "2025", "2026", "Variación %"])

    row_unidades = fila
    _label_cell(ws, f"A{fila}", "Unidades vendidas")
    _input_cell(ws, f"B{fila}", unidades_2025, FMT_INT)
    _input_cell(ws, f"C{fila}", unidades_2026, FMT_INT)
    fila += 1

    row_ticket = fila
    _label_cell(ws, f"A{fila}", "Ticket $ (venta / facturas)")
    _formula_cell(ws, f"B{fila}", f'=IFERROR(B{row_venta_2025}/B{row_facturas},"")', FMT_MONEY)
    _formula_cell(ws, f"C{fila}", f'=IFERROR(B{row_venta_2026}/C{row_facturas},"")', FMT_MONEY)
    _formula_cell(ws, f"D{fila}", f'=IFERROR((C{fila}-B{fila})/B{fila},"")', FMT_PCT)
    fila += 1

    _label_cell(ws, f"A{fila}", "Ticket unidades (unidades / facturas)")
    _formula_cell(ws, f"B{fila}", f'=IFERROR(B{row_unidades}/B{row_facturas},"")', FMT_DEC2)
    _formula_cell(ws, f"C{fila}", f'=IFERROR(C{row_unidades}/C{row_facturas},"")', FMT_DEC2)
    _formula_cell(ws, f"D{fila}", f'=IFERROR((C{fila}-B{fila})/B{fila},"")', FMT_PCT)
    fila += 2

    # ============================================================
    # D. VENTAS POR CATEGORÍA
    # ============================================================
    fila = _section_title(ws, fila, "D. VENTAS POR CATEGORÍA", last_col=8)
    fila = _table_header(ws, fila, [
        "Categoría", "Venta 2025", "Venta 2026", "Diferencia",
        "Variación %", "Meta 2026", "Meta proporcional", "Cumplimiento %"
    ])

    primera_fila_cat = fila
    for linea in lineas_datos:
        hist_2025 = db.session.query(func.sum(SalesHistoryLine.venta)).filter(
            SalesHistoryLine.store_id == store_id,
            SalesHistoryLine.line_id == linea.get("line_id"),
            SalesHistoryLine.anio == anio - 1,
            SalesHistoryLine.mes == mes,
        ).scalar()
        hist_2026 = db.session.query(func.sum(SalesHistoryLine.venta)).filter(
            SalesHistoryLine.store_id == store_id,
            SalesHistoryLine.line_id == linea.get("line_id"),
            SalesHistoryLine.anio == anio,
            SalesHistoryLine.mes == mes,
        ).scalar()
        cuota_linea = _float(linea.get("meta", 0))

        _label_cell(ws, f"A{fila}", linea.get("linea"))
        _input_cell(ws, f"B{fila}", _float(hist_2025), FMT_MONEY)
        _input_cell(ws, f"C{fila}", _float(hist_2026), FMT_MONEY)
        _formula_cell(ws, f"D{fila}", f"=C{fila}-B{fila}", FMT_MONEY)
        _formula_cell(ws, f"E{fila}", f'=IFERROR(D{fila}/B{fila},"")', FMT_PCT)
        _input_cell(ws, f"F{fila}", cuota_linea, FMT_MONEY)
        _formula_cell(ws, f"G{fila}", f"=IFERROR(F{fila}*(B${row_dias_transc}/B${row_dias_habiles}),\"\")", FMT_MONEY)
        _formula_cell(ws, f"H{fila}", f'=IFERROR(C{fila}/G{fila},"")', FMT_PCT)
        fila += 1

    ultima_fila_cat = fila - 1
    _label_cell(ws, f"A{fila}", "TOTAL categorías", bold=True)
    _formula_cell(ws, f"B{fila}", f"=SUM(B{primera_fila_cat}:B{ultima_fila_cat})", FMT_MONEY, bold=True)
    _formula_cell(ws, f"C{fila}", f"=SUM(C{primera_fila_cat}:C{ultima_fila_cat})", FMT_MONEY, bold=True)
    _formula_cell(ws, f"D{fila}", f"=SUM(D{primera_fila_cat}:D{ultima_fila_cat})", FMT_MONEY, bold=True)
    _formula_cell(ws, f"E{fila}", f'=IFERROR(D{fila}/B{fila},"")', FMT_PCT, bold=True)
    _formula_cell(ws, f"F{fila}", f"=SUM(F{primera_fila_cat}:F{ultima_fila_cat})", FMT_MONEY, bold=True)
    _formula_cell(ws, f"G{fila}", f"=SUM(G{primera_fila_cat}:G{ultima_fila_cat})", FMT_MONEY, bold=True)
    _formula_cell(ws, f"H{fila}", f'=IFERROR(C{fila}/G{fila},"")', FMT_PCT, bold=True)
    fila_total_cat = fila
    fila += 1

    _label_cell(ws, f"A{fila}", "Diferencia vs. Venta Total 2026 (Sección A) — debe ser 0", small=True)
    _formula_cell(ws, f"C{fila}", f"=C{fila_total_cat}-B{row_venta_2026}", FMT_MONEY)
    fila += 2

    # ============================================================
    # E. RANKING DE ASESORAS
    # ============================================================
    fila = _section_title(ws, fila, "E. RANKING DE ASESORAS", last_col=7)
    fila = _table_header(ws, fila, [
        "Asesor(a)", "Venta 2026", "Unidades", "Facturas",
        "Ticket $", "Ticket Unid.", "% Participación"
    ])

    primera_fila_ases = fila
    for asesora in metas_asesoras:
        advisor_id = asesora.get("advisor_id")
        nombre = asesora.get("nombre")
        venta = _float(asesora.get("venta", 0))
        perf = perf_dict.get(advisor_id)
        unidades = _float(perf.unidades) if perf else 0
        facturas = _float(perf.facturas) if perf else 0

        _label_cell(ws, f"A{fila}", nombre)
        _input_cell(ws, f"B{fila}", venta, FMT_MONEY)
        _input_cell(ws, f"C{fila}", unidades, FMT_INT)
        _input_cell(ws, f"D{fila}", facturas, FMT_INT)
        _formula_cell(ws, f"E{fila}", f'=IFERROR(B{fila}/D{fila},"")', FMT_MONEY)
        _formula_cell(ws, f"F{fila}", f'=IFERROR(C{fila}/D{fila},"")', FMT_DEC2)
        _formula_cell(ws, f"G{fila}", f'=IFERROR(B{fila}/B${row_venta_2026},"")', FMT_PCT)
        fila += 1

    ultima_fila_ases = fila - 1
    _label_cell(ws, f"A{fila}", "TOTAL asesoras", bold=True)
    _formula_cell(ws, f"B{fila}", f"=SUM(B{primera_fila_ases}:B{ultima_fila_ases})", FMT_MONEY, bold=True)
    _formula_cell(ws, f"C{fila}", f"=SUM(C{primera_fila_ases}:C{ultima_fila_ases})", FMT_INT, bold=True)
    _formula_cell(ws, f"D{fila}", f"=SUM(D{primera_fila_ases}:D{ultima_fila_ases})", FMT_INT, bold=True)
    _formula_cell(ws, f"E{fila}", f'=IFERROR(B{fila}/D{fila},"")', FMT_MONEY, bold=True)
    _formula_cell(ws, f"F{fila}", f'=IFERROR(C{fila}/D{fila},"")', FMT_DEC2, bold=True)
    _formula_cell(ws, f"G{fila}", f'=IFERROR(B{fila}/B${row_venta_2026},"")', FMT_PCT, bold=True)
    fila_total_ases = fila
    fila += 1

    _label_cell(ws, f"A{fila}", "Diferencia vs. Venta Total 2026 (Sección A) — debe ser 0", small=True)
    _formula_cell(ws, f"B{fila}", f"=B{fila_total_ases}-B{row_venta_2026}", FMT_MONEY)
    fila += 2

    # ============================================================
    # F. CHECKLIST CUALITATIVO DE VISITA
    # ============================================================
    fila = _section_title(ws, fila, "F. CHECKLIST CUALITATIVO DE VISITA", last_col=3)
    fila = _table_header(ws, fila, ["Ítem a verificar", "Cumple", "Observaciones"])

    checklist_estructura = [
        ("Exhibición y visual merchandising", [
            "Vitrina principal actualizada según campaña vigente",
        ]),
        ("Gestion Operativa", [
            "Tablero actualizado",
            "Metas socializadas al equipo",
            "Revisar cuanderno de conteo, verificar faltante y que lo suban al Drive",
            "Cambio de precios",
        ]),
        ("Aseo y orden", [
            "Piso, mostradores y probadores limpios",
            "Mercancía doblada / colgada correctamente por talla y color",
            "Bodega y zona de cajas organizadas",
        ]),
        ("Visual", [
            "Vitrinas: Asegurarse de que las vitrinas estén atractivas y alineadas con las campañas actuales.",
            "Exhibiciones: Revisar la correcta implementación de las exhibiciones.",
            "Producto de promoción exhibido en zona de alto tráfico",
        ]),
        ("Servicio al cliente", [
            "Personal completo según turno programado",
            "Asesoras aplican protocolo de venta y venta cruzada",
            "Tiempo de atención en caja dentro del estándar",
        ]),
        ("Presentacion", [
            "Presentacion Personal: Uniforme, cabello, manos y zapatos.",
        ]),
    ]

    fila_primer_item = fila
    fila_ultimo_item = fila
    for subtitulo, items in checklist_estructura:
        ws.merge_cells(start_row=fila, start_column=1, end_row=fila, end_column=6)
        cell = ws.cell(row=fila, column=1, value=subtitulo)
        cell.font = FONT_SUBHEADER
        cell.fill = FILL_SUBHEADER
        cell.alignment = ALIGN_LEFT
        for c in range(1, 7):
            ws.cell(row=fila, column=c).border = BORDER_THIN
            if c <= 6:
                ws.cell(row=fila, column=c).fill = FILL_SUBHEADER
        fila += 1

        for item in items:
            _label_cell(ws, f"A{fila}", f"   {item}")
            _input_cell(ws, f"B{fila}", None, align=ALIGN_CENTER)
            ws.merge_cells(start_row=fila, start_column=3, end_row=fila, end_column=6)
            _input_cell(ws, f"C{fila}", None, align=ALIGN_LEFT)
            ws[f"C{fila}"].font = Font(name="Arial", size=9, color=COLOR_INPUT_FONT)
            for c in range(1, 7):
                ws.cell(row=fila, column=c).border = BORDER_THIN
            fila_ultimo_item = fila
            fila += 1

    _label_cell(ws, f"A{fila}", "Producto-obsevaciones sugerencias necesidades", bold=True)
    ws.merge_cells(start_row=fila, start_column=1, end_row=fila, end_column=6)
    for c in range(1, 7):
        ws.cell(row=fila, column=c).fill = FILL_SUBHEADER if c <= 6 else FILL_NONE
        ws.cell(row=fila, column=c).border = BORDER_THIN
    ws.cell(row=fila, column=1).font = FONT_SUBHEADER
    ws.cell(row=fila, column=1).alignment = ALIGN_CENTER
    fila += 1
    # dos filas en blanco para observaciones libres
    for _ in range(2):
        ws.merge_cells(start_row=fila, start_column=1, end_row=fila, end_column=6)
        _input_cell(ws, f"A{fila}", None, align=ALIGN_LEFT)
        for c in range(1, 7):
            ws.cell(row=fila, column=c).border = BORDER_THIN
        fila += 1

    fila += 1
    row_pct_cumpl = fila
    _label_cell(ws, f"A{fila}", "% Cumplimiento del checklist (Sí / total evaluado)", bold=True)
    _formula_cell(
        ws, f"B{fila}",
        f'=IFERROR(COUNTIF(B{fila_primer_item}:B{fila_ultimo_item},"Sí")'
        f'/(COUNTIF(B{fila_primer_item}:B{fila_ultimo_item},"Sí")'
        f'+COUNTIF(B{fila_primer_item}:B{fila_ultimo_item},"No")),"")',
        FMT_PCT, bold=True
    )
    fila += 1
    _label_cell(ws, f"A{fila}", 'Ítems evaluados como "No" (a corregir)')
    _formula_cell(ws, f"B{fila}", f'=COUNTIF(B{fila_primer_item}:B{fila_ultimo_item},"No")', FMT_INT)

    # --- Anchos de columna y freeze panes ---
    ws.column_dimensions["A"].width = 45.29
    ws.column_dimensions["B"].width = 16
    ws.column_dimensions["C"].width = 15
    ws.column_dimensions["D"].width = 15
    ws.column_dimensions["E"].width = 15
    ws.column_dimensions["F"].width = 15
    ws.column_dimensions["G"].width = 15
    ws.column_dimensions["H"].width = 15
    ws.freeze_panes = "A4"

    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return output