from dash import Dash, dash_table, dcc, callback, Output, Input
import pandas as pd
import plotly.express as px
import dash_mantine_components as dmc
from panoctagon.common import get_engine
from typing import Any


def get_tbl_cols() -> list[str]:
    tbl_cols = [
        "title",
        "fighter_result",
        "opponent_name",
        "round_num",
        "total_strikes_landed",
        "total_strikes_attempted",
        "takedowns_landed",
        "takedowns_attempted",
    ]
    return tbl_cols


# TODO: precompute this
df = pd.read_sql_query(
    """
    with
        event_details      as (
            select
                title,
                event_date,
                fight_uid
            from ufc_events a
            inner join ufc_fights b
                on a.event_uid = b.event_uid
        ),
        fighter_details    as (
            select
                fighter_uid,
                first_name,
                last_name,
                height_inches,
                reach_inches
            from ufc_fighters
        ),
        fight_results_long as (
            select
                fight_uid,
                fighter1_uid    as fighter_uid,
                fighter1_result as fighter_result
            from ufc_fights
            union
            select
                fight_uid,
                fighter2_uid    as fighter_uid,
                fighter2_result as fighter_result
            from ufc_fights
        ),
        fs                 as (
            select
                a.fight_uid,
                a.round_num,
                a.fighter_uid,
                c.fighter_result,
                b.first_name || ' ' || b.last_name as fighter_name,
                b.reach_inches,
                b.height_inches,
                total_strikes_landed,
                total_strikes_attempted,
                takedowns_landed,
                takedowns_attempted
            from ufc_fight_stats a
            inner join fighter_details b
                on a.fighter_uid = b.fighter_uid
            inner join fight_results_long c
                on a.fight_uid = c.fight_uid
                and a.fighter_uid = c.fighter_uid
        ),
        opp_fs             as (
            select
                a.fight_uid,
                a.round_num,
                a.fighter_uid                      as opponent_uid,
                c.fighter_result                   as opponent_result,
                b.first_name || ' ' || b.last_name as opponent_name,
                b.reach_inches                     as opponent_reach_inches,
                b.height_inches                    as opponent_height_inches,
                total_strikes_landed               as opponent_strikes_landed,
                total_strikes_attempted            as opponent_strikes_attempted,
                takedowns_landed                   as opponent_takedowns_landed,
                takedowns_attempted                as opponent_takedowns_attempted
            from ufc_fight_stats a
            inner join fighter_details b
                on a.fighter_uid = b.fighter_uid
            inner join fight_results_long c
                on a.fight_uid = c.fight_uid
                and a.fighter_uid = c.fighter_uid

        )
    select
        event_details.title,
        event_details.event_date,
        fs.fight_uid,
        fs.round_num,
        fighter_name,
        fighter_result,
        height_inches,
        reach_inches,
        total_strikes_landed,
        total_strikes_attempted,
        takedowns_landed,
        takedowns_attempted,
        opponent_name,
        opponent_result,
        opponent_reach_inches,
        opponent_height_inches,
        opponent_strikes_attempted,
        opponent_strikes_landed,
        opponent_takedowns_attempted,
        opponent_takedowns_landed
    from fs
    inner join event_details
        on fs.fight_uid = event_details.fight_uid
    inner join opp_fs
        on fs.fight_uid = opp_fs.fight_uid
        and fs.round_num = opp_fs.round_num
        and fs.fighter_uid != opp_fs.opponent_uid;
    """,
    get_engine(),
)

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
                    columns=[{"name": i, "id": i} for i in df[get_tbl_cols()].columns],
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
    df_filtered = (
        df.assign(fighter_name=lambda x: x.fighter_name.str.strip().str.title())  # type: ignore
        .query(f"fighter_name == '{fighter_name}'")
        .sort_values("event_date", ascending=False)
    )[get_tbl_cols()]

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
