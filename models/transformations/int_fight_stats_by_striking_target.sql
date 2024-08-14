with
    head     as (
        select
            fight_uid,
            fighter_uid,
            round_num,
            'head'                     as target,
            sig_strikes_head_attempted as attempted,
            sig_strikes_head_landed    as landed
        from {{ ref("stg_ufc__fight_stats") }}
    ),
    body     as (
        select
            fight_uid,
            fighter_uid,
            round_num,
            'body'                     as target,
            sig_strikes_body_attempted as attempted,
            sig_strikes_body_landed    as landed
        from {{ ref("stg_ufc__fight_stats") }}
    ),
    leg      as (
        select
            fight_uid,
            fighter_uid,
            round_num,
            'leg'                     as target,
            sig_strikes_leg_attempted as attempted,
            sig_strikes_leg_landed    as landed
        from {{ ref("stg_ufc__fight_stats") }}
    ),
    combined as (
        select *
        from head
        union
        select *
        from body
        union
        select *
        from leg
    ),
    summed   as (
        select
            fight_uid,
            target,
            sum(landed)    as landed,
            sum(attempted) as attempted
        from combined
        group by fight_uid, target
    ),
    final    as (
        select fight_uid, target, 'landed' as metric, landed as strikes
from summed
union
select
    fight_uid,
    target,
    'attempted' as metric,
    attempted as strikes
from summed
    )
select
    fight_uid,
    target,
    metric,
    strikes
from final
