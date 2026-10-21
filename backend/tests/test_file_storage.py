
import asyncio

import pytest
from fastapi import HTTPException, UploadFile
from starlette.datastructures import Headers

from app import file_storage


class ChunkedUpload(UploadFile):
    """Upload test double that returns controlled chunks."""

    def __init__(self, filename, content_type, chunks):
        super().__init__(
            file=None,
            filename=filename,
            headers=Headers({"content-type": content_type}),
        )
        self.chunks = list(chunks)
        self.closed_by_test = False

    async def read(self, size=-1):
        if not self.chunks:
            return b""
        return self.chunks.pop(0)

    async def close(self):
        self.closed_by_test = True


@pytest.fixture
def isolated_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(file_storage, "STORAGE_DIR", tmp_path)
    return tmp_path


def test_valid_utf8_text_upload_succeeds(isolated_storage):
    async def run_test():
        content = "TrustVault document — सुरक्षित".encode("utf-8")
        upload = ChunkedUpload(
            "notes.txt",
            "text/plain",
            [content[:10], content[10:]],
        )

        storage_key, filename, size = await file_storage.save_upload(upload)

        assert filename == "notes.txt"
        assert size == len(content)
        assert len(storage_key) == 32
        assert (isolated_storage / storage_key).read_bytes() == content
        assert upload.closed_by_test

    asyncio.run(run_test())


def test_invalid_utf8_after_first_32_bytes_is_rejected(isolated_storage):
    async def run_test():
        content = b"A" * 40 + b"\xff"
        upload = ChunkedUpload("notes.txt", "text/plain", [content])

        with pytest.raises(HTTPException) as exc:
            await file_storage.save_upload(upload)

        assert exc.value.status_code == 415
        assert list(isolated_storage.iterdir()) == []
        assert upload.closed_by_test

    asyncio.run(run_test())


def test_null_byte_after_first_32_bytes_is_rejected(isolated_storage):
    async def run_test():
        content = b"A" * 40 + b"\x00" + b"B"
        upload = ChunkedUpload("notes.txt", "text/plain", [content])

        with pytest.raises(HTTPException) as exc:
            await file_storage.save_upload(upload)

        assert exc.value.status_code == 415
        assert list(isolated_storage.iterdir()) == []
        assert upload.closed_by_test

    asyncio.run(run_test())


def test_empty_text_upload_is_rejected(isolated_storage):
    async def run_test():
        upload = ChunkedUpload("empty.txt", "text/plain", [])

        with pytest.raises(HTTPException) as exc:
            await file_storage.save_upload(upload)

        assert exc.value.status_code == 415
        assert list(isolated_storage.iterdir()) == []

    asyncio.run(run_test())


def test_invalid_pdf_signature_is_rejected(isolated_storage):
    async def run_test():
        upload = ChunkedUpload(
            "fake.pdf",
            "application/pdf",
            [b"This is not a PDF"],
        )

        with pytest.raises(HTTPException) as exc:
            await file_storage.save_upload(upload)

        assert exc.value.status_code == 415
        assert list(isolated_storage.iterdir()) == []

    asyncio.run(run_test())


def test_unsupported_extension_is_rejected(isolated_storage):
    async def run_test():
        upload = ChunkedUpload(
            "script.exe",
            "application/octet-stream",
            [b"MZ fake executable"],
        )

        with pytest.raises(HTTPException) as exc:
            await file_storage.save_upload(upload)

        assert exc.value.status_code == 415
        assert list(isolated_storage.iterdir()) == []

    asyncio.run(run_test())


def test_upload_exceeding_size_limit_is_rejected(
    isolated_storage,
    monkeypatch,
):
    async def run_test():
        monkeypatch.setattr(file_storage, "MAX_FILE_SIZE", 16)

        upload = ChunkedUpload(
            "large.txt",
            "text/plain",
            [b"A" * 10, b"B" * 7],
        )

        with pytest.raises(HTTPException) as exc:
            await file_storage.save_upload(upload)

        assert exc.value.status_code == 413
        assert list(isolated_storage.iterdir()) == []
        assert upload.closed_by_test

    asyncio.run(run_test())
