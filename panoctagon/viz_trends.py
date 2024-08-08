"""
viz playground for app inclusion
"""

import pandas as pd
import plotly.express as px
from panoctagon.common import get_engine


def main():
    df = pd.read_sql_query(
        """
        with
            head     as (
                select
                    fight_uid,
                    fighter_uid,
                    round_num,
                    'head'                     as target,
                    sig_strikes_head_attempted as attempted,
                    sig_strikes_head_landed    as landed
                from ufc_fight_stats
            ),
            body     as (
                select
                    fight_uid,
                    fighter_uid,
                    round_num,
                    'body'                     as target,
                    sig_strikes_body_attempted as attempted,
                    sig_strikes_body_landed    as landed
                from ufc_fight_stats
            ),
            leg      as (
                select
                    fight_uid,
                    fighter_uid,
                    round_num,
                    'leg'                     as target,
                    sig_strikes_leg_attempted as attempted,
                    sig_strikes_leg_landed    as landed
                from ufc_fight_stats
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
                   select
                       fight_uid,
                       target,
                       'landed' as metric,
                       landed   as value
                   from summed
                   union
                   select
                       fight_uid,
                       target,
                       'attempted' as metric,
                       attempted   as value
                   from summed
               )
           select a.*, c.event_date
           from final a
           left join ufc_fights b
           on a.fight_uid = b.fight_uid
           left join ufc_events c
           on b.event_uid = c.event_uid
        """,
        get_engine(),
    )

    fig = px.scatter(
        data_frame=df,
        x="event_date",
        color="target",
        y="value",
        facet_col="metric",
        facet_row="target",
        opacity=0.2
    )
    fig = fig.update_yaxes(matches=None)
    fig.show()


if __name__ == "__main__":
    main()
