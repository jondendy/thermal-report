import os
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_CENTER, TA_LEFT

# ===== USER: Place actual image file paths below =====
THERMAL_IMG_PATH = "thermal_sample.jpg"      # Place a real sample image for real output
VISIBLE_IMG_PATH = "visible_sample.jpg"      # Place a real sample image for real output
LOGO_IMG_PATH = "logo_sample.jpg"            # Optional, for logo

# ===== Sample Data =====
PROPERTY_ADDRESS = "123 Main Street, Chesham"
SURVEY_DATE = "2025-11-13"
INSPECTOR_NAME = "Jon Andrew"
COMPANY_LOGO_PATH = LOGO_IMG_PATH
EXEC_SUMMARY = "The thermal inspection identified several minor and one significant anomaly. No major safety issues detected."
FINDINGS = [
    {
        "title": "Thermal bridge detected at window frame",
        "description": "Temperature differential around window frame suggests possible thermal bridge. Recommend insulation retrofit.",
        "thermal_image": THERMAL_IMG_PATH,
        "visible_image": VISIBLE_IMG_PATH,
        "max_temp": "21.2°C",
        "min_temp": "12.8°C",
        "severity": "Medium"
    },
    {
        "title": "Heat loss at loft hatch",
        "description": "Elevated infrared readings at loft hatch indicate potential air leakage or poor insulation.",
        "thermal_image": THERMAL_IMG_PATH,
        "visible_image": VISIBLE_IMG_PATH,
        "max_temp": "22.0°C",
        "min_temp": "14.3°C",
        "severity": "High"
    }
]
RECOMMENDATIONS = [
    "Improve insulation around window frames to eliminate thermal bridges.",
    "Seal and insulate loft hatch to reduce heat loss."
]
TECHNICAL_DETAILS = [
    ["Camera Model", "FLIR E6"],
    ["Resolution", "160 x 120"],
    ["Temperature Range", "-20°C to 250°C"],
    ["Survey Time", "45 min"],
    ["Ambient Temperature", "13°C"]
]

STYLES = getSampleStyleSheet()
TITLE_STYLE = STYLES["Title"]
HEADER_STYLE = ParagraphStyle(
    'HeaderStyle', fontSize=12, leading=14, alignment=TA_CENTER, spaceAfter=10, textColor=colors.darkblue)
FOOTER_STYLE = ParagraphStyle(
    'FooterStyle', fontSize=9, alignment=TA_CENTER, textColor=colors.grey)
SUMMARY_STYLE = ParagraphStyle(
    'SummaryStyle', fontSize=11, leading=13, alignment=TA_LEFT, spaceAfter=10)
FINDING_TITLE_STYLE = ParagraphStyle(
    'FindingTitleStyle', fontSize=12, leading=15, alignment=TA_LEFT, spaceAfter=6, textColor=colors.red)
FINDING_DESC_STYLE = STYLES["BodyText"]
RECOMMEND_STYLE = ParagraphStyle(
    'RecommendStyle', fontSize=11, leading=13, alignment=TA_LEFT, spaceAfter=6, textColor=colors.green)

# Add header & footer to each page
def header_footer(canvas, doc):
    canvas.saveState()
    width, height = A4
    header_text = f"Thermal Survey Report - {PROPERTY_ADDRESS}"
    footer_text = f"Page {doc.page}"
    canvas.setFont("Helvetica-Bold", 10)
    canvas.drawCentredString(width / 2, height - 15, header_text)
    canvas.setFont("Helvetica", 8)
    canvas.drawCentredString(width / 2, 15, footer_text)
    canvas.restoreState()

# Cover page construction
def create_cover(story):
    if os.path.isfile(COMPANY_LOGO_PATH):
        logo = Image(COMPANY_LOGO_PATH, width=60, height=60)
        story.append(logo)
    story.append(Spacer(1, 20))
    story.append(Paragraph("Thermal Survey Report", TITLE_STYLE))
    story.append(Spacer(1, 8))
    info_table = Table([
        ["Property Address:", PROPERTY_ADDRESS],
        ["Survey Date:", SURVEY_DATE],
        ["Inspector:", INSPECTOR_NAME]
    ], colWidths=[110, 280])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('TEXTCOLOR', (0,0), (0,-1), colors.black),
        ('FONTSIZE', (0,0),(-1,-1),11),
        ('BOTTOMPADDING', (0,0),(-1,-1),6)]))
    story.append(info_table)
    story.append(Spacer(1, 20))
    story.append(Paragraph("Professional building inspection survey conducted using a FLIR infrared camera.", SUMMARY_STYLE))
    story.append(PageBreak())

# Executive summary construction
def create_summary(story):
    story.append(Paragraph("Executive Summary", HEADER_STYLE))
    story.append(Spacer(1, 6))
    story.append(Paragraph(EXEC_SUMMARY, SUMMARY_STYLE))
    stats_table = Table([
        ["Number of findings", str(len(FINDINGS))],
        ["Highest anomaly severity", max(f['severity'] for f in FINDINGS)],
        ["Survey duration", "45 min"]], colWidths=[140, 140])
    stats_table.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),colors.whitesmoke),
        ('TEXTCOLOR',(0,0),(-1,-1),colors.black),
        ('FONTSIZE',(0,0),(-1,-1),11),
        ('BOTTOMPADDING',(0,0),(-1,-1),6)]))
    story.append(stats_table)
    story.append(PageBreak())

# Findings section construction
def create_findings(story):
    story.append(Paragraph("Survey Findings", HEADER_STYLE))
    story.append(Spacer(1,10))
    for finding in FINDINGS:
        story.append(Paragraph(finding['title'], FINDING_TITLE_STYLE))
        story.append(Spacer(1,3))
        story.append(Paragraph(finding['description'], FINDING_DESC_STYLE))
        story.append(Spacer(1,5))
        images_row = []
        if os.path.isfile(finding['thermal_image']):
            images_row.append(Image(finding['thermal_image'], width=120, height=80))
        if os.path.isfile(finding['visible_image']):
            images_row.append(Image(finding['visible_image'], width=120, height=80))
        if images_row:
            img_table = Table([images_row], colWidths=[130, 130])
            img_table.setStyle(TableStyle([
                ('ALIGN',(0,0),(-1,-1),'CENTER'),
                ('VALIGN',(0,0),(-1,-1),'MIDDLE')]))
            story.append(img_table)
        details_table = Table([
            ["Max Temperature", finding['max_temp']],
            ["Min Temperature", finding['min_temp']],
            ["Severity", finding['severity']]
        ], colWidths=[110, 110])
        details_table.setStyle(TableStyle([
            ('FONTSIZE',(0,0),(-1,-1),10),
            ('BOTTOMPADDING',(0,0),(-1,-1),6)]))
        story.append(details_table)
        story.append(Spacer(1, 12))
    story.append(PageBreak())

# Technical details table
def create_technical_details(story):
    story.append(Paragraph("Technical Survey Details", HEADER_STYLE))
    tech_table = Table(TECHNICAL_DETAILS, colWidths=[120, 200])
    tech_table.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),colors.lightgrey),
        ('FONTSIZE',(0,0),(-1,-1),10),
        ('BOTTOMPADDING',(0,0),(-1,-1),5)]))
    story.append(tech_table)
    story.append(PageBreak())

# Recommendations
def create_recommendations(story):
    story.append(Paragraph("Recommendations", HEADER_STYLE))
    for rec in RECOMMENDATIONS:
        story.append(Paragraph(rec, RECOMMEND_STYLE))
    story.append(PageBreak())

# Main routine
def generate_pdf(output_file):
    story = []
    create_cover(story)
    create_summary(story)
    create_findings(story)
    create_technical_details(story)
    create_recommendations(story)
    doc = SimpleDocTemplate(
        output_file,
        pagesize=A4,
        leftMargin=25,
        rightMargin=25,
        topMargin=25,
        bottomMargin=25)
    doc.build(story, onFirstPage=header_footer, onLaterPages=header_footer)

# EXAMPLE USAGE:
# generate_pdf("sample_thermal_survey.pdf")