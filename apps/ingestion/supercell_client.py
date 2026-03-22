import logging

import httpx

from .config import COC_API_TOKEN, COC_BASE_URL

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(30.0)


def _encode_tag(tag: str) -> str:
    from urllib.parse import quote

    return quote(tag, safe="")


def _client() -> httpx.Client:
    if not (COC_API_TOKEN or "").strip():
        raise RuntimeError(
            "ingestion.unconfigured: set COC_API_TOKEN before calling the Clash of Clans API."
        )
    headers = {"Authorization": f"Bearer {COC_API_TOKEN}", "Accept": "application/json"}
    return httpx.Client(base_url=COC_BASE_URL, headers=headers, timeout=_TIMEOUT)


def _raise_for_status(resp: httpx.Response, *, endpoint: str, resource_id: str) -> None:
    try:
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        preview = (exc.response.text or "")[:500]
        logger.error(
            "CoC API HTTP error",
            extra={
                "event": "coc.http.error",
                "endpoint": endpoint,
                "resource_id": resource_id,
                "status_code": exc.response.status_code,
                "body_preview": preview,
            },
        )
        raise


def get_clan(client: httpx.Client, tag: str) -> dict | None:
    resp = client.get(f"/clans/{_encode_tag(tag)}")
    if resp.status_code == 404:
        logger.warning(
            "Clan not found",
            extra={"event": "coc.clan.not_found", "clan_tag": tag},
        )
        return None
    _raise_for_status(resp, endpoint="get_clan", resource_id=tag)
    return resp.json()


def get_current_war(client: httpx.Client, tag: str) -> dict | None:
    resp = client.get(f"/clans/{_encode_tag(tag)}/currentwar")
    if resp.status_code in (404, 403):
        logger.info(
            "War data unavailable",
            extra={
                "event": "coc.war.unavailable",
                "clan_tag": tag,
                "status_code": resp.status_code,
            },
        )
        return None
    _raise_for_status(resp, endpoint="get_current_war", resource_id=tag)
    data = resp.json()
    if data.get("state") == "notInWar":
        return None
    return data


def get_capital_raids(client: httpx.Client, tag: str, limit: int = 5) -> list[dict]:
    resp = client.get(f"/clans/{_encode_tag(tag)}/capitalraidseasons", params={"limit": limit})
    if resp.status_code in (404, 403):
        logger.info(
            "Capital raid data unavailable",
            extra={"event": "coc.raids.unavailable", "clan_tag": tag, "status_code": resp.status_code},
        )
        return []
    _raise_for_status(resp, endpoint="get_capital_raids", resource_id=tag)
    return resp.json().get("items", [])


def get_player(client: httpx.Client, tag: str) -> dict | None:
    resp = client.get(f"/players/{_encode_tag(tag)}")
    if resp.status_code == 404:
        logger.warning(
            "Player not found",
            extra={"event": "coc.player.not_found", "player_tag": tag},
        )
        return None
    _raise_for_status(resp, endpoint="get_player", resource_id=tag)
    return resp.json()


def create_client() -> httpx.Client:
    return _client()
