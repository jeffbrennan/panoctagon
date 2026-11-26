from __future__ import annotations

import time
import os
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import text

from panoctagon.api.models import (
    DashboardMetadata,
    FighterAnalytics,
    NetworkAnalytics,
    RosterAnalytics,
)
from panoctagon.api.database import current_revision, get_read_engine

router = APIRouter(tags=["Dashboard analytics"])


@lru_cache(maxsize=64)
def _cached_rows(sql: str, params: tuple, period: int, revision: str) -> list[dict[str, Any]]:
    with get_read_engine().connect() as conn:
        return [dict(row) for row in conn.execute(text(sql), dict(params)).mappings()]


def rows(sql: str, **params: Any) -> list[dict[str, Any]]:
    return _cached_rows(sql, tuple(sorted(params.items())), int(time.monotonic() // 120), current_revision().revision)


def current_year() -> int:
    return datetime.now(timezone.utc).year


@router.get("/metadata", response_model=DashboardMetadata)
def metadata() -> dict[str, Any]:
    result = rows("""
        select (select max(substr(downloaded_ts, 1, 10)) from ufc_events) as last_refresh,
            (select count(*) from ufc_fighters) as fighters,
            (select count(*) from ufc_fights where fighter1_result is not null) as fights,
            (select min(year(cast(event_date as date))) from ufc_events) as first_year,
            (select max(year(cast(event_date as date))) from ufc_events) as last_year,
            coalesce(
                (select fighter_uid from ufc_fighters
                 where lower(first_name || ' ' || last_name) like '%max holloway%'
                 order by fighter_uid limit 1),
                (select fighter_uid from (
                    select fighter1_uid as fighter_uid from ufc_fights where fighter1_result is not null
                    union all
                    select fighter2_uid as fighter_uid from ufc_fights where fighter2_result is not null
                ) group by fighter_uid order by count(*) desc, fighter_uid limit 1),
                (select fighter_uid from ufc_fighters order by fighter_uid limit 1)
            ) as default_fighter_uid
    """)[0]
    revision = current_revision()
    return {**result, "current_year": current_year(), "revision": revision.revision if revision.published_at else None, "published_at": revision.published_at}


@router.get("/fighter/{fighter_uid}/headshot", response_class=FileResponse)
def headshot(fighter_uid: str) -> FileResponse:
    if not fighter_uid.isalnum() or len(fighter_uid) > 64:
        raise HTTPException(status_code=404, detail="Headshot not found")
    directory = Path(os.environ.get("PANOCTAGON_API_HEADSHOTS", Path(__file__).parents[2] / "data" / "raw" / "ufc" / "fighter_headshots"))
    for extension in ("png", "jpg", "jpeg", "webp"):
        path = directory / f"{fighter_uid}_headshot.{extension}"
        if path.is_file():
            return FileResponse(path, headers={"Cache-Control": "public, max-age=86400"})
    raise HTTPException(status_code=404, detail="Headshot not found")


_BIO_KEYS = (
    "fighter_uid",
    "first_name",
    "last_name",
    "full_name",
    "nickname",
    "dob",
    "place_of_birth",
    "stance",
    "style",
    "height_inches",
    "reach_inches",
    "leg_reach_inches",
)
_RECORD_KEYS = ("wins", "losses", "draws", "no_contests", "total_fights")


@router.get("/fighter/{fighter_uid}/analytics", response_model=FighterAnalytics)
def fighter_analytics(fighter_uid: str) -> dict[str, Any]:
    summary = rows(
        """
        with fighter_fights as (
            select fighter1_result as result from ufc_fights
            where fighter1_uid = :uid and fighter1_result is not null
            union all
            select fighter2_result as result from ufc_fights
            where fighter2_uid = :uid and fighter2_result is not null
        ), rec as (
            select
                sum(case when result = 'WIN' then 1 else 0 end) as wins,
                sum(case when result = 'LOSS' then 1 else 0 end) as losses,
                sum(case when result = 'DRAW' then 1 else 0 end) as draws,
                sum(case when result = 'NO_CONTEST' then 1 else 0 end) as no_contests,
                count(*) as total_fights
            from fighter_fights
        )
        select f.fighter_uid, f.first_name, f.last_name,
            f.first_name || ' ' || f.last_name as full_name,
            f.nickname, f.dob, f.place_of_birth, f.stance, f.style,
            f.height_inches, f.reach_inches, f.leg_reach_inches,
            coalesce(r.wins, 0) as wins,
            coalesce(r.losses, 0) as losses,
            coalesce(r.draws, 0) as draws,
            coalesce(r.no_contests, 0) as no_contests,
            coalesce(r.total_fights, 0) as total_fights
        from ufc_fighters f
        cross join rec r
        where f.fighter_uid = :uid
        """,
        uid=fighter_uid,
    )
    if not summary:
        raise HTTPException(status_code=404, detail="Fighter not found")
    row = summary[0]
    fights = rows(
        """
        with totals as (
            select fight_uid, fighter_uid,
                sum(total_strikes_landed) as strikes_landed,
                sum(total_strikes_attempted) as strikes_attempted,
                sum(sig_strikes_landed) as sig_strikes_landed,
                sum(sig_strikes_attempted) as sig_strikes_attempted,
                sum(sig_strikes_head_landed) as head,
                sum(sig_strikes_body_landed) as body,
                sum(sig_strikes_leg_landed) as leg,
                sum(takedowns_landed) as takedowns,
                sum(control_time_seconds) as control_seconds
            from ufc_fight_stats group by fight_uid, fighter_uid
        ), fighter_fights as (
            select fight_uid, event_uid, fighter2_uid as opponent_uid,
                fighter1_result as result, decision, decision_round, fight_division, fight_order
            from ufc_fights where fighter1_uid = :uid and fighter1_result is not null
            union all
            select fight_uid, event_uid, fighter1_uid as opponent_uid,
                fighter2_result as result, decision, decision_round, fight_division, fight_order
            from ufc_fights where fighter2_uid = :uid and fighter2_result is not null
        ), odds as (
            select bl.fight_uid, bo.closing_odds,
                row_number() over (partition by bl.fight_uid order by bo.event_date desc, bo.slug desc) as rn
            from bfo_ufc_link bl join bfo_parsed_odds bo
                on bl.match_id = bo.match_id and bl.fighter = bo.fighter
            where bl.fighter_uid = :uid
        )
        select f.*, e.title as event_title, e.event_date,
            o.first_name || ' ' || o.last_name as opponent_name,
            t.strikes_landed, t.strikes_attempted, t.sig_strikes_landed,
            t.sig_strikes_attempted, t.head, t.body, t.leg, t.takedowns, t.control_seconds,
            ot.strikes_landed as strikes_absorbed, odds.closing_odds
        from fighter_fights f
        join ufc_events e on f.event_uid = e.event_uid
        join ufc_fighters o on f.opponent_uid = o.fighter_uid
        left join totals t on f.fight_uid = t.fight_uid and t.fighter_uid = :uid
        left join totals ot on f.fight_uid = ot.fight_uid and ot.fighter_uid = f.opponent_uid
        left join odds on f.fight_uid = odds.fight_uid and odds.rn = 1
        order by e.event_date, e.event_uid, f.fight_order desc nulls last, f.fight_uid
    """,
        uid=fighter_uid,
    )
    return {
        "bio": {key: row[key] for key in _BIO_KEYS},
        "record": {key: int(row[key] or 0) for key in _RECORD_KEYS},
        "fights": fights,
    }


@lru_cache(maxsize=24)
def _network(division: str, start_year: int, end_year: int, period: int, revision: str) -> dict[str, Any]:
    import networkx as nx

    fights = rows(
        """
        select f.fighter1_uid, f.fighter2_uid, f.fighter1_result, f.fighter2_result,
            a.first_name || ' ' || a.last_name as fighter1_name,
            b.first_name || ' ' || b.last_name as fighter2_name
        from ufc_fights f
        join ufc_events e on f.event_uid = e.event_uid
        join ufc_fighters a on f.fighter1_uid = a.fighter_uid
        join ufc_fighters b on f.fighter2_uid = b.fighter_uid
        where f.fight_division = :division and f.fighter1_result is not null
            and year(cast(e.event_date as date)) between :start_year and :end_year
        order by e.event_date, f.fight_uid
    """,
        division=division,
        start_year=start_year,
        end_year=end_year,
    )
    graph = nx.Graph()
    for fight in fights:
        for side in (1, 2):
            uid = fight[f"fighter{side}_uid"]
            if uid not in graph:
                graph.add_node(uid, name=fight[f"fighter{side}_name"], fights=0, wins=0, losses=0)
            node = graph.nodes[uid]
            node["fights"] += 1
            node["wins"] += fight[f"fighter{side}_result"] == "WIN"
            node["losses"] += fight[f"fighter{side}_result"] == "LOSS"
        a, b = fight["fighter1_uid"], fight["fighter2_uid"]
        if not graph.has_edge(a, b):
            graph.add_edge(a, b, fights=0, wins={}, draws=0, no_contests=0)
        edge = graph[a][b]
        edge["fights"] += 1
        for side in (1, 2):
            if fight[f"fighter{side}_result"] == "WIN":
                uid = fight[f"fighter{side}_uid"]
                edge["wins"][uid] = edge["wins"].get(uid, 0) + 1
        edge["draws"] += fight["fighter1_result"] == "DRAW"
        edge["no_contests"] += fight["fighter1_result"] == "NO_CONTEST"
    positions = {}
    components = sorted(nx.connected_components(graph), key=len, reverse=True)
    for index, component in enumerate(components):
        layout = nx.spring_layout(graph.subgraph(component), seed=42, iterations=60, scale=400)
        if index == 0:
            positions.update(layout)
        else:
            center_x = 580 + ((index - 1) // 5) * 180
            center_y = -320 + ((index - 1) % 5) * 160
            for uid, point in layout.items():
                positions[uid] = (
                    center_x + float(point[0]) * 0.12,
                    center_y + float(point[1]) * 0.12,
                )
    return {
        "nodes": [
            {"id": uid, **values, "x": float(positions[uid][0]), "y": float(positions[uid][1])}
            for uid, values in graph.nodes(data=True)
        ],
        "links": [
            {
                "source": a,
                "target": b,
                "fights": values["fights"],
                "source_wins": values["wins"].get(a, 0),
                "target_wins": values["wins"].get(b, 0),
                "draws": values["draws"],
                "no_contests": values["no_contests"],
            }
            for a, b, values in graph.edges(data=True)
        ],
    }


@router.get("/analytics/network", response_model=NetworkAnalytics)
def network(
    division: str = "HEAVYWEIGHT",
    start_year: int | None = Query(None, ge=1993, le=2100),
    end_year: int | None = Query(None, ge=1993, le=2100),
) -> dict[str, Any]:
    year = current_year()
    start_year = start_year if start_year is not None else year - 5
    end_year = end_year if end_year is not None else year
    if start_year > end_year:
        raise HTTPException(status_code=422, detail="Start year must not exceed end year")
    return _network(division, start_year, end_year, int(time.monotonic() // 120), current_revision().revision)


@router.get("/analytics/roster", response_model=RosterAnalytics)
def roster_analytics(division: str = "MIDDLEWEIGHT") -> dict[str, Any]:
    fighters = rows(
        """
        with results as (
            select fight_uid, fighter1_uid as fighter_uid, fighter2_uid as opponent_uid,
                fighter1_result as result, fight_division from ufc_fights
            union all
            select fight_uid, fighter2_uid, fighter1_uid, fighter2_result, fight_division from ufc_fights
        ), primary_division as (
            select fighter_uid, fight_division,
                row_number() over (partition by fighter_uid order by count(*) desc, fight_division) as rn
            from results where fight_division is not null group by fighter_uid, fight_division
        ), records as (
            select fighter_uid, count(*) as total_fights,
                count(case when result = 'WIN' then 1 end) as wins
            from results where result is not null group by fighter_uid
        ), opposition as (
            select r.fighter_uid, sum(coalesce(o.wins, 0)) as opposition_strength
            from results r left join records o on r.opponent_uid = o.fighter_uid
            where r.result = 'WIN' group by r.fighter_uid
        ), striking as (
            select a.fighter_uid, median(a.total_strikes_landed) as landed,
                median(b.total_strikes_landed) as absorbed
            from ufc_fight_stats a join ufc_fight_stats b
                on a.fight_uid = b.fight_uid and a.round_num = b.round_num and a.fighter_uid != b.fighter_uid
            group by a.fighter_uid
        )
        select f.fighter_uid, f.first_name || ' ' || f.last_name as fighter_name,
            r.total_fights, r.wins, s.landed, s.absorbed,
            coalesce(o.opposition_strength, 0) as opposition_strength
        from ufc_fighters f
        join records r on f.fighter_uid = r.fighter_uid
        join striking s on f.fighter_uid = s.fighter_uid
        left join primary_division d on f.fighter_uid = d.fighter_uid and d.rn = 1
        left join opposition o on f.fighter_uid = o.fighter_uid
        where r.total_fights >= 5 and (:division = 'ALL' or d.fight_division = :division)
            and s.landed is not null and s.absorbed is not null
        order by r.total_fights desc, f.fighter_uid
    """,
        division=division,
    )
    targets = rows(
        """
        with results as (
            select fight_uid, fighter1_uid as fighter_uid, fighter1_result as result, fight_division from ufc_fights
            union all
            select fight_uid, fighter2_uid, fighter2_result, fight_division from ufc_fights
        ), totals as (
            select s.fight_uid, s.fighter_uid, r.result,
                sum(sig_strikes_landed) as total, sum(sig_strikes_head_landed) as head,
                sum(sig_strikes_body_landed) as body, sum(sig_strikes_leg_landed) as leg
            from ufc_fight_stats s join results r on s.fight_uid = r.fight_uid and s.fighter_uid = r.fighter_uid
            where r.result in ('WIN', 'LOSS') and (:division = 'ALL' or r.fight_division = :division)
            group by s.fight_uid, s.fighter_uid, r.result
        ), targets as (
            select fight_uid, fighter_uid, result, 'Head' as target, head * 100.0 / total as pct from totals where total > 0
            union all select fight_uid, fighter_uid, result, 'Body', body * 100.0 / total from totals where total > 0
            union all select fight_uid, fighter_uid, result, 'Leg', leg * 100.0 / total from totals where total > 0
        ), summaries as (
            select target, result, count(*) as sample_count,
                quantile_cont(pct, 0.25) as q1, median(pct) as median,
                quantile_cont(pct, 0.75) as q3
            from targets where pct is not null group by target, result
        )
        select s.target, s.result, s.sample_count as count, s.q1, s.median, s.q3,
            min(t.pct) filter (where t.pct >= s.q1 - 1.5 * (s.q3 - s.q1)) as low,
            max(t.pct) filter (where t.pct <= s.q3 + 1.5 * (s.q3 - s.q1)) as high,
            list(struct_pack(value := t.pct, fighter_uid := t.fighter_uid,
                fighter_name := f.first_name || ' ' || f.last_name,
                event_title := e.title, event_date := e.event_date))
                filter (where t.pct < s.q1 - 1.5 * (s.q3 - s.q1)
                    or t.pct > s.q3 + 1.5 * (s.q3 - s.q1)) as outliers
        from summaries s join targets t on s.target = t.target and s.result = t.result
        join ufc_fighters f on t.fighter_uid = f.fighter_uid
        join ufc_fights fi on t.fight_uid = fi.fight_uid
        join ufc_events e on fi.event_uid = e.event_uid
        group by s.target, s.result, s.sample_count, s.q1, s.median, s.q3
        order by s.target, s.result
    """,
        division=division,
    )
    advantages = rows(
        """
        with long_fights as (
            select fight_uid, fighter1_uid as fighter_uid, fighter2_uid as opponent_uid,
                fighter1_result as result, fight_division, event_uid, fight_order from ufc_fights
            union all
            select fight_uid, fighter2_uid, fighter1_uid, fighter2_result, fight_division, event_uid, fight_order from ufc_fights
        ), experience as (
            select l.*, e.event_date,
                row_number() over (partition by l.fighter_uid order by e.event_date, e.event_uid, l.fight_order desc nulls last, l.fight_uid) as experience
            from long_fights l join ufc_events e on l.event_uid = e.event_uid
        ), differences as (
            select a.result,
                date_diff('day', try_cast(f.dob as date), try_cast(o.dob as date)) / 365.25 as age,
                f.reach_inches - o.reach_inches as reach,
                a.experience - b.experience as experience
            from experience a join experience b on a.fight_uid = b.fight_uid and a.opponent_uid = b.fighter_uid
            join ufc_fighters f on a.fighter_uid = f.fighter_uid
            join ufc_fighters o on a.opponent_uid = o.fighter_uid
            where a.result in ('WIN', 'LOSS') and (:division = 'ALL' or a.fight_division = :division)
        ), metrics as (
            select result, 'Age' as metric, age as difference from differences
            union all select result, 'Reach', reach from differences
            union all select result, 'Experience', experience from differences
        ), bins as (
            select *, case when metric = 'Reach' then
                case when difference <= -6 then 0 when difference <= -3 then 1
                    when difference <= -1 then 2 when difference <= 1 then 3
                    when difference <= 3 then 4 when difference <= 6 then 5 else 6 end
                else case when difference <= -10 then 0 when difference <= -5 then 1
                when difference <= -2 then 2 when difference <= 0 then 3 when difference <= 2 then 4
                when difference <= 5 then 5 when difference <= 10 then 6 else 7 end end as bin_order
            from metrics where difference is not null
        )
        select metric, bin_order, count(*) as count,
            avg(case when result = 'WIN' then 100.0 else 0.0 end) as win_rate
        from bins group by metric, bin_order having count(*) >= 20 order by metric, bin_order
    """,
        division=division,
    )
    bin_labels = [
        "≤ −10",
        "−10 to −5",
        "−5 to −2",
        "−2 to 0",
        "0 to +2",
        "+2 to +5",
        "+5 to +10",
        "> +10",
    ]
    reach_labels = ["≤ −6", "−6 to −3", "−3 to −1", "Even", "+1 to +3", "+3 to +6", "> +6"]
    return {
        "fighters": fighters,
        "targets": [
            {
                "target": r["target"],
                "result": r["result"],
                "count": r["count"],
                "values": [r["low"], r["q1"], r["median"], r["q3"], r["high"]],
                "outliers": r["outliers"] or [],
            }
            for r in targets
        ],
        "advantages": [
            {
                "metric": r["metric"],
                "bin": (reach_labels if r["metric"] == "Reach" else bin_labels)[r["bin_order"]],
                "count": r["count"],
                "win_rate": r["win_rate"],
            }
            for r in advantages
        ],
    }
