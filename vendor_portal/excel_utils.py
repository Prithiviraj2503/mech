from io import BytesIO
from pathlib import Path

from django.conf import settings


TEMPLATE_RELATIVE_PATH = Path("vendor_portal") / "static" / "Supplier Certificate Template.xls"


def _cell_to_indices(cell_ref):
    column_part = ""
    row_part = ""
    for char in cell_ref:
        if char.isalpha():
            column_part += char.upper()
        elif char.isdigit():
            row_part += char

    column_index = 0
    for char in column_part:
        column_index = column_index * 26 + (ord(char) - ord("A") + 1)

    return int(row_part) - 1, column_index - 1


def _set_cell(sheet, cell_ref, value):
    row_index, col_index = _cell_to_indices(cell_ref)
    sheet.write(row_index, col_index, value if value is not None else "")


def _chemical(document, key, row_name):
    return document.chemical_data.get(key, {}).get(row_name, "")


def _mechanical(document, key, row_name):
    return document.mechanical_data.get(key, {}).get(row_name, "")


def _heat_row(document, index, key):
    rows = document.heat_treatment_details.get("rows", [])
    if index < len(rows):
        return rows[index].get(key, "")
    return ""


def _line_item(document, index, key):
    rows = document.line_items or []
    if index < len(rows):
        return rows[index].get(key, "")
    return ""


def render_document_excel(document):
    try:
        import xlrd
        from xlutils.copy import copy as xl_copy
    except ImportError as exc:
        raise RuntimeError(
            "Excel export dependencies are not installed. Install the packages from requirements.txt before downloading Excel."
        ) from exc

    template_path = Path(settings.BASE_DIR) / TEMPLATE_RELATIVE_PATH
    if not template_path.exists():
        raise RuntimeError("Supplier Certificate Template.xls was not found in vendor_portal/static.")

    workbook = xlrd.open_workbook(template_path.as_posix(), formatting_info=True)
    writable_workbook = xl_copy(workbook)
    sheet = writable_workbook.get_sheet(0)

    simple_map = {
        "A3": f"TC No:{document.document_number}",
        "N3": f"Date:{document.certificate_date.strftime('%d.%m.%Y') if document.certificate_date else ''}",
        "F1": document.company_name,
        "F2": document.company_address,
        "N1": document.barcode_value,
        "A6": document.customer_name,
        "A7": document.po_number,
        "A8": document.material_grade,
        "A9": document.material_standard,
        "A10": document.tdc_number,
        "I6": document.maker,
        "I7": document.mill_certificate_number,
        "I8": document.raw_material_specification,
        "I9": document.manufacturing_process,
        "I10": document.heat_number,
        "I11": document.raw_material_standard,
        "A13": document.forging_data.get("heat_no", ""),
        "A14": document.forging_data.get("heat_batch_no", ""),
        "I13": document.forging_data.get("forge_method", ""),
        "I14": document.forging_data.get("supplier_identification", ""),
        "A42": document.notes,
        "J46": document.authorized_signatory,
        "J47": document.signatory_role,
    }

    for cell_ref, value in simple_map.items():
        _set_cell(sheet, cell_ref, value)

    chemical_columns = {
        "c": "C",
        "si": "D",
        "mn": "E",
        "p": "F",
        "s": "G",
        "cr": "H",
        "mo": "I",
        "ni": "J",
        "cu": "K",
        "v": "L",
        "nb": "M",
        "cr_mo": "N",
        "cr_mo_ni_cu_v": "O",
        "ce": "P",
    }
    chemical_rows = {"min": 18, "max": 19, "actual": 20}
    for key, column in chemical_columns.items():
        for row_name, row_number in chemical_rows.items():
            _set_cell(sheet, f"{column}{row_number}", _chemical(document, key, row_name))

    mechanical_row_map = {
        "yield_strength": 24,
        "tensile_strength": 25,
        "elongation": 26,
        "reduction_of_area": 27,
        "hardness_hbv": 28,
        "impact_test": 29,
    }
    for key, row_number in mechanical_row_map.items():
        _set_cell(sheet, f"B{row_number}", _mechanical(document, key, "spec_min"))
        _set_cell(sheet, f"C{row_number}", _mechanical(document, key, "spec_max"))
        _set_cell(sheet, f"D{row_number}", _mechanical(document, key, "actual"))

    _set_cell(sheet, "A32", document.heat_treatment_details.get("heat_no", ""))
    _set_cell(sheet, "B32", document.heat_treatment_details.get("process", ""))
    _set_cell(sheet, "G32", document.heat_treatment_details.get("furnace_type", ""))
    _set_cell(sheet, "G33", document.heat_treatment_details.get("furnace_no", ""))
    _set_cell(sheet, "A33", document.heat_treatment_details.get("heat_batch_no", ""))

    heat_rows = [33, 34, 35, 36]
    for index, row_number in enumerate(heat_rows):
        _set_cell(sheet, f"C{row_number}", _heat_row(document, index, "temperature_c"))
        _set_cell(sheet, f"D{row_number}", _heat_row(document, index, "soaking_hours"))
        _set_cell(sheet, f"E{row_number}", _heat_row(document, index, "cooling_medium"))

    item_rows = [38, 39, 40, 41, 42]
    for index, row_number in enumerate(item_rows):
        _set_cell(sheet, f"A{row_number}", _line_item(document, index, "item"))
        _set_cell(sheet, f"B{row_number}", _line_item(document, index, "description"))
        _set_cell(sheet, f"D{row_number}", _line_item(document, index, "specification"))
        _set_cell(sheet, f"F{row_number}", _line_item(document, index, "production_no"))
        _set_cell(sheet, f"G{row_number}", _line_item(document, index, "total_quantity"))
        _set_cell(sheet, f"H{row_number}", _line_item(document, index, "supplied_quantity"))

    output = BytesIO()
    writable_workbook.save(output)
    return output.getvalue()
