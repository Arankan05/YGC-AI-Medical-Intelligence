import logging
import time
from functools import lru_cache
from typing import Optional, Union

import jwt
from supabase import Client, create_client

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


class StorageError(Exception):
    """Base exception for all storage service errors."""
    pass


class StorageFileTooLargeError(StorageError):
    """Raised when an uploaded file exceeds the 25 MB size limit."""
    pass


class StorageFileNotFoundError(StorageError):
    """Raised when a requested file does not exist in storage."""
    pass


class StorageFileAlreadyExistsError(StorageError):
    """Raised when a file already exists at path and overwrite is not enabled."""
    pass


class StorageUploadError(StorageError):
    """Raised when a file upload operation fails."""
    pass


class StorageDownloadError(StorageError):
    """Raised when a file download operation fails."""
    pass


class StorageDeleteError(StorageError):
    """Raised when a file deletion operation fails."""
    pass


def _resolve_storage_key(settings: Settings) -> str:
    """
    Resolves the appropriate key for server-side private Supabase Storage operations:
    1. Returns SUPABASE_SERVICE_KEY if explicitly configured.
    2. If SUPABASE_JWT_SECRET is configured, derives a signed service_role JWT.
    3. Falls back to SUPABASE_KEY.
    """
    if settings.SUPABASE_SERVICE_KEY and settings.SUPABASE_SERVICE_KEY.strip():
        return settings.SUPABASE_SERVICE_KEY.strip()

    if settings.SUPABASE_JWT_SECRET and settings.SUPABASE_URL:
        try:
            # Extract project ref from URL (e.g. 'fkpppzbzbvrgqbkeauzv')
            project_ref = settings.SUPABASE_URL.split("://")[-1].split(".")[0]
            now = int(time.time())
            payload = {
                "iss": "supabase",
                "ref": project_ref,
                "role": "service_role",
                "iat": now,
                "exp": now + (10 * 365 * 24 * 3600),  # 10 years
            }
            derived_key = jwt.encode(payload, settings.SUPABASE_JWT_SECRET, algorithm="HS256")
            logger.info("Derived server-side service_role key from SUPABASE_JWT_SECRET for storage operations.")
            return derived_key
        except Exception as e:
            logger.debug("Could not derive service_role key: %s", type(e).__name__)

    return settings.SUPABASE_KEY


class SupabaseStorageService:
    """
    Independent service for interacting with private Supabase Storage buckets.
    Manages uploads, secure downloads, signed URL generation, and file deletion
    while ensuring credentials and raw error payloads are never leaked.
    """

    def __init__(self, settings: Optional[Settings] = None):
        self._settings = settings or get_settings()
        self._bucket_name = self._settings.SUPABASE_STORAGE_BUCKET
        self._max_file_size = self._settings.STORAGE_MAX_FILE_SIZE_BYTES

        try:
            storage_key = _resolve_storage_key(self._settings)
            self._client: Client = create_client(
                self._settings.SUPABASE_URL,
                storage_key,
            )
            self._ensure_bucket()
        except Exception as e:
            logger.error("Failed to initialize Supabase storage client: %s", type(e).__name__)
            raise StorageError("Could not initialize secure storage service connection.") from None

    def _ensure_bucket(self) -> None:
        """Ensures the configured private storage bucket exists, creating it if needed."""
        try:
            self._client.storage.get_bucket(self._bucket_name)
        except Exception:
            try:
                self._client.storage.create_bucket(
                    self._bucket_name,
                    options={"public": False},
                )
                logger.info("Created private storage bucket '%s'", self._bucket_name)
            except Exception as create_err:
                logger.debug("Bucket verification/creation status: %s", type(create_err).__name__)

    @property
    def bucket_name(self) -> str:
        """Returns the configured private storage bucket name."""
        return self._bucket_name

    @property
    def max_file_size_bytes(self) -> int:
        """Returns the maximum allowed file size in bytes (25 MB)."""
        return self._max_file_size

    def upload_file(
        self,
        file_bytes: bytes,
        storage_path: str,
        content_type: str = "application/octet-stream",
        upsert: bool = False,
    ) -> str:
        """
        Uploads binary file content to the private medical-documents bucket.

        Args:
            file_bytes: Raw binary content of the file.
            storage_path: Target path/key in the bucket (e.g. 'patient_id/document_id.pdf').
            content_type: MIME type of the document.
            upsert: Whether to overwrite if the file exists. Defaults to False.

        Returns:
            The normalized storage path of the stored file.

        Raises:
            StorageUploadError: If file is empty or upload fails.
            StorageFileTooLargeError: If file exceeds 25 MB.
            StorageFileAlreadyExistsError: If file exists and upsert is False.
        """
        if not file_bytes:
            raise StorageUploadError("Cannot upload an empty file.")

        file_size = len(file_bytes)
        if file_size > self._max_file_size:
            raise StorageFileTooLargeError(
                f"File size ({file_size} bytes) exceeds maximum permitted limit ({self._max_file_size} bytes)."
            )

        storage_path = storage_path.strip().lstrip("/")
        if not storage_path:
            raise StorageUploadError("Invalid or empty storage path specified.")

        logger.info(
            "Executing storage UPLOAD (bucket=%s, path=%s, size=%d bytes, content_type=%s, upsert=%s)",
            self._bucket_name,
            storage_path,
            file_size,
            content_type,
            upsert,
        )

        try:
            if not upsert and self.exists(storage_path):
                raise StorageFileAlreadyExistsError(
                    f"A file already exists at '{storage_path}'. Set upsert=True to overwrite."
                )

            from storage3.types import FileOptions
            file_options: FileOptions = {
                "content-type": content_type,
                "upsert": "true" if upsert else "false",
            }

            self._client.storage.from_(self._bucket_name).upload(
                path=storage_path,
                file=file_bytes,
                file_options=file_options,
            )
            logger.info("Storage UPLOAD succeeded for path '%s'", storage_path)
            return storage_path

        except (StorageFileTooLargeError, StorageFileAlreadyExistsError, StorageUploadError):
            raise
        except Exception as e:
            logger.error(
                "Storage UPLOAD failed for bucket '%s', path '%s': %s (%s)",
                self._bucket_name,
                storage_path,
                type(e).__name__,
                getattr(e, "message", str(e)),
            )
            raise StorageUploadError("Failed to upload document to storage.") from None

    def download_file(self, storage_path: str) -> bytes:
        """
        Downloads binary content of a private file from the bucket.

        Args:
            storage_path: Path/key of the file in the bucket.

        Returns:
            Raw bytes of the requested document.

        Raises:
            StorageFileNotFoundError: If file is not found.
            StorageDownloadError: If download fails.
        """
        storage_path = storage_path.strip().lstrip("/")
        if not storage_path:
            raise StorageDownloadError("Invalid or empty storage path specified.")

        logger.info(
            "Executing storage DOWNLOAD (bucket=%s, path=%s)",
            self._bucket_name,
            storage_path,
        )

        try:
            data = self._client.storage.from_(self._bucket_name).download(storage_path)
            if data is None:
                raise StorageFileNotFoundError(f"File '{storage_path}' not found in storage.")
            logger.info("Storage DOWNLOAD succeeded for path '%s' (%d bytes)", storage_path, len(data))
            return data
        except StorageFileNotFoundError:
            raise
        except Exception as e:
            logger.error(
                "Storage DOWNLOAD failed for bucket '%s', path '%s': %s",
                self._bucket_name,
                storage_path,
                type(e).__name__,
            )
            raise StorageDownloadError("Failed to download document from storage.") from None

    def delete_file(self, storage_path: str) -> bool:
        """
        Deletes a private file from the storage bucket.

        Args:
            storage_path: Path/key of the file to delete.

        Returns:
            True if deletion was successfully executed.

        Raises:
            StorageDeleteError: If delete operation fails.
        """
        storage_path = storage_path.strip().lstrip("/")
        if not storage_path:
            raise StorageDeleteError("Invalid or empty storage path specified.")

        logger.info(
            "Executing storage DELETE (bucket=%s, path=%s)",
            self._bucket_name,
            storage_path,
        )

        try:
            self._client.storage.from_(self._bucket_name).remove([storage_path])
            logger.info("Storage DELETE succeeded for path '%s'", storage_path)
            return True
        except Exception as e:
            logger.error(
                "Storage DELETE failed for bucket '%s', path '%s': %s",
                self._bucket_name,
                storage_path,
                type(e).__name__,
            )
            raise StorageDeleteError("Failed to delete document from storage.") from None

    def get_signed_url(self, storage_path: str, expires_in_seconds: int = 3600) -> str:
        """
        Generates a secure, time-limited signed URL for authorized access to a private document.

        Args:
            storage_path: Path/key of the file in the bucket.
            expires_in_seconds: URL expiration window in seconds (default: 3600s / 1 hour).

        Returns:
            Secure signed URL string.

        Raises:
            StorageError: If signed URL generation fails.
        """
        storage_path = storage_path.strip().lstrip("/")
        if not storage_path:
            raise StorageError("Invalid or empty storage path specified.")

        try:
            result = self._client.storage.from_(self._bucket_name).create_signed_url(
                path=storage_path,
                expires_in=expires_in_seconds,
            )
            signed_url = result.get("signedURL") or result.get("signedUrl")
            if not signed_url:
                raise StorageError("Signed URL was not returned by storage service.")
            return signed_url
        except StorageError:
            raise
        except Exception as e:
            logger.error("Failed to generate signed URL for path '%s': %s", storage_path, type(e).__name__)
            raise StorageError("Could not generate secure access URL for document.") from None

    def exists(self, storage_path: str) -> bool:
        """
        Checks whether a file exists in the private storage bucket.

        Args:
            storage_path: Path/key of the file to check.

        Returns:
            True if file exists, False otherwise.
        """
        storage_path = storage_path.strip().lstrip("/")
        if not storage_path:
            return False

        try:
            folder = "/".join(storage_path.split("/")[:-1]) if "/" in storage_path else ""
            filename = storage_path.split("/")[-1]
            files = self._client.storage.from_(self._bucket_name).list(folder)
            return any(f.get("name") == filename for f in files if isinstance(f, dict))
        except Exception:
            return False


@lru_cache
def get_storage_service() -> SupabaseStorageService:
    """
    Returns a cached singleton instance of SupabaseStorageService.
    """
    return SupabaseStorageService()
