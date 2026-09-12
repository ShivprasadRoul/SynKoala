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


async def create_signed_url(bucket_and_path: str, expires_in: int = 3600) -> str:
    """Turns the internal `"{bucket}/{path}"` key `upload_object` returns (and
    `screens.image_url`/`stimuli.source_url` store) into a real, temporary
    URL a plain `<img src>` can load. The `stimuli` bucket is private (HLD
    §9, planning/03-data-model-and-infra.md's "Supabase wiring": "private,
    signed URLs") — that key alone is never fetchable by a browser, only by a
    caller holding the service-role key (`download_object`, below)."""
    key = _require_service_role_key()
    bucket, path = bucket_and_path.split("/", 1)
    url = f"{settings.supabase_storage_url}/object/sign/{bucket}/{path}"
    async with httpx.AsyncClient() as client:
        response = await client.post(
            url,
            headers={"Authorization": f"Bearer {key}"},
            json={"expiresIn": expires_in},
        )
    if response.status_code >= 400:
        raise StorageError(
            f"Supabase Storage sign failed ({response.status_code}): {response.text}"
        )
    return f"{settings.supabase_storage_url}{response.json()['signedURL']}"


async def signed_url_or_none(bucket_and_path: str | None, expires_in: int = 3600) -> str | None:
    if not bucket_and_path:
        return None
    return await create_signed_url(bucket_and_path, expires_in)


async def download_object(bucket_and_path: str) -> tuple[bytes, str]:
    """`bucket_and_path` is the `"{bucket}/{path}"` string `upload_object` returns and
    `screens.image_url` stores — the Stimulus Engine's VisionProvider needs the raw
    bytes back to actually analyze the screenshot (planning/05-stimulus-engine.md)."""
    key = _require_service_role_key()
    bucket, path = bucket_and_path.split("/", 1)
    url = f"{settings.supabase_storage_url}/object/{bucket}/{path}"
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers={"Authorization": f"Bearer {key}"})
    if response.status_code >= 400:
        raise StorageError(
            f"Supabase Storage download failed ({response.status_code}): {response.text}"
        )
    content_type = response.headers.get("content-type", "application/octet-stream")
    return response.content, content_type
