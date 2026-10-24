import io
import logging
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, status
from pypdf import PdfReader, PdfWriter
from reportlab.lib import colors
from reportlab.pdfgen import canvas

from app.models import Document, User

logger = logging.getLogger(__name__)


def generate_watermarked_pdf(
    source_path: Path,
    viewer: User,
    document: Document,
    is_download: bool = True,
) -> bytes:
    """
    Generate a viewer-specific watermarked PDF in memory.

    Requirements:
    - Preserves original uploaded file unchanged in private storage.
    - Watermark contains:
        1. Authenticated viewer's email and name
        2. UTC generation timestamp explicitly marked as UTC
        3. Document ID and trace reference
        4. Confidentiality notice
    - Uses approximately two low-opacity diagonal placements per page.
    - Dynamically matches each page's dimensions (portrait or landscape).
    - Fails closed on encrypted, malformed, or unsupported PDFs.
    """
    if not source_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source document file not found",
        )

    try:
        # Read the original PDF
        with open(source_path, "rb") as f:
            pdf_bytes = f.read()

        reader = PdfReader(io.BytesIO(pdf_bytes))

        if reader.is_encrypted:
            logger.warning(
                "Document %d is encrypted and cannot be watermarked safely.",
                document.id,
            )
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Encrypted documents cannot be watermarked safely.",
            )

        total_pages = len(reader.pages)
        if total_pages == 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="PDF document contains no valid pages.",
            )

        writer = PdfWriter()

        # Watermark metadata
        utc_timestamp_str = datetime.now(timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S UTC"
        )
        trace_ref = f"TRC-{document.id}-{uuid4().hex[:8].upper()}"
        viewer_identity = f"{viewer.name} ({viewer.email})" if viewer.name else f"{viewer.email}"
        action_label = "DOWNLOADED COPY" if is_download else "VIEWER STREAM"

        # Apply watermark to every page matching individual page dimensions
        for page_idx, page in enumerate(reader.pages):
            width = float(page.mediabox.width)
            height = float(page.mediabox.height)

            # Generate in-memory watermark overlay for this page size
            wm_buffer = io.BytesIO()
            can = canvas.Canvas(wm_buffer, pagesize=(width, height))

            # Restrained, subtle styling (low opacity ~0.18, dark slate color)
            can.setFillColor(colors.Color(0.25, 0.28, 0.35, alpha=0.18))

            # Placement 1: Upper diagonal
            can.saveState()
            can.setFont("Helvetica-Bold", 12)
            can.translate(width * 0.5, height * 0.70)
            can.rotate(32)
            can.drawCentredString(
                0,
                12,
                f"TRUSTVAULT SECURE • {viewer_identity} • {action_label}",
            )
            can.setFont("Helvetica", 9)
            can.drawCentredString(
                0,
                -4,
                f"Generated: {utc_timestamp_str} • Ref: {trace_ref} • Page {page_idx + 1}/{total_pages}",
            )
            can.restoreState()

            # Placement 2: Lower diagonal
            can.saveState()
            can.setFont("Helvetica-Bold", 12)
            can.translate(width * 0.5, height * 0.30)
            can.rotate(32)
            can.drawCentredString(
                0,
                12,
                f"CONFIDENTIAL • FOR AUTHORIZED USE ONLY • {viewer_identity}",
            )
            can.setFont("Helvetica", 9)
            can.drawCentredString(
                0,
                -4,
                f"Doc #{document.id}: {document.title[:40]} • {utc_timestamp_str}",
            )
            can.restoreState()

            can.showPage()
            can.save()

            # Merge the watermark onto the original page
            wm_reader = PdfReader(io.BytesIO(wm_buffer.getvalue()))
            page.merge_page(wm_reader.pages[0])
            writer.add_page(page)

        output_stream = io.BytesIO()
        writer.write(output_stream)
        return output_stream.getvalue()

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "Failed to watermark document %d for user %d: %s",
            document.id,
            viewer.id,
            exc,
            exc_info=True,
        )
        # Fail closed: never return the unwatermarked original to a shared viewer
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The document could not be processed for watermarked delivery.",
        ) from exc
