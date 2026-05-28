from __future__ import annotations

from pathlib import Path
from typing import Any


SEVERITY_COLORS = {
    "critical": "#b91c1c",
    "high": "#c2410c",
    "medium": "#b45309",
    "low": "#15803d",
    "info": "#0369a1",
}


def render_pdf(path: Path, report: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        return _render_reportlab(path, report)
    except ModuleNotFoundError:
        return _render_minimal_pdf(path, report)


def _render_reportlab(path: Path, report: dict[str, Any]) -> Path:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(str(path), pagesize=A4, rightMargin=42, leftMargin=42, topMargin=42, bottomMargin=42)
    story = []
    summary = report["summary"]
    narrative = report["narrative"]

    story.append(Paragraph("Copilot Readiness Assessment", styles["Title"]))
    story.append(Spacer(1, 24))
    story.append(Paragraph(f"Prepared for: {summary['customer_name']}", styles["Heading2"]))
    story.append(Paragraph(f"Assessment date: {summary.get('assessment_date') or '-'}", styles["Normal"]))
    story.append(Paragraph("Prepared by: CRA Platform", styles["Normal"]))
    story.append(Spacer(1, 36))
    story.append(PageBreak())

    story.append(Paragraph("Executive Summary", styles["Heading1"]))
    story.append(Paragraph(narrative["executive_summary"], styles["BodyText"]))
    story.append(Spacer(1, 12))
    story.append(_table([
        ["Overall readiness", f"{summary['overall_readiness']}%"],
        ["Readiness status", summary["readiness_status"]],
        ["Pass / Warning / Fail", f"{summary['pass_total']} / {summary['warning_total']} / {summary['fail_total']}"],
        ["Critical / High", f"{summary['critical_findings']} / {summary['high_findings']}"],
    ]))
    story.append(Spacer(1, 12))
    story.append(Paragraph("Key Observations", styles["Heading2"]))
    for item in narrative["key_observations"]:
        story.append(Paragraph(f"• {item}", styles["BodyText"]))
    story.append(PageBreak())

    story.append(Paragraph("Analytics & Charts", styles["Heading1"]))
    for title, rows in _analytics_tables(report["analytics"]).items():
        story.append(Paragraph(title, styles["Heading2"]))
        story.append(_table(rows))
        story.append(Spacer(1, 12))
    story.append(PageBreak())

    for service, findings in report["sections"].items():
        story.append(Paragraph(service, styles["Heading1"]))
        rows = [["Parameter", "Severity", "Finding", "Recommendation"]]
        for finding in findings:
            rows.append([
                finding["title"],
                finding["severity"].title(),
                finding["finding"],
                finding["recommendation"],
            ])
        table = Table(rows, repeatRows=1, colWidths=[120, 58, 160, 160])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d1d5db")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
        ]))
        story.append(table)
        story.append(PageBreak())

    story.append(Paragraph("Conclusion", styles["Heading1"]))
    story.append(Paragraph(narrative["conclusion"], styles["BodyText"]))
    doc.build(story)
    return path


def _table(rows: list[list[Any]]):
    from reportlab.lib import colors
    from reportlab.platypus import Table, TableStyle

    table = Table(rows)
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d1d5db")),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e5e7eb")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return table


def _analytics_tables(analytics: dict) -> dict[str, list[list[Any]]]:
    return {
        "Severity distribution": [["Severity", "Count"], *[[i["name"], i["value"]] for i in analytics["severity_distribution"]]],
        "Pillar distribution": [["Pillar", "Count"], *[[i["name"], i["value"]] for i in analytics["pillar_distribution"]]],
        "Service distribution": [["Service", "Count"], *[[i["name"], i["value"]] for i in analytics["service_distribution"]]],
        "Pass vs fail": [["Status", "Count"], *[[i["name"], i["value"]] for i in analytics["pass_fail"]]],
    }


def _render_minimal_pdf(path: Path, report: dict[str, Any]) -> Path:
    summary = report["summary"]
    narrative = report["narrative"]

    def pdf_text(value: Any) -> str:
        clean = " ".join(str(value or "-").split())
        return clean.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    def wrap_line(label: str, value: Any | None = None, width: int = 92) -> list[str]:
        text = f"{label}: {value}" if value is not None else str(label)
        words = " ".join(text.split()).split(" ")
        lines: list[str] = []
        current = ""
        for word in words:
            next_value = f"{current} {word}".strip()
            if len(next_value) > width and current:
                lines.append(current)
                current = word
            else:
                current = next_value
        if current:
            lines.append(current)
        return lines or ["-"]

    lines: list[str] = [
        "Copilot Readiness Assessment",
        "",
        f"Prepared for: {summary['customer_name']}",
        f"Assessment date: {summary.get('assessment_date') or '-'}",
        "Prepared by: CRA Platform",
        "",
        "Executive Summary",
        *wrap_line(narrative["executive_summary"]),
        "",
        f"Overall readiness: {summary['overall_readiness']}%",
        f"Readiness status: {summary['readiness_status']}",
        f"Pass / Warning / Fail: {summary['pass_total']} / {summary['warning_total']} / {summary['fail_total']}",
        f"Critical / High findings: {summary['critical_findings']} / {summary['high_findings']}",
        "",
        "Key Observations",
    ]
    for item in narrative["key_observations"]:
        lines.extend(wrap_line(f"- {item}"))
    lines.extend(["", "Recommendations"])
    for item in narrative["recommendations"]:
        lines.extend(wrap_line(f"- {item}"))
    lines.extend(["", "Analytics"])
    analytics = report["analytics"]
    for name, items in [
        ("Severity distribution", analytics["severity_distribution"]),
        ("Pillar distribution", analytics["pillar_distribution"]),
        ("Service distribution", analytics["service_distribution"]),
        ("Pass vs fail", analytics["pass_fail"]),
    ]:
        rendered = ", ".join(f"{item['name']} {item['value']}" for item in items)
        lines.extend(wrap_line(name, rendered))
    lines.extend(["", "Detailed Assessment"])
    for service, findings in report["sections"].items():
        lines.extend(["", service])
        if not findings:
            lines.append("No findings recorded.")
            continue
        for finding in findings:
            lines.extend(wrap_line(f"- {finding['title']} [{finding['severity'].title()}]", finding["finding"]))
            lines.extend(wrap_line("  Recommendation", finding["recommendation"]))
    lines.extend(["", "Conclusion", *wrap_line(narrative["conclusion"])])

    lines_per_page = 48
    page_chunks = [lines[index : index + lines_per_page] for index in range(0, len(lines), lines_per_page)] or [["No report content"]]
    font_object_id = 3
    first_page_object_id = 4
    first_content_object_id = first_page_object_id + len(page_chunks)
    page_object_ids = [first_page_object_id + index for index in range(len(page_chunks))]
    content_object_ids = [first_content_object_id + index for index in range(len(page_chunks))]

    objects: list[str] = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{' '.join(f'{object_id} 0 R' for object_id in page_object_ids)}] /Count {len(page_chunks)} >>",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    for page_id, content_id in zip(page_object_ids, content_object_ids, strict=True):
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            f"/Resources << /Font << /F1 {font_object_id} 0 R >> >> /Contents {content_id} 0 R >>"
        )
    for page_number, chunk in enumerate(page_chunks, start=1):
        commands = ["BT", "/F1 10 Tf", "50 790 Td", "14 TL"]
        for line_index, line in enumerate(chunk):
            if line_index:
                commands.append("T*")
            commands.append(f"({pdf_text(line[:110])}) Tj")
        commands.extend(["T*", f"(Page {page_number} of {len(page_chunks)}) Tj", "ET"])
        stream = "\n".join(commands)
        stream_bytes = stream.encode("latin-1", errors="replace")
        objects.append(f"<< /Length {len(stream_bytes)} >>\nstream\n{stream}\nendstream")

    pdf = b"%PDF-1.4\n"
    offsets: list[int] = [0]
    for idx, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf += f"{idx} 0 obj\n".encode("latin-1")
        pdf += obj.encode("latin-1", errors="replace")
        pdf += b"\nendobj\n"
    xref = len(pdf)
    pdf += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("latin-1")
    for offset in offsets[1:]:
        pdf += f"{offset:010d} 00000 n \n".encode("latin-1")
    pdf += (
        f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref}\n%%EOF\n"
    ).encode("latin-1")
    path.write_bytes(pdf)
    return path
