import httpx

from app.core.settings import settings


class StorageError(Exception):
    pass


def _require_service_role_key() -> str:
    if not settings.supabase_service_role_key:
        raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY is not set — required for Storage access")
    return settings.supabase_service_role_key


async def ensure_bucket(bucket: str) -> None:
    """Supabase Storage buckets aren't auto-created — this makes the stimulus upload
    path work without a manual dashboard step, per HLD §9 (private, not public)."""
    key = _require_service_role_key()
    headers = {"Authorization": f"Bearer {key}"}
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{settings.supabase_storage_url}/bucket/{bucket}", headers=headers
        )
        if response.status_code == 200:
            return
        response = await client.post(
            f"{settings.supabase_storage_url}/bucket",
            headers=headers,
            json={"id": bucket, "name": bucket, "public": False},
        )
    if response.status_code >= 400 and "already exists" not in response.text.lower():
        raise StorageError(f"Could not create Storage bucket {bucket!r}: {response.text}")


async def upload_object(bucket: str, path: str, content: bytes, content_type: str) -> str:
    key = _require_service_role_key()
    url = f"{settings.supabase_storage_url}/object/{bucket}/{path}"
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url,
            content=content,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": content_type,
                "x-upsert": "true",
            },
        )
    if response.status_code >= 400:
        raise StorageError(
            f"Supabase Storage upload failed ({response.status_code}): {response.text}"
        )
    return f"{bucket}/{path}"
