"""Bulletin de paie au format PDF (ReportLab)."""
from io import BytesIO

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from core.company import get_company
from core.utils import format_money

from .models import PayslipLine

PRIMARY = colors.HexColor('#4f46e5')
LIGHT = colors.HexColor('#eef2ff')
BORDER = colors.HexColor('#cbd5e1')


def _money(value, company):
    if value in (None, ''):
        return ''
    return format_money(value, company.currency_decimals, separator=' ')


def _rate(value):
    if value in (None, ''):
        return ''
    return f'{value.normalize():f}'.replace('.', ',') + ' %'


def render_payslip_pdf(payslip):
    company = get_company()
    employee = payslip.employee
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=14 * mm, rightMargin=14 * mm,
                            topMargin=12 * mm, bottomMargin=14 * mm,
                            title=f'Bulletin {payslip.number}', author=company.name)
    styles = getSampleStyleSheet()
    small = ParagraphStyle('small', parent=styles['Normal'], fontSize=8, leading=10)
    normal = ParagraphStyle('normal', parent=styles['Normal'], fontSize=9, leading=12)
    title = ParagraphStyle('title', parent=styles['Title'], fontSize=15, textColor=PRIMARY, spaceAfter=0)
    right = ParagraphStyle('right', parent=normal, alignment=TA_RIGHT)
    story = []

    # En-tête : entreprise / titre
    company_lines = [f'<b>{company.legal_name or company.name}</b>']
    for value in (company.address, ' '.join(filter(None, [company.city, company.country])), company.phone,
                  company.email):
        if value:
            company_lines.append(value)
    if company.tax_number:
        company_lines.append(f'NINEA : {company.tax_number}')
    if company.registration_number:
        company_lines.append(f'RCCM : {company.registration_number}')
    left_cell = [Paragraph('<br/>'.join(company_lines), small)]
    if company.logo:
        try:
            logo = Image(company.logo.path, width=28 * mm, height=16 * mm, kind='proportional')
            left_cell.insert(0, logo)
        except Exception:
            pass
    header = Table([[left_cell, [Paragraph('BULLETIN DE PAIE', title),
                                 Paragraph(f'Période : <b>{payslip.period.label}</b>', right),
                                 Paragraph(f'N° {payslip.number}', right)]]],
                   colWidths=[95 * mm, 87 * mm])
    header.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP')]))
    story += [header, Spacer(1, 6 * mm)]

    # Bloc salarié
    info = [
        ['Matricule', employee.employee_id, 'Date d’embauche', employee.hire_date.strftime('%d/%m/%Y')],
        ['Nom et prénom', payslip.employee_name, 'Contrat', payslip.contract_type],
        ['Poste', payslip.position_title or '—', 'Département', payslip.department_name or '—'],
        ['N° sécurité sociale', employee.social_security_number or '—', 'Parts fiscales',
         f'{employee.tax_shares}'.replace('.', ',')],
        ['Mode de paiement', employee.get_payment_method_display(), 'Jours rémunérés', f'{payslip.days_in_service}'],
    ]
    info_table = Table(info, colWidths=[34 * mm, 57 * mm, 34 * mm, 57 * mm])
    info_table.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 8.5),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#475569')),
        ('TEXTCOLOR', (2, 0), (2, -1), colors.HexColor('#475569')),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica-Bold'),
        ('FONTNAME', (3, 0), (3, -1), 'Helvetica-Bold'),
        ('BOX', (0, 0), (-1, -1), 0.6, BORDER),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8fafc')),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4), ('TOPPADDING', (0, 0), (-1, -1), 4),
    ]))
    story += [info_table, Spacer(1, 6 * mm)]

    # Lignes du bulletin
    rows = [['Rubrique', 'Base', 'Taux sal.', 'Gains', 'Retenues', 'Taux pat.', 'Part patronale']]
    for line in payslip.lines.all():
        is_earning = line.kind == PayslipLine.Kind.EARNING
        show_deduction = not is_earning and (line.amount or line.kind != PayslipLine.Kind.CONTRIBUTION)
        rows.append([
            Paragraph(line.label, small),
            _money(line.base, company),
            _rate(line.rate),
            _money(line.amount, company) if is_earning else '',
            _money(line.amount, company) if show_deduction else '',
            _rate(line.employer_rate),
            _money(line.employer_amount, company) if line.employer_amount else '',
        ])
    rows.append(['TOTAUX', '', '', _money(payslip.gross_salary, company), _money(payslip.total_deductions, company),
                 '', _money(payslip.employer_contributions, company)])
    lines_table = Table(rows, colWidths=[56 * mm, 22 * mm, 15 * mm, 23 * mm, 23 * mm, 15 * mm, 28 * mm],
                        repeatRows=1)
    lines_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), PRIMARY),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LINEBELOW', (0, 1), (-1, -2), 0.3, BORDER),
        ('BOX', (0, 0), (-1, -1), 0.6, BORDER),
        ('BACKGROUND', (0, -1), (-1, -1), LIGHT),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#f8fafc')]),
    ]))
    story += [lines_table, Spacer(1, 6 * mm)]

    # Synthèse et net à payer
    summary = Table([
        ['Salaire brut', _money(payslip.gross_salary, company),
         'Coût total employeur', _money(payslip.employer_cost, company)],
        ['Cotisations salariales', _money(payslip.employee_contributions, company),
         'Revenu imposable', _money(payslip.taxable_salary, company)],
        ['Impôt sur le revenu', _money(payslip.income_tax, company),
         'Autres retenues', _money(payslip.other_deductions, company)],
    ], colWidths=[45 * mm, 46 * mm, 45 * mm, 46 * mm])
    summary.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 8.5), ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('ALIGN', (3, 0), (3, -1), 'RIGHT'), ('BOX', (0, 0), (-1, -1), 0.6, BORDER),
        ('LINEBELOW', (0, 0), (-1, -2), 0.3, BORDER),
    ]))
    net = Table([['NET À PAYER',f'{_money(payslip.net_salary, company)} {company.currency}']],
                colWidths=[120 * mm, 62 * mm])
    net.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), PRIMARY), ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'), ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'), ('TOPPADDING', (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
    ]))
    story += [summary, Spacer(1, 4 * mm), net, Spacer(1, 8 * mm)]

    payment = payslip.period.payment_date
    footer = (f'Montants exprimés en {company.currency}. '
              + (f'Payé le {payment:%d/%m/%Y}. ' if payment else '')
              + 'Pour vous aider à faire valoir vos droits, conservez ce bulletin de paie sans limitation de durée. '
              + f'Document généré le {timezone.localtime():%d/%m/%Y à %H:%M}.')
    story.append(Paragraph(footer, ParagraphStyle('foot', parent=small, textColor=colors.HexColor('#64748b'))))

    doc.build(story)
    return buffer.getvalue()
