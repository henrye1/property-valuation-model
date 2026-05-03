"""Supabase Storage wrapper for the 'imports' bucket.

The only file in the API package that imports the Supabase Storage SDK.
"""
from __future__ import annotations

import re
import tempfile
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast
from uuid import UUID

if TYPE_CHECKING:
    from supabase import Client


BUCKET = "imports"

_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


def safe_filename(name: str) -> str:
    """Conservative filesystem-safe transform: keep alnum/._-, collapse runs."""
    cleaned = _SAFE_NAME.sub("_", name).strip("._-") or "file"
    return cleaned[:200]


def storage_path_for(batch_id: UUID, safe_name: str) -> str:
    return f"{batch_id}/{safe_name}"


class StorageClient:
    """Thin wrapper around supabase-py's storage_from_."""

    def __init__(self, client: Client, *, signed_url_ttl_s: int = 300) -> None:
        self._client = client
        self._ttl = signed_url_ttl_s

    def upload(self, batch_id: UUID, filename: str, data: bytes) -> str:
        """Returns the storage_path written. Filename collisions are the
        caller's responsibility (router suffixes __1/__2 before calling)."""
        safe = safe_filename(filename)
        path = storage_path_for(batch_id, safe)
        self._client.storage.from_(BUCKET).upload(
            path, data, file_options={"content-type":
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
        )
        return path

    def download(self, path: str) -> bytes:
        return self._client.storage.from_(BUCKET).download(path)

    def signed_url(self, path: str) -> str:
        """Returns a 5-minute (configurable) signed URL string."""
        # Cast to Mapping[str, Any] so the runtime key-fallback below survives
        # supabase-py's TypedDict tightening across versions.
        result = cast(
            Mapping[str, Any],
            self._client.storage.from_(BUCKET).create_signed_url(path, self._ttl),
        )
        # supabase-py returns {'signedURL': '...'} (or 'signedUrl' depending on version).
        for key in ("signedURL", "signedUrl", "signed_url"):
            if key in result:
                return str(result[key])
        raise RuntimeError(f"No signedURL in storage response: {result!r}")

    def delete_prefix(self, batch_id: UUID) -> None:
        """Delete every object under <batch_id>/. List-then-delete pattern."""
        prefix = str(batch_id)
        listing = self._client.storage.from_(BUCKET).list(prefix)
        names = [f"{prefix}/{obj['name']}" for obj in listing]
        if names:
            self._client.storage.from_(BUCKET).remove(names)


@contextmanager
def downloaded_to_tempfile(client: StorageClient, path: str) -> Iterator[Path]:
    """Context manager: download bytes from Storage to a tempfile, yield the
    Path, delete the tempfile on exit. Used by parse_worker because the
    engine's parse_workbook(path) takes a Path, not bytes."""
    data = client.download(path)
    # delete=False so we control lifecycle: yield the closed file, unlink in finally.
    tf = tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False)  # noqa: SIM115
    try:
        tf.write(data)
        tf.flush()
        tf.close()
        yield Path(tf.name)
    finally:
        Path(tf.name).unlink(missing_ok=True)


def build_client(settings: Any) -> StorageClient:
    """Construct a StorageClient from app settings.

    `settings` is duck-typed (typed as Any) to avoid a circular import with
    config.py.
    """
    from supabase import create_client
    url: str = settings.SUPABASE_URL
    key: str = settings.SUPABASE_SERVICE_ROLE_KEY.get_secret_value()
    ttl = int(settings.STORAGE_SIGNED_URL_TTL_S)
    sb = create_client(url, key)
    return StorageClient(sb, signed_url_ttl_s=ttl)
