import os
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

def generate_pdf_report(filename, patient_data, prediction_data, disease_info):
    doc = SimpleDocTemplate(filename, pagesize=letter)
    story = []
    styles = getSampleStyleSheet()

    # Title
    title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=20, textColor=colors.HexColor("#1E293B"))
    story.append(Paragraph("MediScan AI — Screening Report", title_style))
    story.append(Spacer(1, 10))

    # Legal Disclaimer Header Banner
    disclaimer_style = ParagraphStyle('DiscStyle', parent=styles['Normal'], fontSize=8, textColor=colors.HexColor("#991B1B"))
    disclaimer_text = "<b>DISCLAIMER:</b> This tool provides an AI-assisted screening estimate based on image pattern recognition. It is not a certified diagnostic device and does not replace evaluation by a licensed medical professional."
    
    disc_table = Table([[Paragraph(disclaimer_text, disclaimer_style)]], colWidths=[500])
    disc_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#FEF2F2")),
        ('BORDER', (0,0), (-1,-1), 1, colors.HexColor("#FCA5A5")),
        ('PADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(disc_table)
    story.append(Spacer(1, 15))

    # Patient Details Table
    patient_info = [
        [Paragraph("<b>Patient Name:</b>", styles['Normal']), Paragraph(str(patient_data['name']), styles['Normal'])],
        [Paragraph("<b>Age:</b>", styles['Normal']), Paragraph(str(patient_data['age']), styles['Normal'])],
        [Paragraph("<b>Scan Category:</b>", styles['Normal']), Paragraph(prediction_data['disease'].replace('_', ' ').title(), styles['Normal'])],
    ]
    info_table = Table(patient_info, colWidths=[150, 350])
    info_table.setStyle(TableStyle([('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1"))]))
    story.append(info_table)
    story.append(Spacer(1, 15))

    # Prediction Section
    pred_color = "#16A34A" if prediction_data['is_conclusive'] else "#DC2626"
    result_text = f"<font color='{pred_color}'><b>Prediction:</b> {prediction_data['prediction']}</font><br/><b>Confidence Score:</b> {prediction_data['confidence']}%"
    story.append(Paragraph(result_text, styles['Heading2']))
    story.append(Spacer(1, 10))

    # Grad-CAM Heatmap Image
    heatmap_path = prediction_data.get('heatmap_path')
    if heatmap_path and os.path.exists(heatmap_path):
        story.append(Paragraph("<b>Grad-CAM Feature Activation Overlay:</b>", styles['Normal']))
        story.append(Spacer(1, 5))
        story.append(Image(heatmap_path, width=220, height=220))
        story.append(Spacer(1, 15))

    # Dynamic/Static Medical Information
    if disease_info:
        summary_text = f"<b>Medical Summary:</b> {disease_info.get('summary', 'N/A')}<br/><br/>" \
                       f"<b>Clinical Guidance:</b> {disease_info.get('next_steps', 'Consult a specialist.')}"
        story.append(Paragraph(summary_text, styles['Normal']))

    doc.build(story)