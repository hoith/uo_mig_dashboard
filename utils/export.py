# utils/export.py
import io
import pandas as pd
from datetime import datetime


def export_to_excel(data_dict, filename='portfolio_report.xlsx'):
    """Export multiple DataFrames to Excel."""
    output = io.BytesIO()

    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        for sheet_name, df in data_dict.items():
            if isinstance(df, pd.DataFrame) and not df.empty:
                df.to_excel(writer, sheet_name=sheet_name[:31], index=True)
            elif isinstance(df, dict):
                pd.DataFrame([df]).to_excel(writer, sheet_name=sheet_name[:31], index=False)

    return output.getvalue()


def generate_pdf_report(metrics, holdings_df, stress_results):
    """Generate a simple PDF report (requires reportlab)."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet

        output = io.BytesIO()
        doc = SimpleDocTemplate(output, pagesize=letter)
        styles = getSampleStyleSheet()
        elements = []

        # Title
        elements.append(Paragraph("Portfolio Risk Report", styles['Title']))
        elements.append(Spacer(1, 20))

        # Date
        elements.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles['Normal']))
        elements.append(Spacer(1, 20))

        # Key Metrics
        elements.append(Paragraph("Key Performance Metrics", styles['Heading2']))
        metrics_data = [[k, f"{v:.4f}" if isinstance(v, float) else str(v)] for k, v in metrics.items()]
        metrics_table = Table(metrics_data, colWidths=[200, 150])
        metrics_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
        ]))
        elements.append(metrics_table)
        elements.append(Spacer(1, 20))

        doc.build(elements)
        return output.getvalue()
    except ImportError:
        return None
