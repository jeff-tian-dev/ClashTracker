"""Infer and set is_home_attacker on legacy war_attacks rows (NULL).

CoC war rows link attacker and defender on opposite clans. We bipartite-color tags
per war, then pick which color is "home" using players.clan_tag vs wars.clan_tag /
wars.opponent_tag. Ingestion normally sets this from the API payload; this script
repairs historical rows so war_player_leaderboard_stats can see them.

Run from repo root:  PYTHONPATH=apps python -m ingestion.war_backfill
"""

from __future__ import annotations

import logging
from collections import defaultdict, deque
from typing import Any

from .db import get_db

logger = logging.getLogger(__name__)


def _connected_components(
    nodes: set[str], edges: list[tuple[str, str]]
) -> list[set[str]]:
    adj: dict[str, set[str]] = defaultdict(set)
    for a, b in edges:
        adj[a].add(b)
        adj[b].add(a)
    seen: set[str] = set()
    comps: list[set[str]] = []
    for n in nodes:
        if n in seen:
            continue
        comp: set[str] = set()
        stack = [n]
        while stack:
            t = stack.pop()
            if t in seen:
                continue
            seen.add(t)
            comp.add(t)
            for nb in adj[t]:
                if nb not in seen:
                    stack.append(nb)
        comps.append(comp)
    return comps


def _color_component(
    comp: set[str], edges: list[tuple[str, str]]
) -> dict[str, int] | None:
    """Bipartite 0/1 coloring; return None if not bipartite."""
    adj: dict[str, set[str]] = defaultdict(set)
    for a, b in edges:
        if a in comp and b in comp:
            adj[a].add(b)
            adj[b].add(a)
    color: dict[str, int] = {}
    for start in comp:
        if start in color:
            continue
        color[start] = 0
        dq: deque[str] = deque([start])
        while dq:
            t = dq.popleft()
            for nbr in adj[t]:
                want = 1 - color[t]
                if nbr in color:
                    if color[nbr] != want:
                        return None
                else:
                    color[nbr] = want
                    dq.append(nbr)
    for t in comp:
        if t not in color:
            color[t] = 0
    return color


def _home_color_for_component(
    color: dict[str, int],
    comp: set[str],
    clan_tag: str,
    opponent_tag: str | None,
    tag_to_clan: dict[str, str],
) -> int:
    """Return color value (0 or 1) that should count as home attackers."""

    def count_for_color(c: int, pred) -> int:
        return sum(1 for t in comp if color.get(t, 0) == c and pred(t))

    def is_home_clan(t: str) -> bool:
        return tag_to_clan.get(t) == clan_tag

    def is_opp_clan(t: str) -> bool:
        return bool(opponent_tag) and tag_to_clan.get(t) == opponent_tag

    h0 = count_for_color(0, is_home_clan)
    h1 = count_for_color(1, is_home_clan)
    if h0 > h1:
        return 0
    if h1 > h0:
        return 1
    o0 = count_for_color(0, is_opp_clan)
    o1 = count_for_color(1, is_opp_clan)
    if o0 > o1:
        return 1
    if o1 > o0:
        return 0
    return 0


def run_backfill() -> dict[str, int]:
    db = get_db()
    wars_touched = 0
    rows_updated = 0
    wars_skipped = 0

    wresp = (
        db.table("wars")
        .select("id, clan_tag, opponent_tag")
        .execute()
    )
    wars_by_id: dict[int, dict[str, Any]] = {int(w["id"]): w for w in (wresp.data or [])}

    all_rows: list[dict[str, Any]] = []
    batch = 1000
    start = 0
    while True:
        aresp = (
            db.table("war_attacks")
            .select("id, war_id, attacker_tag, defender_tag, is_home_attacker")
            .order("id")
            .range(start, start + batch - 1)
            .execute()
        )
        chunk = list(aresp.data or [])
        all_rows.extend(chunk)
        if len(chunk) < batch:
            break
        start += batch

    by_war: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for r in all_rows:
        by_war[int(r["war_id"])].append(r)

    for war_id, rows in by_war.items():
        null_rows = [r for r in rows if r.get("is_home_attacker") is None]
        if not null_rows:
            continue
        war = wars_by_id.get(war_id)
        if not war:
            logger.warning("war_backfill: war_id=%s missing in wars, skipping", war_id)
            wars_skipped += 1
            continue

        clan_tag = war["clan_tag"]
        opponent_tag = (war.get("opponent_tag") or "").strip() or None

        nodes: set[str] = set()
        edges: list[tuple[str, str]] = []
        for r in rows:
            a, d = r["attacker_tag"], r["defender_tag"]
            nodes.add(a)
            nodes.add(d)
            edges.append((a, d))

        tags_list = list(nodes)
        pres = (
            db.table("players")
            .select("tag, clan_tag")
            .in_("tag", tags_list)
            .execute()
        )
        tag_to_clan: dict[str, str] = {
            str(p["tag"]): str(p["clan_tag"]) for p in (pres.data or []) if p.get("tag")
        }

        tag_on_home_side: dict[str, bool] = {}
        ok = True
        for comp in _connected_components(nodes, edges):
            sub_edges = [(a, b) for a, b in edges if a in comp and b in comp]
            col = _color_component(comp, sub_edges)
            if col is None:
                logger.warning(
                    "war_backfill: non-bipartite war_id=%s component_size=%s",
                    war_id,
                    len(comp),
                )
                ok = False
                break
            home_attack_color = _home_color_for_component(
                col, comp, clan_tag, opponent_tag, tag_to_clan
            )
            for t in comp:
                tag_on_home_side[t] = col[t] == home_attack_color

        if not ok:
            wars_skipped += 1
            continue

        for r in null_rows:
            att = r["attacker_tag"]
            is_home = tag_on_home_side.get(att, False)
            db.table("war_attacks").update({"is_home_attacker": is_home}).eq(
                "id", r["id"]
            ).execute()
            rows_updated += 1
        wars_touched += 1
        logger.info(
            "war_backfill: war_id=%s updated %d null attack row(s)",
            war_id,
            len(null_rows),
        )

    return {
        "wars_updated": wars_touched,
        "rows_updated": rows_updated,
        "wars_skipped": wars_skipped,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    out = run_backfill()
    print(out)
