from pathlib import Path
from typing import Optional
import html
import docx
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from app.core.errors import AppException, AppErrorCode
from app.core.logging import logger

class FormatConverter:
    @classmethod
    def _find_soffice(cls) -> Optional[str]:
        """Locates headless LibreOffice binary if available."""
        import shutil
        for name in ["soffice", "libreoffice"]:
            path = shutil.which(name)
            if path:
                return path
        win_paths = [
            Path(r"C:\Program Files\LibreOffice\program\soffice.exe"),
            Path(r"C:\Program Files (x86)\LibreOffice\program\soffice.exe")
        ]
        for p in win_paths:
            if p.exists():
                return str(p)
        return None

    @classmethod
    def convert_docx_to_pdf(cls, docx_path: Path, output_pdf_path: Path) -> Path:
        """
        Converts a DOCX file to a PDF file.
        Uses headless LibreOffice for layout-preserving fidelity if installed;
        otherwise uses ReportLab Platypus engine preserving headers, footers, paragraphs, and tables.
        """
        if not docx_path.exists():
            raise AppException(code=AppErrorCode.DOCUMENT_NOT_FOUND, message=f"DOCX source file not found: {docx_path}")

        # 1. Attempt native layout-preserving LibreOffice conversion if installed
        soffice_bin = cls._find_soffice()
        if soffice_bin:
            try:
                import subprocess
                import shutil
                out_dir = output_pdf_path.parent
                res = subprocess.run(
                    [soffice_bin, "--headless", "--convert-to", "pdf", str(docx_path), "--outdir", str(out_dir)],
                    capture_output=True,
                    timeout=30
                )
                generated_pdf = out_dir / f"{docx_path.stem}.pdf"
                if generated_pdf.exists():
                    shutil.move(str(generated_pdf), str(output_pdf_path))
                    logger.info(f"DOCX to PDF converted with native LibreOffice fidelity: {output_pdf_path}")
                    return output_pdf_path
            except Exception as e:
                logger.warning(f"Native LibreOffice conversion failed, falling back to ReportLab: {e}")

        # 2. ReportLab structured flowable fallback with header and footer preservation
        try:
            doc = docx.Document(docx_path)

            # Extract header and footer strings from first section if present
            header_text = ""
            footer_text = ""
            if doc.sections:
                sec = doc.sections[0]
                if sec.header and sec.header.paragraphs:
                    header_text = " ".join(p.text for p in sec.header.paragraphs if p.text.strip())
                if sec.footer and sec.footer.paragraphs:
                    footer_text = " ".join(p.text for p in sec.footer.paragraphs if p.text.strip())

            def draw_page_decorations(canvas, pdf_doc):
                canvas.saveState()
                canvas.setFont('Helvetica', 8)
                canvas.setFillColor(colors.HexColor('#64748b'))
                if header_text:
                    canvas.drawString(54, pdf_doc.height + 54 + 18, header_text[:90])
                    canvas.setStrokeColor(colors.HexColor('#e2e8f0'))
                    canvas.setLineWidth(0.5)
                    canvas.line(54, pdf_doc.height + 54 + 12, pdf_doc.width + 54, pdf_doc.height + 54 + 12)
                if footer_text:
                    canvas.drawCentredString((pdf_doc.width / 2) + 54, 32, footer_text[:90])
                    canvas.setStrokeColor(colors.HexColor('#e2e8f0'))
                    canvas.setLineWidth(0.5)
                    canvas.line(54, 44, pdf_doc.width + 54, 44)
                canvas.restoreState()

            pdf = SimpleDocTemplate(
                str(output_pdf_path),
                pagesize=letter,
                rightMargin=54,
                leftMargin=54,
                topMargin=54,
                bottomMargin=54
            )

            styles = getSampleStyleSheet()
            normal_style = styles["Normal"]
            normal_style.fontSize = 11
            normal_style.leading = 15

            story = []

            for elem in doc.element.body:
                tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
                if tag == "p":
                    for p in doc.paragraphs:
                        if p._p is elem:
                            para_html = cls._paragraph_to_html(p)
                            if para_html.strip():
                                story.append(Paragraph(para_html, normal_style))
                            else:
                                story.append(Spacer(1, 8))
                            story.append(Spacer(1, 4))
                            break

                elif tag == "tbl":
                    for t in doc.tables:
                        if t._tbl is elem:
                            table_flowable = cls._table_to_flowable(t, normal_style)
                            if table_flowable:
                                story.append(table_flowable)
                                story.append(Spacer(1, 10))
                            break

            if not story:
                story.append(Paragraph("Empty Document", normal_style))

            pdf.build(story, onFirstPage=draw_page_decorations, onLaterPages=draw_page_decorations)
            return output_pdf_path

        except Exception as e:
            logger.error(f"DOCX to PDF conversion failed: {e}")
            raise AppException(
                code=AppErrorCode.GENERATION_ERROR,
                message=f"DOCX to PDF conversion failed: {str(e)}"
            )

    @classmethod
    def _paragraph_to_html(cls, paragraph) -> str:
        parts = []
        for r in paragraph.runs:
            text = html.escape(r.text)
            if not text:
                continue
            if r.bold:
                text = f"<b>{text}</b>"
            if r.italic:
                text = f"<i>{text}</i>"
            if r.underline:
                text = f"<u>{text}</u>"
            parts.append(text)
        return "".join(parts)

    @classmethod
    def _table_to_flowable(cls, table, style) -> Table:
        table_data = []
        for row in table.rows:
            row_data = []
            for cell in row.cells:
                cell_text = cell.text.strip()
                escaped = html.escape(cell_text).replace("\n", "<br/>")
                row_data.append(Paragraph(escaped, style))
            table_data.append(row_data)

        if not table_data:
            return None

        t = Table(table_data)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
            ('FONTSIZE', (0,0), (-1,-1), 10),
            ('BOTTOMPADDING', (0,0), (-1,-1), 6),
            ('TOPPADDING', (0,0), (-1,-1), 6),
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
        ]))
        return t
