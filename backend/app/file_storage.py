import codecs
import os
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile

# Default location: backend/private_storage/.
# This directory must never be mounted as a public/static directory.
STORAGE_DIR = Path(
    os.getenv(
        "TRUSTVAULT_STORAGE_DIR",
        str(Path(__file__).resolve().parents[1] / "private_storage"),
    )
).resolve()

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

ALLOWED_TYPES = {
    ".pdf": {"application/pdf", "application/octet-stream"},
    ".txt": {"text/plain", "application/octet-stream"},
    ".png": {"image/png", "application/octet-stream"},
    ".jpg": {"image/jpeg", "application/octet-stream"},
    ".jpeg": {"image/jpeg", "application/octet-stream"},
}


def validate_file_header(extension: str, header: bytes) -> bool:
    """Check the initial signature for supported binary formats."""
    if extension == ".pdf":
        return header.startswith(b"%PDF-")
    if extension == ".png":
        return header.startswith(b"\x89PNG\r\n\x1a\n")
    if extension in {".jpg", ".jpeg"}:
        return header.startswith(b"\xff\xd8\xff")
    if extension == ".txt":
        # Full TXT content is validated incrementally while streaming.
        return b"\x00" not in header
    return False


async def save_upload(upload: UploadFile) -> tuple[str, str, int]:
    """Validate and store an upload under a random, server-generated key."""
    # Strip path separators, null bytes, and traversal sequences
    clean_name = (upload.filename or "").replace("\\", "/").rsplit("/", 1)[-1]
    clean_name = clean_name.replace("\x00", "").strip()
    if clean_name in {".", ".."} or not clean_name:
        raise HTTPException(
            status_code=415,
            detail="Invalid filename.",
        )

    filename = clean_name
    extension = Path(filename).suffix.lower()

    if not filename or extension not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=415,
            detail="Unsupported file type. Allowed: PDF, TXT, PNG, JPG.",
        )

    content_type = (upload.content_type or "").lower()
    if content_type not in ALLOWED_TYPES[extension]:
        raise HTTPException(
            status_code=415,
            detail="File extension and content type do not match.",
        )

    STORAGE_DIR.mkdir(parents=True, exist_ok=True)

    storage_key = uuid4().hex
    destination = STORAGE_DIR / storage_key
    size = 0
    header = b""
    text_decoder = (
        codecs.getincrementaldecoder("utf-8")()
        if extension == ".txt"
        else None
    )

    try:
        with destination.open("xb") as output:
            while True:
                chunk = await upload.read(64 * 1024)
                if not chunk:
                    break

                size += len(chunk)
                if size > MAX_FILE_SIZE:
                    raise HTTPException(
                        status_code=413,
                        detail="Maximum file size is 10 MB.",
                    )

                if len(header) < 32:
                    header += chunk[: 32 - len(header)]

                if extension == ".txt":
                    if b"\x00" in chunk:
                        raise HTTPException(
                            status_code=415,
                            detail="The uploaded text file contains invalid content.",
                        )
                    try:
                        # Incremental decoding validates all bytes, including
                        # multibyte UTF-8 characters split across chunks.
                        text_decoder.decode(chunk, final=False)
                    except UnicodeDecodeError as exc:
                        raise HTTPException(
                            status_code=415,
                            detail="The uploaded text file is not valid UTF-8.",
                        ) from exc

                output.write(chunk)

        if size == 0 or not validate_file_header(extension, header):
            raise HTTPException(
                status_code=415,
                detail="The uploaded file is empty or its contents are invalid.",
            )

        if text_decoder is not None:
            try:
                text_decoder.decode(b"", final=True)
            except UnicodeDecodeError as exc:
                raise HTTPException(
                    status_code=415,
                    detail="The uploaded text file is not valid UTF-8.",
                ) from exc

        return storage_key, filename, size

    except Exception:
        destination.unlink(missing_ok=True)
        raise
    finally:
        await upload.close()


def get_storage_path(storage_key: str) -> Path:
    """Resolve a server-generated storage key to an existing private file."""
    if (
        not storage_key
        or len(storage_key) != 32
        or any(char not in "0123456789abcdef" for char in storage_key)
    ):
        raise HTTPException(status_code=404, detail="File not found")

    path = STORAGE_DIR / storage_key

    if not path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    return path
