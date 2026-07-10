import logging
import posixpath

import requests
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import Storage
from django.utils.deconstruct import deconstructible
from imagekitio import APIError, ImageKit

logger = logging.getLogger(__name__)


@deconstructible
class ImageKitStorage(Storage):
    """Django storage backend that uploads/serves media via ImageKit.io."""

    def __init__(self):
        self._client = None

    @property
    def client(self):
        if self._client is None:
            self._client = ImageKit(private_key=settings.IMAGEKIT_PRIVATE_KEY)
        return self._client

    def _save(self, name, content):
        content.seek(0)
        raw = content.read()

        folder = "/" + posixpath.dirname(name).strip("/")
        file_name = posixpath.basename(name)

        try:
            result = self.client.files.upload(
                file=raw,
                file_name=file_name,
                folder=folder,
                use_unique_file_name=False,
                overwrite_file=True,
            )
        except APIError as e:
            raise IOError(f"ImageKit upload failed for '{name}': {e}") from e

        file_path = result.file_path or f"/{name}"
        return file_path.lstrip("/")

    def _open(self, name, mode="rb"):
        response = requests.get(self.url(name))
        response.raise_for_status()
        return ContentFile(response.content, name=name)

    def exists(self, name):
        return False

    def get_available_name(self, name, max_length=None):
        return name

    def url(self, name):
        base = settings.IMAGEKIT_URL_ENDPOINT.rstrip("/")
        return f"{base}/{name.lstrip('/')}"

    def size(self, name):
        response = requests.head(self.url(name))
        return int(response.headers.get("Content-Length", 0))

    def delete(self, name):
        folder = "/" + posixpath.dirname(name).strip("/")
        file_name = posixpath.basename(name)
        try:
            results = self.client.assets.list(path=folder, search_query=f'name = "{file_name}"')
            for file_obj in results:
                if getattr(file_obj, "name", None) == file_name:
                    self.client.files.delete(file_obj.file_id)
                    return
            logger.warning(f"ImageKit delete: file not found for '{name}'")
        except APIError as e:
            logger.error(f"ImageKit delete failed for '{name}': {e}")
