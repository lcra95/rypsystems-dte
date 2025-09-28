"""
RendererWorker - PDF/HTML template rendering.

Implements document rendering including PDF generation, HTML templates,
custom styling, and branding options for document presentation.
"""

import base64
import io
from typing import Dict, Any, List, Optional, Union, BinaryIO
from datetime import datetime
from pathlib import Path
import logging

from .base import BaseWorker, WorkerResult, WorkerStatus
from ...dte.document import BaseDocument

# Optional dependencies for rendering
try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.units import mm, cm
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

try:
    from jinja2 import Environment, FileSystemLoader, Template
    JINJA2_AVAILABLE = True
except ImportError:
    JINJA2_AVAILABLE = False


logger = logging.getLogger(__name__)


class RenderFormat:
    """Supported render formats."""
    PDF = "pdf"
    HTML = "html"
    XML = "xml"
    JSON = "json"
    TEXT = "text"


class RendererWorker(BaseWorker):
    """
    Renderer worker for document visualization.

    Generates PDF and HTML representations of documents using templates
    with support for custom styling and branding.
    """

    def __init__(self, name: Optional[str] = None, config: Optional[Dict[str, Any]] = None):
        """Initialize renderer worker."""
        super().__init__(name, config)

        # Default configuration
        self.default_config = {
            'default_format': RenderFormat.PDF,
            'pdf_page_size': 'A4',
            'pdf_margins': {'top': 20, 'bottom': 20, 'left': 20, 'right': 20},  # in mm
            'template_dir': None,
            'custom_templates': {},
            'include_logo': True,
            'include_barcode': True,
            'font_family': 'Helvetica',
            'font_size': 10,
            'header_font_size': 14,
            'company_logo_path': None,
            'output_dir': None,
            'embed_fonts': False,
            'watermark': None,
            'page_numbering': True
        }

        # Merge with provided config
        self.config = {**self.default_config, **(config or {})}

        # Initialize template environment
        self.template_env = None
        if JINJA2_AVAILABLE and self.config.get('template_dir'):
            self.template_env = Environment(
                loader=FileSystemLoader(self.config['template_dir'])
            )

    def process(self, document: BaseDocument, context: Optional[Dict[str, Any]] = None) -> WorkerResult:
        """
        Render document to specified format.

        Args:
            document: Document to render
            context: Rendering context

        Returns:
            Rendering result with generated content
        """
        result = WorkerResult(
            worker_name=self.name,
            status=WorkerStatus.SUCCESS,
            document=document
        )

        try:
            # Get rendering parameters
            render_context = context or {}
            output_format = render_context.get('format', self.config['default_format'])
            output_path = render_context.get('output_path')

            # Check dependencies
            if output_format == RenderFormat.PDF and not REPORTLAB_AVAILABLE:
                result.status = WorkerStatus.ERROR
                result.add_error(
                    "missing_dependency",
                    "ReportLab is required for PDF rendering. Install with: pip install reportlab"
                )
                return result

            if output_format == RenderFormat.HTML and not JINJA2_AVAILABLE:
                result.status = WorkerStatus.WARNING
                result.add_warning(
                    "missing_dependency",
                    "Jinja2 is recommended for HTML rendering. Install with: pip install jinja2"
                )

            # Render document
            if output_format == RenderFormat.PDF:
                rendered_content = self._render_pdf(document, render_context)
                content_type = "application/pdf"
            elif output_format == RenderFormat.HTML:
                rendered_content = self._render_html(document, render_context)
                content_type = "text/html"
            elif output_format == RenderFormat.XML:
                rendered_content = self._render_xml(document, render_context)
                content_type = "application/xml"
            elif output_format == RenderFormat.JSON:
                rendered_content = self._render_json(document, render_context)
                content_type = "application/json"
            elif output_format == RenderFormat.TEXT:
                rendered_content = self._render_text(document, render_context)
                content_type = "text/plain"
            else:
                result.status = WorkerStatus.ERROR
                result.add_error("invalid_format", f"Unsupported format: {output_format}")
                return result

            # Save to file if output path specified
            if output_path:
                self._save_rendered_content(rendered_content, output_path, output_format)
                result.add_info("file_saved", f"Rendered document saved to {output_path}")

            # Store rendered content
            result.data['rendered_content'] = rendered_content
            result.data['content_type'] = content_type
            result.data['format'] = output_format
            result.data['size_bytes'] = len(rendered_content) if isinstance(rendered_content, (str, bytes)) else 0

            result.add_info("rendering_complete", f"Document rendered to {output_format.upper()}")

        except Exception as e:
            self.logger.exception(f"Error rendering document to {output_format}")
            result.status = WorkerStatus.ERROR
            result.add_error("rendering_error", f"Error rendering document: {str(e)}")

        return result

    def _render_pdf(self, document: BaseDocument, context: Dict[str, Any]) -> bytes:
        """Render document as PDF."""
        if not REPORTLAB_AVAILABLE:
            raise ImportError("ReportLab is required for PDF rendering")

        # Create PDF buffer
        buffer = io.BytesIO()

        # Get page size
        page_size = A4 if self.config['pdf_page_size'] == 'A4' else letter
        margins = self.config['pdf_margins']

        # Create document
        doc = SimpleDocTemplate(
            buffer,
            pagesize=page_size,
            topMargin=margins['top'] * mm,
            bottomMargin=margins['bottom'] * mm,
            leftMargin=margins['left'] * mm,
            rightMargin=margins['right'] * mm
        )

        # Prepare content
        story = []
        styles = getSampleStyleSheet()

        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=self.config['header_font_size'],
            fontName=self.config['font_family']
        )

        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontSize=self.config['font_size'],
            fontName=self.config['font_family']
        )

        # Document data
        datos = document.get_datos()

        # Title
        tipo_doc = self._get_document_type_name(document.get_tipo_documento())
        story.append(Paragraph(f"{tipo_doc} N° {document.get_folio()}", title_style))
        story.append(Spacer(1, 12))

        # Document information table
        doc_info = self._extract_document_info(document)
        if doc_info:
            doc_table = Table(doc_info, colWidths=[4*cm, 6*cm])
            doc_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 12),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            story.append(doc_table)
            story.append(Spacer(1, 12))

        # Parties information
        parties_info = self._extract_parties_info(document)
        if parties_info:
            parties_table = Table(parties_info, colWidths=[2*cm, 4*cm, 2*cm, 4*cm])
            parties_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            story.append(parties_table)
            story.append(Spacer(1, 12))

        # Detail items
        detail_data = self._extract_detail_data(document)
        if detail_data:
            detail_table = Table(detail_data)
            detail_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            story.append(detail_table)
            story.append(Spacer(1, 12))

        # Totals
        totals_data = self._extract_totals_data(document)
        if totals_data:
            totals_table = Table(totals_data, colWidths=[6*cm, 3*cm])
            totals_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)
            ]))
            story.append(totals_table)

        # Include TED barcode if configured and available
        if self.config['include_barcode']:
            try:
                ted_data = document.get_ted()
                if ted_data and hasattr(document, 'get_pdf417_image'):
                    story.append(Spacer(1, 12))
                    story.append(Paragraph("Timbre Electrónico:", normal_style))
                    # Note: PDF417 image integration would require additional implementation
                    story.append(Paragraph("(Código PDF417 aquí)", normal_style))
            except Exception as e:
                self.logger.warning(f"Could not include barcode: {e}")

        # Build PDF
        doc.build(story)

        # Get PDF content
        buffer.seek(0)
        pdf_content = buffer.getvalue()
        buffer.close()

        return pdf_content

    def _render_html(self, document: BaseDocument, context: Dict[str, Any]) -> str:
        """Render document as HTML."""
        # Use template if available
        template_name = context.get('template', 'document.html')

        if self.template_env:
            try:
                template = self.template_env.get_template(template_name)
                return template.render(document=document, datos=document.get_datos(), **context)
            except Exception as e:
                self.logger.warning(f"Template rendering failed: {e}, using default HTML")

        # Default HTML rendering
        html_content = self._generate_default_html(document, context)
        return html_content

    def _render_xml(self, document: BaseDocument, context: Dict[str, Any]) -> str:
        """Render document as XML."""
        return document.save_xml()

    def _render_json(self, document: BaseDocument, context: Dict[str, Any]) -> str:
        """Render document as JSON."""
        import json
        return json.dumps(document.get_datos(), indent=2, ensure_ascii=False, default=str)

    def _render_text(self, document: BaseDocument, context: Dict[str, Any]) -> str:
        """Render document as plain text."""
        datos = document.get_datos()

        lines = []
        lines.append("=" * 60)
        lines.append(f"{self._get_document_type_name(document.get_tipo_documento())} N° {document.get_folio()}")
        lines.append("=" * 60)
        lines.append("")

        # Document info
        encabezado = datos.get('Encabezado', {})
        id_doc = encabezado.get('IdDoc', {})

        lines.append("INFORMACIÓN DEL DOCUMENTO:")
        lines.append(f"Fecha Emisión: {id_doc.get('FchEmis', 'N/A')}")
        lines.append(f"Tipo: {id_doc.get('TipoDTE', 'N/A')}")
        lines.append("")

        # Parties
        emisor = encabezado.get('Emisor', {})
        receptor = encabezado.get('Receptor', {})

        lines.append("EMISOR:")
        lines.append(f"RUT: {emisor.get('RUTEmisor', 'N/A')}")
        lines.append(f"Razón Social: {emisor.get('RznSoc', 'N/A')}")
        lines.append("")

        lines.append("RECEPTOR:")
        lines.append(f"RUT: {receptor.get('RUTRecep', 'N/A')}")
        lines.append(f"Razón Social: {receptor.get('RznSocRecep', 'N/A')}")
        lines.append("")

        # Detail
        detalle = datos.get('Detalle', [])
        if not isinstance(detalle, list):
            detalle = [detalle]

        lines.append("DETALLE:")
        lines.append("-" * 60)
        for i, item in enumerate(detalle, 1):
            lines.append(f"{i}. {item.get('NmbItem', 'Sin nombre')}")
            lines.append(f"   Cantidad: {item.get('QtyItem', 0)}")
            lines.append(f"   Precio: ${item.get('PrcItem', 0):,}")
            lines.append("")

        # Totals
        totales = encabezado.get('Totales', {})
        if totales:
            lines.append("TOTALES:")
            lines.append("-" * 30)
            for key, value in totales.items():
                lines.append(f"{key}: ${value:,}" if isinstance(value, (int, float)) else f"{key}: {value}")

        return "\n".join(lines)

    def _generate_default_html(self, document: BaseDocument, context: Dict[str, Any]) -> str:
        """Generate default HTML template."""
        datos = document.get_datos()

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{self._get_document_type_name(document.get_tipo_documento())} N° {document.get_folio()}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .header {{ text-align: center; border-bottom: 2px solid #000; padding-bottom: 10px; }}
        .section {{ margin: 20px 0; }}
        .label {{ font-weight: bold; }}
        table {{ width: 100%; border-collapse: collapse; margin: 10px 0; }}
        th, td {{ border: 1px solid #ccc; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
        .totals {{ text-align: right; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{self._get_document_type_name(document.get_tipo_documento())} N° {document.get_folio()}</h1>
    </div>
"""

        # Document info
        encabezado = datos.get('Encabezado', {})
        id_doc = encabezado.get('IdDoc', {})

        html += f"""
    <div class="section">
        <h2>Información del Documento</h2>
        <p><span class="label">Fecha Emisión:</span> {id_doc.get('FchEmis', 'N/A')}</p>
        <p><span class="label">Tipo:</span> {id_doc.get('TipoDTE', 'N/A')}</p>
    </div>
"""

        # Parties
        emisor = encabezado.get('Emisor', {})
        receptor = encabezado.get('Receptor', {})

        html += f"""
    <div class="section">
        <h2>Partes</h2>
        <table>
            <tr>
                <th>Emisor</th>
                <th>Receptor</th>
            </tr>
            <tr>
                <td>
                    <strong>RUT:</strong> {emisor.get('RUTEmisor', 'N/A')}<br>
                    <strong>Razón Social:</strong> {emisor.get('RznSoc', 'N/A')}
                </td>
                <td>
                    <strong>RUT:</strong> {receptor.get('RUTRecep', 'N/A')}<br>
                    <strong>Razón Social:</strong> {receptor.get('RznSocRecep', 'N/A')}
                </td>
            </tr>
        </table>
    </div>
"""

        # Detail
        detalle = datos.get('Detalle', [])
        if not isinstance(detalle, list):
            detalle = [detalle]

        html += """
    <div class="section">
        <h2>Detalle</h2>
        <table>
            <tr>
                <th>Item</th>
                <th>Cantidad</th>
                <th>Precio</th>
                <th>Total</th>
            </tr>
"""

        for item in detalle:
            qty = int(item.get('QtyItem', 0))
            price = int(item.get('PrcItem', 0))
            total = qty * price
            html += f"""
            <tr>
                <td>{item.get('NmbItem', 'Sin nombre')}</td>
                <td>{qty}</td>
                <td>${price:,}</td>
                <td>${total:,}</td>
            </tr>
"""

        html += "</table></div>"

        # Totals
        totales = encabezado.get('Totales', {})
        if totales:
            html += """
    <div class="section totals">
        <h2>Totales</h2>
        <table style="width: 300px; margin-left: auto;">
"""
            for key, value in totales.items():
                formatted_value = f"${value:,}" if isinstance(value, (int, float)) else str(value)
                html += f"<tr><td>{key}</td><td>{formatted_value}</td></tr>"

            html += "</table></div>"

        html += """
</body>
</html>
"""
        return html

    def _extract_document_info(self, document: BaseDocument) -> List[List[str]]:
        """Extract document information for table."""
        datos = document.get_datos()
        encabezado = datos.get('Encabezado', {})
        id_doc = encabezado.get('IdDoc', {})

        info = [['Campo', 'Valor']]
        info.append(['Tipo DTE', str(id_doc.get('TipoDTE', 'N/A'))])
        info.append(['Folio', str(document.get_folio())])
        info.append(['Fecha Emisión', str(id_doc.get('FchEmis', 'N/A'))])

        return info

    def _extract_parties_info(self, document: BaseDocument) -> List[List[str]]:
        """Extract parties information for table."""
        datos = document.get_datos()
        encabezado = datos.get('Encabezado', {})
        emisor = encabezado.get('Emisor', {})
        receptor = encabezado.get('Receptor', {})

        info = [['', 'Emisor', '', 'Receptor']]
        info.append(['RUT', emisor.get('RUTEmisor', 'N/A'), 'RUT', receptor.get('RUTRecep', 'N/A')])
        info.append(['Razón Social', emisor.get('RznSoc', 'N/A'), 'Razón Social', receptor.get('RznSocRecep', 'N/A')])

        return info

    def _extract_detail_data(self, document: BaseDocument) -> List[List[str]]:
        """Extract detail data for table."""
        datos = document.get_datos()
        detalle = datos.get('Detalle', [])

        if not isinstance(detalle, list):
            detalle = [detalle]

        data = [['Item', 'Cantidad', 'Precio', 'Total']]

        for item in detalle:
            qty = int(item.get('QtyItem', 0))
            price = int(item.get('PrcItem', 0))
            total = qty * price

            data.append([
                item.get('NmbItem', 'Sin nombre'),
                str(qty),
                f"${price:,}",
                f"${total:,}"
            ])

        return data

    def _extract_totals_data(self, document: BaseDocument) -> List[List[str]]:
        """Extract totals data for table."""
        datos = document.get_datos()
        encabezado = datos.get('Encabezado', {})
        totales = encabezado.get('Totales', {})

        if not totales:
            return []

        data = []
        for key, value in totales.items():
            formatted_value = f"${value:,}" if isinstance(value, (int, float)) else str(value)
            data.append([key, formatted_value])

        return data

    def _get_document_type_name(self, tipo_dte: int) -> str:
        """Get document type name."""
        type_names = {
            33: "Factura Electrónica",
            34: "Factura No Afecta o Exenta Electrónica",
            39: "Boleta Electrónica",
            41: "Boleta No Afecta o Exenta Electrónica",
            46: "Factura de Compra Electrónica",
            52: "Guía de Despacho Electrónica",
            56: "Nota de Débito Electrónica",
            61: "Nota de Crédito Electrónica"
        }
        return type_names.get(tipo_dte, f"Documento Tipo {tipo_dte}")

    def _save_rendered_content(self, content: Union[str, bytes], output_path: str, format_type: str):
        """Save rendered content to file."""
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        if format_type == RenderFormat.PDF:
            with open(output_file, 'wb') as f:
                f.write(content)
        else:
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(content)

    def validate_config(self) -> List[str]:
        """Validate worker configuration."""
        errors = []

        # Check PDF dependencies if PDF rendering is default
        if self.config['default_format'] == RenderFormat.PDF and not REPORTLAB_AVAILABLE:
            errors.append("ReportLab is required for PDF rendering")

        # Validate template directory
        template_dir = self.config.get('template_dir')
        if template_dir and not Path(template_dir).exists():
            errors.append(f"Template directory does not exist: {template_dir}")

        # Validate output directory
        output_dir = self.config.get('output_dir')
        if output_dir and not Path(output_dir).exists():
            try:
                Path(output_dir).mkdir(parents=True, exist_ok=True)
            except Exception:
                errors.append(f"Cannot create output directory: {output_dir}")

        return errors