import logging

from shared.logutil import (
    get_ingestion_run_id,
    log_event,
    new_correlation_id,
    reset_ingestion_run_id_ctx,
    set_ingestion_run_id_ctx,
)

from . import supercell_client as coc
from . import db
from . import legends

logger = logging.getLogger(__name__)


def run_once() -> None:
    run_id = new_correlation_id()
    token = set_ingestion_run_id_ctx(run_id)
    try:
        _run_once_inner()
    finally:
        reset_ingestion_run_id_ctx(token)


def _run_once_inner() -> None:
    log_event(
        logger,
        "ingestion.run.start",
        "ingestion run started",
        ingestion_run_id=get_ingestion_run_id(),
    )
    tracked = db.get_tracked_clans()
    always_tags_list = db.get_tracked_player_tags()
    always_tags = set(always_tags_list)

    if not tracked and not always_tags:
        log_event(
            logger,
            "ingestion.run.empty",
            "No tracked clans or always-tracked players — nothing to ingest",
            ingestion_run_id=get_ingestion_run_id(),
        )
        return

    if tracked:
        log_event(
            logger,
            "ingestion.run.tracklist",
            f"Starting ingestion for {len(tracked)} tracked clan(s)",
            clan_count=len(tracked),
            ingestion_run_id=get_ingestion_run_id(),
        )
    if always_tags:
        log_event(
            logger,
            "ingestion.run.always_track",
            f"Always-tracking {len(always_tags)} player(s)",
            always_track_count=len(always_tags),
            ingestion_run_id=get_ingestion_run_id(),
        )

    client = coc.create_client()
    active_tags: set[str] = set(always_tags)

    try:
        for entry in tracked:
            clan_tag = entry["clan_tag"]
            log_event(
                logger,
                "ingestion.clan.start",
                f"Processing clan {clan_tag}",
                clan_tag=clan_tag,
                ingestion_run_id=get_ingestion_run_id(),
            )
            ok, member_tags = _ingest_clan(client, clan_tag)
            if ok:
                active_tags |= member_tags
            else:
                active_tags |= db.get_player_tags_for_clan(clan_tag)

        for tag in sorted(always_tags):
            player_data = coc.get_player(client, tag)
            if player_data:
                db.upsert_player(player_data)
            else:
                log_event(
                    logger,
                    "ingestion.player.always_track_skip",
                    f"Could not fetch always-tracked player {tag}",
                    player_tag=tag,
                    ingestion_run_id=get_ingestion_run_id(),
                )

        db.reconcile_tracked_roster(active_tags)

        legends.ingest_legends(client)
    finally:
        client.close()

    log_event(
        logger,
        "ingestion.run.complete",
        "Ingestion complete",
        ingestion_run_id=get_ingestion_run_id(),
    )


def _ingest_clan(client, clan_tag: str) -> tuple[bool, set[str]]:
    clan_data = coc.get_clan(client, clan_tag)
    if not clan_data:
        log_event(
            logger,
            "ingestion.clan.skip",
            f"Could not fetch clan {clan_tag}, skipping",
            clan_tag=clan_tag,
            ingestion_run_id=get_ingestion_run_id(),
        )
        return False, set()

    db.upsert_clan(clan_data)

    member_list = clan_data.get("memberList", [])
    member_tags = {m["tag"] for m in member_list}
    log_event(
        logger,
        "ingestion.players.fetch",
        f"Fetching {len(member_list)} player(s) for clan {clan_tag}",
        clan_tag=clan_tag,
        member_count=len(member_list),
        ingestion_run_id=get_ingestion_run_id(),
    )
    for member in member_list:
        player_data = coc.get_player(client, member["tag"])
        if player_data:
            db.upsert_player(player_data)

    war_data = coc.get_current_war(client, clan_tag)
    if war_data:
        war_id = db.upsert_war(war_data, clan_tag)
        if war_id:
            db.upsert_war_attacks(war_id, war_data)
    else:
        log_event(
            logger,
            "ingestion.war.none",
            f"No active war for {clan_tag}",
            clan_tag=clan_tag,
            ingestion_run_id=get_ingestion_run_id(),
        )

    resolved = db.resolve_stale_wars(clan_tag)
    if resolved:
        log_event(
            logger,
            "ingestion.war.resolved_stale",
            f"Resolved {resolved} stale war(s) for {clan_tag}",
            clan_tag=clan_tag,
            resolved_count=resolved,
            ingestion_run_id=get_ingestion_run_id(),
        )

    raids = coc.get_capital_raids(client, clan_tag, limit=5)
    log_event(
        logger,
        "ingestion.raids.fetched",
        f"Got {len(raids)} capital raid season(s) for {clan_tag}",
        clan_tag=clan_tag,
        raid_count=len(raids),
        ingestion_run_id=get_ingestion_run_id(),
    )
    for raid in raids:
        raid_id = db.upsert_capital_raid(raid, clan_tag)
        if raid_id:
            db.upsert_raid_members(raid_id, raid.get("members", []))

    return True, member_tags
