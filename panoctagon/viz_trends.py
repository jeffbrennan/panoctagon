"""
viz playground for app inclusion
"""

import pandas as pd
import plotly.express as px
from panoctagon.common import get_engine


def main():
    df = pd.read_sql_query(
        """
        select 
            event_date, 
            fight_division,
            weight_lbs,
            target,
            target_order
            strikes,
            target_strike_pct,
            metric
        from mart_striking_stats 
        where metric = 'attempted'
        order by weight_lbs, event_date, target_order desc
        """,
        get_engine(),
        parse_dates=["event_date"],
    )

    max_event_date = df["event_date"].max().strftime("%Y-%m-%d")

    title_text = "Striking Trends by Target, Fight Division"
    subtitle_text = f"last updated: {max_event_date}"
    title = f"<b>{title_text}</b><br>{subtitle_text}"
    print(df.shape)
    print(df.head(10))
    fig = (
        px.area(
            data_frame=df,
            x="event_date",
            color="target",
            y="target_strike_pct",
            facet_col="fight_division",
            title=title,
        )
        .for_each_annotation(lambda a: a.update(text=a.text.split("=")[1]))  # type: ignore
        .update_xaxes(matches=None, showticklabels=True)
        .update_yaxes(matches=None, showticklabels=True)
    )

    fig.show()


if __name__ == "__main__":
    main()
