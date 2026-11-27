from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import text

from panoctagon.api.database import get_read_engine


def search_fighters(
    name: Optional[str] = None,
    division: Optional[str] = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    engine = get_read_engine()
    with engine.connect() as conn:
        query = """
        with fighter_division_counts as (
            select
                fighter_uid,
                fight_division,
                count(*) as fight_count,
                row_number() over (partition by fighter_uid order by count(*) desc) as rn
            from (
                select fighter1_uid as fighter_uid, fight_division from ufc_fights
                where fight_division is not null
                union all
                select fighter2_uid as fighter_uid, fight_division from ufc_fights
                where fight_division is not null
            )
            group by fighter_uid, fight_division
        ),
        fighter_records as (
            select
                fighter_uid,
                sum(case when result = 'WIN' then 1 else 0 end) as wins,
                sum(case when result = 'LOSS' then 1 else 0 end) as losses,
                sum(case when result = 'DRAW' then 1 else 0 end) as draws
            from (
                select fighter1_uid as fighter_uid, fighter1_result as result
                from ufc_fights where fighter1_result is not null
                union all
                select fighter2_uid as fighter_uid, fighter2_result as result
                from ufc_fights where fighter2_result is not null
            )
            group by fighter_uid
        )
        select
            f.fighter_uid,
            f.first_name || ' ' || f.last_name as full_name,
            f.nickname,
            f.stance,
            fdc.fight_division as division,
            coalesce(fr.wins, 0) as wins,
            coalesce(fr.losses, 0) as losses,
            coalesce(fr.draws, 0) as draws
        from ufc_fighters f
        left join fighter_division_counts fdc
            on f.fighter_uid = fdc.fighter_uid and fdc.rn = 1
        left join fighter_records fr
            on f.fighter_uid = fr.fighter_uid
        where 1=1
        """

        params: dict[str, Any] = {"limit": limit}
        if name:
            query += " and lower(f.first_name || ' ' || f.last_name) like lower(:name)"
            params["name"] = f"%{name}%"
        if division:
            query += " and lower(fdc.fight_division) = lower(:division)"
            params["division"] = division

        query += " order by coalesce(fr.wins, 0) + coalesce(fr.losses, 0) desc limit :limit"

        return [dict(row) for row in conn.execute(text(query), params).mappings()]


def get_fighter_detail(
    fighter_uid: str,
) -> tuple[Optional[dict[str, Any]], Optional[dict[str, Any]], list[dict[str, Any]]]:
    engine = get_read_engine()
    with engine.connect() as conn:
        bio_query = """
        select
            fighter_uid,
            first_name,
            last_name,
            first_name || ' ' || last_name as full_name,
            nickname,
            dob,
            place_of_birth,
            stance,
            style,
            height_inches,
            reach_inches,
            leg_reach_inches
        from ufc_fighters
        where fighter_uid = :fighter_uid
        """
        bio_mapping = conn.execute(text(bio_query), {"fighter_uid": fighter_uid}).mappings().first()
        if bio_mapping is None:
            return None, None, []

        record_query = """
        select
            coalesce(sum(case when result = 'WIN' then 1 else 0 end), 0) as wins,
            coalesce(sum(case when result = 'LOSS' then 1 else 0 end), 0) as losses,
            coalesce(sum(case when result = 'DRAW' then 1 else 0 end), 0) as draws,
            coalesce(sum(case when result = 'NO_CONTEST' then 1 else 0 end), 0) as no_contests,
            count(*) as total_fights
        from (
            select fighter1_result as result from ufc_fights where fighter1_uid = :fighter_uid and fighter1_result is not null
            union all
            select fighter2_result as result from ufc_fights where fighter2_uid = :fighter_uid and fighter2_result is not null
        )
        """
        record_mapping = (
            conn.execute(text(record_query), {"fighter_uid": fighter_uid}).mappings().first()
        )

        fights_query = """
        with fighter_fights as (
            select
                f.fight_uid,
                f.event_uid,
                f.fight_division,
                f.fight_type,
                f.decision,
                f.decision_round,
                f.fighter2_uid as opponent_uid,
                f.fighter1_result as result
            from ufc_fights f
            where f.fighter1_uid = :fighter_uid
            union all
            select
                f.fight_uid,
                f.event_uid,
                f.fight_division,
                f.fight_type,
                f.decision,
                f.decision_round,
                f.fighter1_uid as opponent_uid,
                f.fighter2_result as result
            from ufc_fights f
            where f.fighter2_uid = :fighter_uid
        )
        select
            ff.fight_uid,
            e.title as event_title,
            e.event_date,
            ff.fight_division,
            ff.fight_type,
            opp.first_name || ' ' || opp.last_name as opponent_name,
            ff.result,
            ff.decision,
            ff.decision_round
        from fighter_fights ff
        inner join ufc_events e on ff.event_uid = e.event_uid
        inner join ufc_fighters opp on ff.opponent_uid = opp.fighter_uid
        order by e.event_date desc
        limit 10
        """
        fights = [
            dict(row)
            for row in conn.execute(text(fights_query), {"fighter_uid": fighter_uid}).mappings()
        ]

        return dict(bio_mapping), dict(record_mapping) if record_mapping is not None else None, fights


def get_fighter_stats(fighter_uid: str) -> Optional[dict[str, Any]]:
    engine = get_read_engine()
    with engine.connect() as conn:
        query = """
        with fighter_results as (
            select
                fighter_uid,
                fight_uid,
                opponent_uid,
                result,
                decision
            from (
                select fighter1_uid as fighter_uid, fight_uid, fighter2_uid as opponent_uid,
                       fighter1_result as result, decision
                from ufc_fights where fighter1_uid = :fighter_uid and fighter1_result is not null
                union all
                select fighter2_uid as fighter_uid, fight_uid, fighter1_uid as opponent_uid,
                       fighter2_result as result, decision
                from ufc_fights where fighter2_uid = :fighter_uid and fighter2_result is not null
            )
        ),
        opponent_records as (
            select
                fighter_uid,
                sum(case when result = 'WIN' then 1 else 0 end) as opp_wins,
                sum(case when result = 'LOSS' then 1 else 0 end) as opp_losses
            from (
                select fighter1_uid as fighter_uid, fighter1_result as result
                from ufc_fights where fighter1_result is not null
                union all
                select fighter2_uid as fighter_uid, fighter2_result as result
                from ufc_fights where fighter2_result is not null
            )
            group by fighter_uid
        ),
        opp_strength as (
            select
                round(avg(opp.opp_wins * 100.0 / nullif(opp.opp_wins + opp.opp_losses, 0)), 1) as avg_opp_win_rate
            from fighter_results fr
            inner join opponent_records opp on fr.opponent_uid = opp.fighter_uid
        ),
        fight_stats as (
            select
                round(avg(sig_strikes_landed), 1) as avg_sig_strikes,
                round(sum(sig_strikes_landed) * 100.0 / nullif(sum(sig_strikes_attempted), 0), 1) as strike_accuracy,
                round(avg(takedowns_landed), 1) as avg_takedowns,
                coalesce(sum(knockdowns), 0) as total_knockdowns
            from ufc_fight_stats
            where fighter_uid = :fighter_uid
        ),
        win_types as (
            select
                coalesce(sum(case when result = 'WIN' and decision = 'TKO' then 1 else 0 end), 0) as ko_wins,
                coalesce(sum(case when result = 'WIN' and decision = 'SUB' then 1 else 0 end), 0) as sub_wins,
                coalesce(sum(case when result = 'WIN' and decision in ('UNANIMOUS_DECISION', 'SPLIT_DECISION', 'MAJORITY_DECISION') then 1 else 0 end), 0) as dec_wins
            from fighter_results
        )
        select
            fs.avg_sig_strikes,
            fs.strike_accuracy,
            fs.avg_takedowns,
            fs.total_knockdowns,
            wt.ko_wins,
            wt.sub_wins,
            wt.dec_wins,
            os.avg_opp_win_rate
        from ufc_fighters f
        cross join fight_stats fs
        cross join win_types wt
        cross join opp_strength os
        where f.fighter_uid = :fighter_uid
        """
        row = conn.execute(text(query), {"fighter_uid": fighter_uid}).mappings().first()
        return dict(row) if row is not None else None


_UPCOMING_FIGHTS_SQL = """
with upcoming as (
    select
        f.fight_uid,
        f.event_uid,
        e.title as event_title,
        e.event_date,
        e.event_location,
        f.fight_division,
        f.fight_type,
        f.fight_order,
        f.fighter1_uid,
        f.fighter2_uid
    from ufc_fights f
    inner join ufc_events e on f.event_uid = e.event_uid
    where f.fighter1_result is null
      and e.event_date::date >= current_date
),
upcoming_fighters as (
    select fighter1_uid as fighter_uid from upcoming
    union
    select fighter2_uid as fighter_uid from upcoming
),
fighter_info as (
    select
        f.fighter_uid,
        f.first_name || ' ' || f.last_name as fighter_name,
        f.reach_inches,
        f.height_inches,
        f.stance
    from ufc_fighters f
    inner join upcoming_fighters uf on f.fighter_uid = uf.fighter_uid
),
fighter_records as (
    select
        fighter_uid,
        count(*) as total_fights,
        sum(case when result = 'WIN' then 1 else 0 end) as wins,
        sum(case when result = 'LOSS' then 1 else 0 end) as losses,
        sum(case when result = 'DRAW' then 1 else 0 end) as draws
    from (
        select f.fighter1_uid as fighter_uid, f.fighter1_result as result
        from ufc_fights f
        inner join upcoming_fighters uf on f.fighter1_uid = uf.fighter_uid
        where f.fighter1_result is not null
        union all
        select f.fighter2_uid as fighter_uid, f.fighter2_result as result
        from ufc_fights f
        inner join upcoming_fighters uf on f.fighter2_uid = uf.fighter_uid
        where f.fighter2_result is not null
    )
    group by fighter_uid
),
odds as (
    select bl.fight_uid, bl.fighter_uid, bo.closing_odds,
        row_number() over (
            partition by bl.fight_uid, bl.fighter_uid
            order by bo.event_date desc, bo.slug desc
        ) as rn
    from bfo_ufc_link bl
    inner join upcoming u on bl.fight_uid = u.fight_uid
    inner join bfo_parsed_odds bo
        on bl.match_id = bo.match_id and bl.fighter = bo.fighter
)
select
    u.fight_uid,
    u.event_uid,
    u.event_title,
    u.event_date,
    u.event_location,
    u.fight_division,
    u.fight_type,
    u.fight_order,
    u.fighter1_uid,
    f1.fighter_name as fighter1_name,
    cast(coalesce(fr1.wins, 0) as varchar) || '-' ||
    cast(coalesce(fr1.losses, 0) as varchar) || '-' ||
    cast(coalesce(fr1.draws, 0) as varchar) as fighter1_record,
    f1.reach_inches as fighter1_reach,
    f1.height_inches as fighter1_height,
    f1.stance as fighter1_stance,
    coalesce(fr1.total_fights, 0) as fighter1_total_fights,
    odds1.closing_odds as fighter1_closing_odds,
    u.fighter2_uid,
    f2.fighter_name as fighter2_name,
    cast(coalesce(fr2.wins, 0) as varchar) || '-' ||
    cast(coalesce(fr2.losses, 0) as varchar) || '-' ||
    cast(coalesce(fr2.draws, 0) as varchar) as fighter2_record,
    f2.reach_inches as fighter2_reach,
    f2.height_inches as fighter2_height,
    f2.stance as fighter2_stance,
    coalesce(fr2.total_fights, 0) as fighter2_total_fights,
    odds2.closing_odds as fighter2_closing_odds
from upcoming u
inner join fighter_info f1 on u.fighter1_uid = f1.fighter_uid
inner join fighter_info f2 on u.fighter2_uid = f2.fighter_uid
left join fighter_records fr1 on u.fighter1_uid = fr1.fighter_uid
left join fighter_records fr2 on u.fighter2_uid = fr2.fighter_uid
left join odds odds1 on u.fight_uid = odds1.fight_uid
    and u.fighter1_uid = odds1.fighter_uid and odds1.rn = 1
left join odds odds2 on u.fight_uid = odds2.fight_uid
    and u.fighter2_uid = odds2.fighter_uid and odds2.rn = 1
order by u.event_date asc, u.fight_order asc nulls last
"""


def get_upcoming_rows() -> list[dict[str, Any]]:
    engine = get_read_engine()
    with engine.connect() as conn:
        return [dict(row) for row in conn.execute(text(_UPCOMING_FIGHTS_SQL)).mappings()]


def get_rankings(
    division: Optional[str] = None,
    min_fights: int = 5,
    limit: int = 15,
    sort_by: str = "win_rate",
) -> list[dict[str, Any]]:
    sort_columns = {
        "win_rate": "fs.wins * 1.0 / fs.total_fights desc, fs.total_fights desc",
        "sig_strikes": "coalesce(fsa.avg_sig_strikes, 0) desc",
        "strike_accuracy": "coalesce(fsa.strike_accuracy, 0) desc",
        "takedowns": "coalesce(fsa.avg_takedowns, 0) desc",
        "knockdowns": "coalesce(fsa.total_knockdowns, 0) desc",
        "ko_wins": "fs.ko_wins desc, fs.total_fights desc",
        "sub_wins": "fs.sub_wins desc, fs.total_fights desc",
        "opp_win_rate": "coalesce(fos.avg_opp_win_rate, 0) desc",
    }
    order_by = sort_columns.get(sort_by, sort_columns["win_rate"])

    engine = get_read_engine()
    with engine.connect() as conn:
        query = f"""
        with fighter_division_counts as (
            select
                fighter_uid,
                fight_division,
                count(*) as fight_count,
                row_number() over (partition by fighter_uid order by count(*) desc) as rn
            from (
                select fighter1_uid as fighter_uid, fight_division from ufc_fights
                where fight_division is not null
                union all
                select fighter2_uid as fighter_uid, fight_division from ufc_fights
                where fight_division is not null
            )
            group by fighter_uid, fight_division
        ),
        fighter_results as (
            select
                fighter_uid,
                fight_uid,
                opponent_uid,
                result,
                decision
            from (
                select fighter1_uid as fighter_uid, fight_uid, fighter2_uid as opponent_uid,
                       fighter1_result as result, decision
                from ufc_fights where fighter1_result is not null
                union all
                select fighter2_uid as fighter_uid, fight_uid, fighter1_uid as opponent_uid,
                       fighter2_result as result, decision
                from ufc_fights where fighter2_result is not null
            )
        ),
        opponent_records as (
            select
                fighter_uid,
                sum(case when result = 'WIN' then 1 else 0 end) as opp_wins,
                sum(case when result = 'LOSS' then 1 else 0 end) as opp_losses
            from fighter_results
            group by fighter_uid
        ),
        fighter_opp_strength as (
            select
                fr.fighter_uid,
                round(avg(opp.opp_wins * 100.0 / nullif(opp.opp_wins + opp.opp_losses, 0)), 1) as avg_opp_win_rate
            from fighter_results fr
            inner join opponent_records opp on fr.opponent_uid = opp.fighter_uid
            group by fr.fighter_uid
        ),
        fight_stats_agg as (
            select
                fighter_uid,
                round(avg(sig_strikes_landed), 1) as avg_sig_strikes,
                round(sum(sig_strikes_landed) * 100.0 / nullif(sum(sig_strikes_attempted), 0), 1) as strike_accuracy,
                round(avg(takedowns_landed), 1) as avg_takedowns,
                sum(knockdowns) as total_knockdowns
            from ufc_fight_stats
            group by fighter_uid
        ),
        fighter_stats as (
            select
                fighter_uid,
                count(*) as total_fights,
                sum(case when result = 'WIN' then 1 else 0 end) as wins,
                sum(case when result = 'LOSS' then 1 else 0 end) as losses,
                sum(case when result = 'DRAW' then 1 else 0 end) as draws,
                sum(case when result = 'WIN' and decision = 'TKO' then 1 else 0 end) as ko_wins,
                sum(case when result = 'WIN' and decision = 'SUB' then 1 else 0 end) as sub_wins,
                sum(case when result = 'WIN' and decision in ('UNANIMOUS_DECISION', 'SPLIT_DECISION', 'MAJORITY_DECISION') then 1 else 0 end) as dec_wins
            from fighter_results
            group by fighter_uid
        ),
        ranked as (
            select
                f.fighter_uid,
                f.first_name || ' ' || f.last_name as full_name,
                fdc.fight_division as division,
                fs.wins,
                fs.losses,
                fs.draws,
                round(fs.wins * 100.0 / fs.total_fights, 1) as win_rate,
                fs.total_fights,
                fs.ko_wins,
                fs.sub_wins,
                fs.dec_wins,
                coalesce(fsa.avg_sig_strikes, 0) as avg_sig_strikes,
                coalesce(fsa.strike_accuracy, 0) as strike_accuracy,
                coalesce(fsa.avg_takedowns, 0) as avg_takedowns,
                coalesce(fsa.total_knockdowns, 0) as total_knockdowns,
                coalesce(fos.avg_opp_win_rate, 0) as opp_win_rate,
                row_number() over (
                    partition by fdc.fight_division
                    order by {order_by}
                ) as rank
            from ufc_fighters f
            inner join fighter_division_counts fdc
                on f.fighter_uid = fdc.fighter_uid and fdc.rn = 1
            inner join fighter_stats fs
                on f.fighter_uid = fs.fighter_uid
            left join fight_stats_agg fsa
                on f.fighter_uid = fsa.fighter_uid
            left join fighter_opp_strength fos
                on f.fighter_uid = fos.fighter_uid
            where fs.total_fights >= :min_fights
        )
        select
            rank,
            fighter_uid,
            full_name,
            division,
            wins,
            losses,
            draws,
            win_rate,
            total_fights,
            ko_wins,
            sub_wins,
            dec_wins,
            avg_sig_strikes,
            strike_accuracy,
            avg_takedowns,
            total_knockdowns,
            opp_win_rate
        from ranked
        where 1=1
        """

        params: dict[str, Any] = {"min_fights": min_fights, "limit": limit}
        if division:
            query += " and lower(division) = lower(:division)"
            params["division"] = division

        query += " and rank <= :limit order by division, rank"

        return [dict(row) for row in conn.execute(text(query), params).mappings()]


def get_roster(
    division: Optional[str] = None,
    min_fights: int = 5,
    min_win_rate: Optional[float] = None,
    max_win_rate: Optional[float] = None,
    limit: int = 100,
    sort_by: str = "full_name",
) -> list[dict[str, Any]]:
    sort_columns = {
        "win_rate": "fs.wins * 1.0 / fs.total_fights desc, fs.total_fights desc",
        "sig_strikes": "coalesce(fsa.avg_sig_strikes, 0) desc",
        "strike_accuracy": "coalesce(fsa.strike_accuracy, 0) desc",
        "takedowns": "coalesce(fsa.avg_takedowns, 0) desc",
        "knockdowns": "coalesce(fsa.total_knockdowns, 0) desc",
        "ko_wins": "fs.ko_wins desc, fs.total_fights desc",
        "sub_wins": "fs.sub_wins desc, fs.total_fights desc",
        "opp_win_rate": "coalesce(fos.avg_opp_win_rate, 0) desc",
        "full_name": "full_name",
    }
    order_by = sort_columns.get(sort_by, sort_columns["win_rate"])

    engine = get_read_engine()
    with engine.connect() as conn:
        query = f"""
        with fighter_division_counts as (
            select
                fighter_uid,
                fight_division,
                count(*) as fight_count,
                row_number() over (partition by fighter_uid order by count(*) desc) as rn
            from (
                select fighter1_uid as fighter_uid, fight_division from ufc_fights
                where fight_division is not null
                union all
                select fighter2_uid as fighter_uid, fight_division from ufc_fights
                where fight_division is not null
            )
            group by fighter_uid, fight_division
        ),
        fighter_results as (
            select
                fighter_uid,
                fight_uid,
                opponent_uid,
                result,
                decision
            from (
                select fighter1_uid as fighter_uid, fight_uid, fighter2_uid as opponent_uid,
                       fighter1_result as result, decision
                from ufc_fights where fighter1_result is not null
                union all
                select fighter2_uid as fighter_uid, fight_uid, fighter1_uid as opponent_uid,
                       fighter2_result as result, decision
                from ufc_fights where fighter2_result is not null
            )
        ),
        opponent_records as (
            select
                fighter_uid,
                sum(case when result = 'WIN' then 1 else 0 end) as opp_wins,
                sum(case when result = 'LOSS' then 1 else 0 end) as opp_losses
            from fighter_results
            group by fighter_uid
        ),
        fighter_opp_strength as (
            select
                fr.fighter_uid,
                round(avg(opp.opp_wins * 100.0 / nullif(opp.opp_wins + opp.opp_losses, 0)), 1) as avg_opp_win_rate
            from fighter_results fr
            inner join opponent_records opp on fr.opponent_uid = opp.fighter_uid
            group by fr.fighter_uid
        ),
        fight_stats_agg as (
            select
                fighter_uid,
                round(avg(sig_strikes_landed), 1) as avg_sig_strikes,
                round(sum(sig_strikes_landed) * 100.0 / nullif(sum(sig_strikes_attempted), 0), 1) as strike_accuracy,
                round(avg(takedowns_landed), 1) as avg_takedowns,
                sum(knockdowns) as total_knockdowns
            from ufc_fight_stats
            group by fighter_uid
        ),
        fighter_stats as (
            select
                fighter_uid,
                count(*) as total_fights,
                sum(case when result = 'WIN' then 1 else 0 end) as wins,
                sum(case when result = 'LOSS' then 1 else 0 end) as losses,
                sum(case when result = 'DRAW' then 1 else 0 end) as draws,
                sum(case when result = 'WIN' and decision = 'TKO' then 1 else 0 end) as ko_wins,
                sum(case when result = 'WIN' and decision = 'SUB' then 1 else 0 end) as sub_wins,
                sum(case when result = 'WIN' and decision in ('UNANIMOUS_DECISION', 'SPLIT_DECISION', 'MAJORITY_DECISION') then 1 else 0 end) as dec_wins
            from fighter_results
            group by fighter_uid
        )
        select
            f.fighter_uid,
            f.first_name || ' ' || f.last_name as full_name,
            f.stance,
            fdc.fight_division as division,
            fs.wins,
            fs.losses,
            fs.draws,
            round(fs.wins * 100.0 / fs.total_fights, 1) as win_rate,
            fs.total_fights,
            fs.ko_wins,
            fs.sub_wins,
            fs.dec_wins,
            coalesce(fsa.avg_sig_strikes, 0) as avg_sig_strikes,
            coalesce(fsa.strike_accuracy, 0) as strike_accuracy,
            coalesce(fsa.avg_takedowns, 0) as avg_takedowns,
            coalesce(fsa.total_knockdowns, 0) as total_knockdowns,
            coalesce(fos.avg_opp_win_rate, 0) as opp_win_rate
        from ufc_fighters f
        inner join fighter_division_counts fdc
            on f.fighter_uid = fdc.fighter_uid and fdc.rn = 1
        inner join fighter_stats fs
            on f.fighter_uid = fs.fighter_uid
        left join fight_stats_agg fsa
            on f.fighter_uid = fsa.fighter_uid
        left join fighter_opp_strength fos
            on f.fighter_uid = fos.fighter_uid
        where fs.total_fights >= :min_fights
        """

        params: dict[str, Any] = {"min_fights": min_fights, "limit": limit}
        if division:
            query += " and lower(fdc.fight_division) = lower(:division)"
            params["division"] = division
        if min_win_rate is not None:
            query += " and (fs.wins * 100.0 / fs.total_fights) >= :min_win_rate"
            params["min_win_rate"] = min_win_rate
        if max_win_rate is not None:
            query += " and (fs.wins * 100.0 / fs.total_fights) <= :max_win_rate"
            params["max_win_rate"] = max_win_rate

        query += f" order by {order_by} limit :limit"

        return [dict(row) for row in conn.execute(text(query), params).mappings()]


def get_events(upcoming_only: bool = False, limit: int = 20) -> list[dict[str, Any]]:
    engine = get_read_engine()
    with engine.connect() as conn:
        query = """
        select
            e.event_uid,
            e.title,
            e.event_date,
            e.event_location,
            count(f.fight_uid) as num_fights
        from ufc_events e
        left join ufc_fights f on e.event_uid = f.event_uid
        """

        if upcoming_only:
            query += " where exists (select 1 from ufc_fights uf where uf.event_uid = e.event_uid and uf.fighter1_result is null) and e.event_date::date >= current_date"

        query += " group by e.event_uid, e.title, e.event_date, e.event_location order by e.event_date desc limit :limit"

        return [dict(row) for row in conn.execute(text(query), {"limit": limit}).mappings()]


def search_events(name: Optional[str] = None, limit: int = 20) -> list[dict[str, Any]]:
    engine = get_read_engine()
    with engine.connect() as conn:
        query = """
        select
            e.event_uid,
            e.title,
            e.event_date,
            e.event_location,
            count(f.fight_uid) as num_fights
        from ufc_events e
        left join ufc_fights f on e.event_uid = f.event_uid
        where 1=1
        """

        params: dict[str, Any] = {"limit": limit}
        if name:
            query += " and lower(e.title) like lower(:name)"
            params["name"] = f"%{name}%"

        query += " group by e.event_uid, e.title, e.event_date, e.event_location order by e.event_date desc limit :limit"

        return [dict(row) for row in conn.execute(text(query), params).mappings()]


def get_event_by_uid(event_uid: str) -> Optional[dict[str, Any]]:
    engine = get_read_engine()
    with engine.connect() as conn:
        row = (
            conn.execute(
                text(
                    """
                    select
                        e.event_uid,
                        e.title,
                        e.event_date,
                        e.event_location
                    from ufc_events e
                    where e.event_uid = :event_uid
                    """
                ),
                {"event_uid": event_uid},
            )
            .mappings()
            .first()
        )
        return dict(row) if row is not None else None


def get_event_fights(event_uid: str) -> list[dict[str, Any]]:
    engine = get_read_engine()
    with engine.connect() as conn:
        return [
            dict(row)
            for row in conn.execute(
                text(
                    """
                    select
                        f.fight_uid,
                        f.fight_division,
                        f.fight_type,
                        f.fight_order,
                        f1.first_name || ' ' || f1.last_name as fighter1_name,
                        f.fighter1_result,
                        f2.first_name || ' ' || f2.last_name as fighter2_name,
                        f.fighter2_result,
                        f.decision,
                        f.decision_round
                    from ufc_fights f
                    inner join ufc_fighters f1 on f.fighter1_uid = f1.fighter_uid
                    inner join ufc_fighters f2 on f.fighter2_uid = f2.fighter_uid
                    where f.event_uid = :event_uid
                    order by f.fight_order asc nulls last
                    """
                ),
                {"event_uid": event_uid},
            ).mappings()
        ]


def get_fighter_fights(fighter_uid: str, limit: int = 10) -> list[dict[str, Any]]:
    engine = get_read_engine()
    with engine.connect() as conn:
        return [
            dict(row)
            for row in conn.execute(
                text(
                    """
                    with fighter_fights as (
                        select
                            f.fight_uid,
                            f.event_uid,
                            f.fight_division,
                            f.decision,
                            f.decision_round,
                            f.fighter2_uid as opponent_uid,
                            f.fighter1_result as result
                        from ufc_fights f
                        where f.fighter1_uid = :fighter_uid
                        union all
                        select
                            f.fight_uid,
                            f.event_uid,
                            f.fight_division,
                            f.decision,
                            f.decision_round,
                            f.fighter1_uid as opponent_uid,
                            f.fighter2_result as result
                        from ufc_fights f
                        where f.fighter2_uid = :fighter_uid
                    )
                    select
                        ff.fight_uid,
                        e.title as event_title,
                        e.event_date,
                        ff.fight_division,
                        opp.first_name || ' ' || opp.last_name as opponent_name,
                        ff.result,
                        ff.decision,
                        ff.decision_round
                    from fighter_fights ff
                    inner join ufc_events e on ff.event_uid = e.event_uid
                    inner join ufc_fighters opp on ff.opponent_uid = opp.fighter_uid
                    order by e.event_date desc
                    limit :limit
                    """
                ),
                {"fighter_uid": fighter_uid, "limit": limit},
            ).mappings()
        ]


def get_divisions() -> list[str]:
    engine = get_read_engine()
    with engine.connect() as conn:
        return [
            row[0]
            for row in conn.execute(
                text(
                    """
                    select distinct fight_division as division
                    from ufc_fights
                    where fight_division is not null
                    order by fight_division
                    """
                )
            ).fetchall()
        ]


def get_fight_detail(
    fight_uid: str,
) -> tuple[Optional[dict[str, Any]], list[dict[str, Any]]]:
    engine = get_read_engine()
    with engine.connect() as conn:
        fight_query = """
        select
            f.fight_uid,
            f.event_uid,
            e.title as event_title,
            e.event_date,
            f.fight_division,
            f.fight_type,
            f.decision,
            f.decision_round,
            f.decision_time_seconds,
            f.referee,
            f.fighter1_uid,
            f1.first_name || ' ' || f1.last_name as fighter1_name,
            f.fighter1_result,
            f.fighter2_uid,
            f2.first_name || ' ' || f2.last_name as fighter2_name,
            f.fighter2_result
        from ufc_fights f
        inner join ufc_events e on f.event_uid = e.event_uid
        inner join ufc_fighters f1 on f.fighter1_uid = f1.fighter_uid
        inner join ufc_fighters f2 on f.fighter2_uid = f2.fighter_uid
        where f.fight_uid = :fight_uid
        """
        fight_mapping = (
            conn.execute(text(fight_query), {"fight_uid": fight_uid}).mappings().first()
        )
        if fight_mapping is None:
            return None, []

        stats_query = """
        select
            fs.fighter_uid,
            fs.round_num,
            fs.knockdowns,
            fs.total_strikes_landed,
            fs.total_strikes_attempted,
            fs.sig_strikes_landed,
            fs.sig_strikes_attempted,
            fs.takedowns_landed,
            fs.takedowns_attempted,
            fs.submissions_attempted,
            fs.reversals,
            fs.control_time_seconds
        from ufc_fight_stats fs
        where fs.fight_uid = :fight_uid
        order by fs.fighter_uid, fs.round_num
        """
        stats_rows = [
            dict(row)
            for row in conn.execute(text(stats_query), {"fight_uid": fight_uid}).mappings()
        ]

        return dict(fight_mapping), stats_rows
