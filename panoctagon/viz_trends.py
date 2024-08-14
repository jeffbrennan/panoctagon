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
            event_year,
            fight_division,
            weight_lbs,
            metric,
            target,
            target_order,
            strikes,
            target_strike_pct,
            last_refresh_timestamp 
        from mart_striking_stats 
        order by weight_lbs, event_year, target_order desc
        """,
        get_engine(),
        parse_dates=["event_year", "last_refresh_timestamp"],
    )

    last_refresh = df["last_refresh_timestamp"].to_list()[0].isoformat()

    title_text = "Striking Trends by Target, Fight Division"
    subtitle_text = f"last updated: {last_refresh}"
    title = f"<b>{title_text}</b><br>{subtitle_text}"
    print(df.shape)
    print(df.head(10))
    fig = (
        px.area(
            data_frame=df,
            x="event_year",
            color="target",
            y="target_strike_pct",
            facet_col="fight_division",
            facet_row="metric",
            title=title,
        )
        .for_each_annotation(lambda a: a.update(text=a.text.split("=")[1]))  # type: ignore
        .update_xaxes(matches=None, showticklabels=True)
        .update_yaxes(matches=None, showticklabels=True)
    )

    fig.show()


if __name__ == "__main__":
    main()
