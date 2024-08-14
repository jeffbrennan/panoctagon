with
    events                as (
        select
            event_uid,
            title,
            event_date
        from ufc_events
    ),
    fights                as (
        select
            event_uid,
            fight_uid,
            fight_division
        from {{ source('main', 'ufc_fights')}}
    ),
    divisions             as (
        select
            upper(name) as division,
            weight_lbs
        from {{ source('main', 'divisions')}}
    ),
    valid_division_counts as (
        select
            fight_division,
            count(*) as n
        from fights a
        group by fight_division
        having count(*) > 50
    ),
    max_event_year        as (
        select
            strftime('%Y', max(event_date)) as max_yr
        from events
    ),
    valid_division_dates  as (
        select
            fight_division,
            max(event_date) as max_event_date
        from fights a
        inner join events b
            on a.event_uid = b.event_uid
        group by fight_division
        having strftime('%Y', max(event_date)) >= (
            select
                max_yr
            from max_event_year
        )
    ),
    valid_divisions       as (
        select
            a.fight_division
        from valid_division_counts a
        inner join valid_division_dates b
            on a.fight_division = b.fight_division
    ),
    valid_fights          as (
        select
            a.event_uid,
            a.fight_uid,
            a.fight_division
        from fights a
        inner join valid_divisions b
            on a.fight_division = b.fight_division
    ),
    sum_by_division       as (
        select
            c.event_uid,
            b.fight_division,
            a.target,
            a.metric,
            sum(a.strikes) as strikes
        from {{ ref("int_fight_stats_by_striking_target") }} a
        inner join valid_fights b on
            a.fight_uid = b.fight_uid
        inner join events c on b.event_uid = c.event_uid
        group by c.event_uid, b.fight_division, a.target, a.metric
    ),
    metric_total_count    as (
        select
            event_uid,
            fight_division,
            metric,
            sum(strikes) as strikes_total
        from sum_by_division
        group by event_uid, fight_division, metric
    ),
    agg                   as (
        select
            a.event_uid,
            a.fight_division,
            a.target,
            a.metric,
            a.strikes,
            a.strikes * 1.0 / b.strikes_total as target_strike_pct
        from sum_by_division a
        inner join metric_total_count b
            on a.event_uid = b.event_uid
            and a.fight_division = b.fight_division
            and a.metric = b.metric
    )
select
    a.event_uid,
    b.title,
    b.event_date,
    a.fight_division,
    c.weight_lbs,
    a.target,
    case
        when target == 'head' then 0
        when target == 'body' then 1
        when target == 'leg' then 2
        end target_order,
    a.metric,
    a.strikes,
    a.target_strike_pct
from agg a
inner join events b
    on a.event_uid = b.event_uid
inner join divisions c
    {#    TODO: use uid #} on a.fight_division = c.division