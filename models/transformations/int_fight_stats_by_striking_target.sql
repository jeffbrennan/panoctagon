with
    initial_melt       as (
        {{ dbt_utils.unpivot(
            relation=ref('stg_ufc__fight_stats'),
            cast_to='int',
            exclude=["fight_uid", "fighter_uid", "round_num"],
            field_name="metric_target",
            value_name="strikes"
          ) }}
    )
  , initial_melt_clean as (
        select
            fight_uid,
            fighter_uid,
            round_num,
            case
                when metric_target like '%attempted' then 'attempted'
                when metric_target like '%landed' then 'landed'
                end as metric,
            case
                when metric_target like '%head%' then 'head'
                when metric_target like '%body%' then 'body'
                when metric_target like '%leg%' then 'leg'
                end as target,
            strikes
        from initial_melt
    )
select
    fight_uid,
    fighter_uid,
    round_num,
    metric,
    target,
    strikes
from initial_melt_clean
