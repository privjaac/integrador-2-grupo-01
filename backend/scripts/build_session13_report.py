"""Genera un resumen reproducible de las verificaciones de la sesión 13."""

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether,
)


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / 'output' / 'pdf' / 'elisa_evidencia_sesion_13.pdf'
OUTPUT.parent.mkdir(parents=True, exist_ok=True)

navy = colors.HexColor('#17324d')
teal = colors.HexColor('#087e8b')
light = colors.HexColor('#edf4f6')
styles = getSampleStyleSheet()
styles.add(ParagraphStyle(
    name='ReportTitle', parent=styles['Title'], fontName='Helvetica-Bold',
    fontSize=18, leading=22, textColor=navy, spaceAfter=8,
))
styles.add(ParagraphStyle(
    name='ReportSub', parent=styles['Normal'], fontName='Helvetica',
    fontSize=10, leading=14, textColor=colors.HexColor('#526477'),
    spaceAfter=16,
))
styles.add(ParagraphStyle(
    name='Section', parent=styles['Heading2'], fontName='Helvetica-Bold',
    fontSize=11, leading=14, textColor=teal, spaceBefore=12, spaceAfter=6,
))
styles.add(ParagraphStyle(
    name='SmallReport', parent=styles['Normal'], fontSize=8.7, leading=12,
    spaceAfter=5,
))
styles.add(ParagraphStyle(
    name='TableReport', parent=styles['Normal'], fontSize=8.1, leading=11,
))
styles.add(ParagraphStyle(
    name='TableHeader', parent=styles['TableReport'], fontName='Helvetica-Bold',
    textColor=colors.white,
))
styles.add(ParagraphStyle(
    name='Evidence', parent=styles['Normal'], fontName='Courier',
    fontSize=8, leading=11, textColor=navy,
))
styles.add(ParagraphStyle(
    name='Footer', parent=styles['Normal'], fontSize=8, alignment=TA_CENTER,
    textColor=colors.HexColor('#617284'),
))

doc = SimpleDocTemplate(
    str(OUTPUT), pagesize=(21 * cm, 29.7 * cm),
    leftMargin=2 * cm, rightMargin=2 * cm,
    topMargin=1.7 * cm, bottomMargin=1.7 * cm,
)


def p(text, style='SmallReport'):
    return Paragraph(text, styles[style])


story = [
    p('ELISA | Evidencia de seguridad - sesión 13', 'ReportTitle'),
    p('Implementación equivalente en FastAPI + Django ORM + PostgreSQL. '
      'Las guías describen Spring Boot; este proyecto utiliza otra pila.', 'ReportSub'),
    p('Controles implementados', 'Section'),
]

rows = [
    [p('Requisito', 'TableHeader'), p('Evidencia en ELISA', 'TableHeader')],
    [p('Contraseñas BCrypt', 'TableReport'),
     p('Alta y actualización de colaboradores guardan únicamente el hash; '
       'la API nunca devuelve password_hash.', 'TableReport')],
    [p('JWT y roles', 'TableReport'),
     p('Login emite access y refresh JWT; rutas privadas exigen Bearer. '
       'Los permisos L1-L5 se verifican en los endpoints.', 'TableReport')],
    [p('XSS y validación', 'TableReport'),
     p('DTO Pydantic rechaza HTML, entidades codificadas y campos obligatorios '
       'vacíos; la salida JSON escapa &lt;, &gt; y &amp;.', 'TableReport')],
    [p('CORS e inyección SQL', 'TableReport'),
     p('Orígenes, métodos y cabeceras explícitos. Las búsquedas utilizan '
       'filtros parametrizados de Django ORM.', 'TableReport')],
]
table = Table(rows, colWidths=[4.0 * cm, 13.0 * cm], repeatRows=1, hAlign='LEFT')
table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), navy),
    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, light]),
    ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#c7d4dc')),
    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ('LEFTPADDING', (0, 0), (-1, -1), 8),
    ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ('TOPPADDING', (0, 0), (-1, -1), 7),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
]))
story += [table, Spacer(1, 7), p('Resultados verificados', 'Section')]

evidence = Table([[
    p('Comando: python manage.py test clients --settings=core.test_settings --noinput<br/>'
      'Resultado: Ran 11 tests ... OK<br/>'
      'PostgreSQL local: bcrypt=True; longitud del hash=60<br/>'
      'Casos: XSS=422; sin token=401; rol insuficiente=403; '
      'CORS externo=sin ACAO; búsqueda SQLi=lista vacía', 'Evidence')
]], colWidths=[17.0 * cm])
evidence.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, -1), light),
    ('BOX', (0, 0), (-1, -1), 0.7, teal),
    ('LEFTPADDING', (0, 0), (-1, -1), 10),
    ('TOPPADDING', (0, 0), (-1, -1), 9),
    ('BOTTOMPADDING', (0, 0), (-1, -1), 9),
]))
story += [evidence, Spacer(1, 8)]

story += [
    p('Interpretación OWASP', 'Section'),
    p('El control de acceso basado en roles reduce el riesgo de operaciones '
      'no autorizadas; BCrypt protege las contraseñas almacenadas frente a '
      'exposición directa; la validación y codificación de salida reducen '
      'la superficie de XSS; y las consultas parametrizadas del ORM evitan '
      'que el texto de búsqueda se ejecute como SQL. Estas pruebas no sustituyen '
      'una auditoría de seguridad ni demuestran protección total.'),
    p('Alcance y reproducibilidad', 'Section'),
    p('Las 11 pruebas usan una base SQLite aislada para no alterar PostgreSQL. '
      'Se verificó por separado en la base PostgreSQL local que el hash del '
      'administrador usa el prefijo BCrypt y mide 60 caracteres. No se muestra '
      'el hash completo ni ningún token o contraseña. No se ha hecho commit o push.'),
    p('Fuentes: Ficha de Trabajo sesion13.docx; taller_Sesion13.docx; '
      'backend/clients/tests.py.', 'Footer'),
]

doc.build(story)
print(OUTPUT)
