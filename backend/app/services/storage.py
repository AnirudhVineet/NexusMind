import asyncio
from pathlib import Path

from app.core.config import get_settings
from app.core.exceptions import ValidationError


class StorageService:
    def __init__(self) -> None:
        self.base = Path(get_settings().storage_dir).resolve()

    def _path(self, key: str) -> Path:
        target = (self.base / key).resolve()
        try:
            target.relative_to(self.base)
        except ValueError as e:
            raise ValidationError(f"Invalid storage key: {key}") from e
        return target

    async def ensure_bucket(self) -> None:
        def _mk():
            self.base.mkdir(parents=True, exist_ok=True)

        await asyncio.to_thread(_mk)

    async def upload(self, key: str, data: bytes, content_type: str) -> str:
        def _put():
            target = self._path(key)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)

        await asyncio.to_thread(_put)
        return key

    async def download(self, key: str) -> bytes:
        def _get():
            return self._path(key).read_bytes()

        return await asyncio.to_thread(_get)

    async def delete(self, key: str) -> None:
        def _del():
            try:
                self._path(key).unlink()
            except FileNotFoundError:
                pass

        await asyncio.to_thread(_del)

    async def exists(self, key: str) -> bool:
        def _check():
            return self._path(key).exists()

        return await asyncio.to_thread(_check)


def get_storage() -> StorageService:
    return StorageService()
