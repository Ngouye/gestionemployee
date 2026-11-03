import csv
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO

from django.db import models
from django.http import HttpResponse
from django.utils import timezone
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter


def _clean(value):
    if value is None:
        return ''
    if isinstance(value, bool):
        return 'Oui' if value else 'Non'
    if isinstance(value, datetime):
        return timezone.localtime(value).replace(tzinfo=None) if timezone.is_aware(value) else value
    if isinstance(value, (date, int, float, Decimal, str)):
        return value
    if isinstance(value, models.Model):
        return str(value)
    return str(value)


def export_response(filename, headers, rows, fmt='xlsx', sheet_title='Export'):
    """Renvoie un fichier Excel (xlsx) ou CSV prêt à télécharger."""
    stamp = timezone.localdate().strftime('%Y%m%d')
    if fmt == 'csv':
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="{filename}_{stamp}.csv"'
        response.write('﻿')  # BOM pour Excel
        writer = csv.writer(response, delimiter=';')
        writer.writerow(headers)
        for row in rows:
            writer.writerow([_clean(v) for v in row])
        return response

    wb = Workbook()
    ws = wb.active
    ws.title = sheet_title[:31]
    ws.append(list(headers))
    header_fill = PatternFill('solid', fgColor='4F46E5')
    for cell in ws[1]:
        cell.font = Font(bold=True, color='FFFFFF')
        cell.fill = header_fill
        cell.alignment = Alignment(vertical='center')
    widths = [len(str(h)) for h in headers]
    for row in rows:
        values = [_clean(v) for v in row]
        ws.append(values)
        for i, value in enumerate(values):
            widths[i] = max(widths[i], min(len(str(value)), 60))
    for i, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = width + 3
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            if isinstance(cell.value, (date, datetime)):
                cell.number_format = 'DD/MM/YYYY'
            elif isinstance(cell.value, (int, float, Decimal)) and not isinstance(cell.value, bool):
                cell.number_format = '#,##0.##'
    ws.freeze_panes = 'A2'
    buffer = BytesIO()
    wb.save(buffer)
    response = HttpResponse(
        buffer.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}_{stamp}.xlsx"'
    return response
