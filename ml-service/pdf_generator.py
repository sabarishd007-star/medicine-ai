import os

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

DISCLAIMER = (
    "<b>DISCLAIMER:</b> This tool provides an AI-assisted screening estimate based on image "
    "pattern recognition. It is not a certified diagnostic device and does not replace "
    "evaluation by a licensed medical professional."
)

UNTRAINED_BANNER = (
    "<b>MODEL NOT TRAINED:</b> No validated checkpoint is installed for this module. The "
    "figures below come from an untrained classification head and have NO clinical meaning. "
    "This report is a pipeline demonstration only."
)


def _banner(text, bg, border, fg):
    styles = getSampleStyleSheet()
    style = ParagraphStyle("Banner", parent=styles["Normal"], fontSize=8, textColor=colors.HexColor(fg))
    table = Table([[Paragraph(text, style)]], colWidths=[500])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(bg)),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor(border)),
                ("PADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return table


def generate_pdf_report(filename, patient_data, prediction_data, disease_info):
    doc = SimpleDocTemplate(filename, pagesize=letter, title="MediScan AI Screening Report")
    styles = getSampleStyleSheet()
    story = []

    title_style = ParagraphStyle(
        "TitleStyle", parent=styles["Heading1"], fontSize=20, textColor=colors.HexColor("#1E293B")
    )
    story.append(Paragraph("MediScan AI &mdash; Screening Report", title_style))
    story.append(Spacer(1, 10))

    story.append(_banner(DISCLAIMER, "#FEF2F2", "#FCA5A5", "#991B1B"))
    story.append(Spacer(1, 10))

    untrained = prediction_data.get("model_status") == "UNTRAINED_BACKBONE"
    if untrained:
        story.append(_banner(UNTRAINED_BANNER, "#FFF7ED", "#FDBA74", "#9A3412"))
        story.append(Spacer(1, 10))

    rows = [
        ["Patient Name", str(patient_data.get("name", "-"))],
        ["Age", str(patient_data.get("age", "-"))],
        ["Scan Category", str(prediction_data.get("disease_display", prediction_data.get("disease", "-")))],
        ["Modality", str(prediction_data.get("modality", "-"))],
        ["Analyzed At (UTC)", str(prediction_data.get("analyzed_at", "-"))],
        ["Model Status", str(prediction_data.get("model_status", "-"))],
    ]
    if patient_data.get("notes"):
        rows.append(["Clinical Notes", str(patient_data["notes"])])

    info_table = Table(
        [[Paragraph(f"<b>{k}</b>", styles["Normal"]), Paragraph(v, styles["Normal"])] for k, v in rows],
        colWidths=[150, 350],
    )
    info_table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1"))]))
    story.append(info_table)
    story.append(Spacer(1, 15))

    conclusive = prediction_data.get("is_conclusive")
    pred_color = "#16A34A" if conclusive else "#DC2626"
    result_text = (
        f"<font color='{pred_color}'><b>Prediction:</b> {prediction_data.get('prediction')}</font><br/>"
        f"<b>Confidence Score:</b> {prediction_data.get('confidence')}% "
        f"(gate: {prediction_data.get('confidence_threshold')}%)"
    )
    if prediction_data.get("stage"):
        result_text += f"<br/><b>Indicated Stage:</b> {prediction_data['stage']}"
    story.append(Paragraph(result_text, styles["Heading2"]))
    story.append(Spacer(1, 8))

    probabilities = prediction_data.get("class_probabilities") or {}
    if probabilities:
        story.append(Paragraph("<b>Class Probability Distribution</b>", styles["Normal"]))
        story.append(Spacer(1, 5))
        prob_rows = [["Class", "Probability"]] + [[k, f"{v}%"] for k, v in probabilities.items()]
        prob_table = Table(prob_rows, colWidths=[300, 200])
        prob_table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F1F5F9")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                ]
            )
        )
        story.append(prob_table)
        story.append(Spacer(1, 15))

    heatmap_path = prediction_data.get("heatmap_path")
    if heatmap_path and os.path.exists(heatmap_path):
        story.append(Paragraph("<b>Grad-CAM Feature Activation Overlay</b>", styles["Normal"]))
        story.append(Spacer(1, 5))
        story.append(Image(heatmap_path, width=220, height=220))
        coverage = prediction_data.get("gradcam_coverage")
        if coverage is not None:
            story.append(Spacer(1, 4))
            story.append(
                Paragraph(
                    f"<font size=8>Activation coverage above 0.5: {coverage:.1%} of the image. "
                    f"A highly diffuse map indicates a weak, non-localised explanation.</font>",
                    styles["Normal"],
                )
            )
        story.append(Spacer(1, 15))

    metrics = prediction_data.get("model_metrics") or {}
    if metrics.get("accuracy") is not None:
        story.append(Paragraph("<b>Measured Model Performance</b>", styles["Normal"]))
        story.append(Spacer(1, 5))
        dataset = metrics.get("dataset", {})
        rows = [
            ["Test accuracy", f"{metrics['accuracy'] * 100:.1f}%"],
            [
                "Always-guess-commonest baseline",
                f"{metrics.get('majority_class_baseline', 0) * 100:.1f}%",
            ],
            ["Macro F1", f"{metrics.get('macro_f1', 0):.3f}"],
            ["Samples evaluated", str(dataset.get("samples_evaluated", "-"))],
            ["Evaluation dataset", str(dataset.get("name", "-"))],
        ]
        table = Table(
            [[Paragraph(f"<b>{k}</b>", styles["Normal"]), Paragraph(v, styles["Normal"])] for k, v in rows],
            colWidths=[220, 280],
        )
        table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                ]
            )
        )
        story.append(table)
        story.append(Spacer(1, 10))

        safety = metrics.get("safety")
        if safety:
            story.append(
                _banner(
                    "<b>FALSE-NEGATIVE RATE:</b> On the evaluation sample this model missed "
                    f"{safety['missed_diseased_cases']} of {safety['diseased_samples']} "
                    f"diseased cases ({safety['false_negative_rate']:.1%}). Sensitivity "
                    f"{safety['sensitivity_recall']:.1%}, specificity {safety['specificity']:.1%}. "
                    "A negative or low-risk result from this tool is NOT evidence that disease "
                    "is absent and must not be used for reassurance.",
                    "#FEF2F2",
                    "#FCA5A5",
                    "#991B1B",
                )
            )
            story.append(Spacer(1, 10))
    elif prediction_data.get("model_status") == "TRAINED":
        story.append(
            _banner(
                "<b>ACCURACY NOT MEASURED:</b> This module runs a trained checkpoint, but its "
                "accuracy has not been evaluated on a labelled test set in this deployment. "
                "No performance claim is made.",
                "#FFF7ED",
                "#FDBA74",
                "#9A3412",
            )
        )
        story.append(Spacer(1, 10))

    if disease_info:
        summary_text = (
            f"<b>Medical Summary:</b> {disease_info.get('summary', 'N/A')}<br/><br/>"
            f"<b>Stage Context:</b> {disease_info.get('stage_info', 'N/A')}<br/><br/>"
            f"<b>Clinical Guidance:</b> {disease_info.get('next_steps', 'Consult a specialist.')}"
        )
        story.append(Paragraph(summary_text, styles["Normal"]))

    doc.build(story)
    return filename
