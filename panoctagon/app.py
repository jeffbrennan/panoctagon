from dash import Dash, dash_table, dcc, callback, Output, Input
import pandas as pd
import plotly.express as px
import dash_mantine_components as dmc
from panoctagon.common import get_engine
from typing import Any

df = pd.read_sql_query(
    """
    select
        fs.fight_uid,
        fs.round_num,
        fs.fighter_uid,
        fs.total_strikes_landed,
        fs.total_strikes_attempted,
        fs.takedowns_landed,
        fs.takedowns_attempted,
        coalesce(f1result.fighter1_result, f2result.fighter2_result) as fighter_result,
        f.first_name,
        f.last_name,
        f.first_name || ' ' || f.last_name as fighter_name,
        f.height_inches,
        f.reach_inches,
        e.event_date,
        e.title
    from ufc_fight_stats fs
    inner join ufc_fighters f
        on fs.fighter_uid = f.fighter_uid
    inner join ufc_fights fights
        on fs.fight_uid = fights.fight_uid
    inner join ufc_events e
        on fights.event_uid = e.event_uid
    left join ufc_fights f1result
        on fs.fighter_uid = f1result.fighter1_uid
        and fs.fight_uid = f1result.fight_uid
    left join ufc_fights f2result
        on fs.fighter_uid = f2result.fighter2_uid
        and fs.fight_uid = f2result.fight_uid
    """,
    get_engine(),
)
tbl_cols = [
    "title",
    "fighter_result",
    "round_num",
    "total_strikes_landed",
    "total_strikes_attempted",
    "takedowns_landed",
    "takedowns_attempted",
]
initial_fighter = df.sample(1)["fighter_name"].item()
if not isinstance(initial_fighter, str):
    raise TypeError()

app = Dash()

app.layout = dmc.Container(
    [
        dmc.Title("Panoctagon", color="blue", size="h3"),
        dmc.TextInput(
            w="200",
            placeholder="Enter Fighter Name",
            label="Fighter Name",
            id="fighter_name",
            value=initial_fighter,
        ),
        dmc.RadioGroup(
            [
                dmc.Radio(i, value=i)
                for i in ["total_strikes_landed", "takedowns_landed"]
            ],
            id="my-dmc-radio-item",
            value="total_strikes_landed",
            size="sm",
        ),
        dmc.Stack(
            [
                dash_table.DataTable(
                    id="table-placeholder",
                    columns=[{"name": i, "id": i} for i in df[tbl_cols].columns],
                    sort_action="native",
                    filter_action="native",
                    style_table={
                        "height": "250px",
                        "overflowX": "scroll",
                        "overflowY": "scroll",
                    },
                ),
                dcc.Graph(figure={}, id="graph-placeholder"),
            ]
        ),
    ]
)


@callback(
    Output(component_id="table-placeholder", component_property="data"),
    Input(component_id="fighter_name", component_property="value"),
)
def update_table(fighter_name: str) -> list[dict[Any, Any]]:
    fighter_name = fighter_name.strip().title()
    tbl_cols = [
        "title",
        "fighter_result",
        "round_num",
        "total_strikes_landed",
        "total_strikes_attempted",
        "takedowns_landed",
        "takedowns_attempted",
    ]

    df_filtered = (
        df.assign(fighter_name=lambda x: x.fighter_name.str.strip().str.title())  # type: ignore
        .query(f"fighter_name == '{fighter_name}'")
        .sort_values("event_date", ascending=False)
    )[tbl_cols]

    if df_filtered.empty:
        return [{}]

    if not isinstance(df_filtered, pd.DataFrame):
        raise TypeError()

    return df_filtered.to_dict("records")


@callback(
    Output(component_id="graph-placeholder", component_property="figure"),
    Input(component_id="my-dmc-radio-item", component_property="value"),
    Input(component_id="fighter_name", component_property="value"),
)
def update_graph(metric: str, fighter_name: str):
    fighter_name = fighter_name.strip().title()
    df_filtered = df[df["fighter_name"].str.strip().str.title() == fighter_name]

    if df_filtered.empty:
        fig = px.strip(title=f"No data for {fighter_name}")
    else:
        fig = px.strip(
            data_frame=df_filtered,
            x="event_date",
            y=metric,
            color="fighter_result",
            title=f"{fighter_name} - {metric}",
        )

    fig.update_layout(height=500)
    return fig


if __name__ == "__main__":
    app.run(debug=True)
