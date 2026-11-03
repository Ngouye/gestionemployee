"""Attestation et certificat de travail au format PDF."""
from io import BytesIO
from xml.sax.saxutils import escape

from django.utils import timezone
from django.utils.dateformat import format as date_format
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer

from core.company import get_company

PRIMARY = colors.HexColor('#4f46e5')


def _long_date(value):
    return date_format(value, 'j F Y') if value else ''


def _grammar(employee):
    if employee.gender == 'F':
        return {'civ': 'Madame', 'born': 'née', 'employed': 'employée', 'subject': 'Elle', 'person': "l'intéressée"}
    if employee.gender == 'M':
        return {'civ': 'Monsieur', 'born': 'né', 'employed': 'employé', 'subject': 'Il', 'person': "l'intéressé"}
    return {'civ': 'Madame / Monsieur', 'born': 'né(e)', 'employed': 'employé(e)', 'subject': 'Il / Elle',
            'person': "l'intéressé(e)"}


def _letter_body(employee, kind, company):
    g = _grammar(employee)
    name = f'<b>{escape(g["civ"])} {escape(employee.first_name)} {escape(employee.last_name.upper())}</b>'
    birth = ''
    if employee.date_of_birth:
        birth = f', {g["born"]} le {_long_date(employee.date_of_birth)}'
        if employee.place_of_birth:
            birth += f' à {escape(employee.place_of_birth)}'
    identity = f", titulaire de la pièce d'identité n° {escape(employee.national_id)}" if employee.national_id else ''
    position = escape(str(employee.position)) if employee.position else 'collaborateur'
    contract = employee.current_contract
    signatory = escape(company.hr_signatory_name) or 'Le représentant légal'
    signatory_title = escape(company.hr_signatory_title)
    entity = escape(company.legal_name or company.name)
    intro = (f'Je soussigné(e), <b>{signatory}</b>{", " + signatory_title if signatory_title else ""} '
             f'de la société <b>{entity}</b>, ')
    if kind == 'certificat':
        return [
            intro + f'certifie que {name}{birth}{identity}, a été {g["employed"]} au sein de notre société '
                    f'du <b>{_long_date(employee.hire_date)}</b> au <b>{_long_date(employee.exit_date)}</b> '
                    f'en qualité de <b>{position}</b>.',
            f'{g["subject"]} nous quitte libre de tout engagement.',
            f'Le présent certificat est délivré à {g["person"]} pour servir et valoir ce que de droit.',
        ]
    contract_text = f', dans le cadre d’un {escape(contract.get_contract_type_display().split(" — ")[-1].lower())}' \
        if contract else ''
    return [
        intro + f'atteste que {name}{birth}{identity}, est {g["employed"]} au sein de notre société depuis le '
                f'<b>{_long_date(employee.hire_date)}</b> en qualité de <b>{position}</b>{contract_text}.',
        f'La présente attestation est délivrée à {g["person"]} pour servir et valoir ce que de droit.',
    ]


def render_employment_letter(employee, kind='attestation'):
    company = get_company()
    buffer = BytesIO()
    title = 'CERTIFICAT DE TRAVAIL' if kind == 'certificat' else 'ATTESTATION DE TRAVAIL'
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=22 * mm, rightMargin=22 * mm, topMargin=18 * mm,
                            bottomMargin=20 * mm, title=f'{title.capitalize()} — {employee}', author=company.name)
    styles = getSampleStyleSheet()
    small = ParagraphStyle('small', parent=styles['Normal'], fontSize=8.5, leading=11,
                           textColor=colors.HexColor('#475569'))
    body = ParagraphStyle('body', parent=styles['Normal'], fontSize=11, leading=17, alignment=TA_JUSTIFY,
                          spaceAfter=10)
    heading = ParagraphStyle('heading', parent=styles['Title'], fontSize=17, textColor=PRIMARY, alignment=TA_CENTER,
                             spaceAfter=4)
    right = ParagraphStyle('right', parent=body, alignment=TA_RIGHT)

    story = []
    if company.logo:
        try:
            story.append(Image(company.logo.path, width=34 * mm, height=18 * mm, kind='proportional', hAlign='LEFT'))
        except Exception:
            pass
    header = [f'<b>{escape(company.legal_name or company.name)}</b>']
    for value in (company.address, ' '.join(filter(None, [company.city, company.country])), company.phone,
                  company.email):
        if value:
            header.append(escape(value))
    ids = ' · '.join(filter(None, [f'NINEA : {escape(company.tax_number)}' if company.tax_number else '',
                                   f'RCCM : {escape(company.registration_number)}'
                                   if company.registration_number else '']))
    if ids:
        header.append(ids)
    story += [Paragraph('<br/>'.join(header), small), Spacer(1, 22 * mm), Paragraph(title, heading),
              Paragraph(f'Réf. {employee.employee_id}-{timezone.localdate():%Y%m%d}',
                        ParagraphStyle('ref', parent=small, alignment=TA_CENTER)),
              Spacer(1, 14 * mm)]
    for paragraph in _letter_body(employee, kind, company):
        story.append(Paragraph(paragraph, body))
    story += [Spacer(1, 10 * mm),
              Paragraph(f'Fait à {escape(company.city or "")}, le {_long_date(timezone.localdate())}', right),
              Spacer(1, 22 * mm),
              Paragraph(f'<b>{escape(company.hr_signatory_name or "")}</b><br/>{escape(company.hr_signatory_title)}',
                        right)]
    doc.build(story)
    return buffer.getvalue()
