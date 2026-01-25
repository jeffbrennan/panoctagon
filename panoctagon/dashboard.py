from typing import Any

import dash_mantine_components as dmc
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import Dash, Input, Output, callback, dash_table, dcc, html

from panoctagon.common import get_engine


def get_main_data() -> pd.DataFrame:
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
            fight_metadata as (
                select
                    fight_uid,
                    fight_division,
                    fight_type,
                    decision,
                    decision_round
                from ufc_fights
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
                    takedowns_attempted,
                    sig_strikes_head_landed,
                    sig_strikes_head_attempted,
                    sig_strikes_body_landed,
                    sig_strikes_body_attempted,
                    sig_strikes_leg_landed,
                    sig_strikes_leg_attempted
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
            fm.fight_division,
            fm.fight_type,
            fm.decision,
            fm.decision_round,
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
            sig_strikes_head_landed,
            sig_strikes_head_attempted,
            sig_strikes_body_landed,
            sig_strikes_body_attempted,
            sig_strikes_leg_landed,
            sig_strikes_leg_attempted,
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
        inner join fight_metadata fm
            on fs.fight_uid = fm.fight_uid
        inner join opp_fs
            on fs.fight_uid = opp_fs.fight_uid
            and fs.round_num = opp_fs.round_num
            and fs.fighter_uid != opp_fs.opponent_uid;
        """,
        get_engine(),
    )
    df["event_date"] = pd.to_datetime(df["event_date"])
    return df


def get_fighter_list(df: pd.DataFrame) -> list[str]:
    fighter_counts = (
        df.groupby("fighter_name")
        .agg({"fight_uid": "nunique"})
        .reset_index()
        .rename(columns={"fight_uid": "fight_count"})
        .sort_values("fight_count", ascending=False)
    )

    return [str(row["fighter_name"]) for _, row in fighter_counts.iterrows()]


def get_decision_types(df: pd.DataFrame) -> list[str]:
    return sorted(df["decision"].dropna().unique().tolist())


def get_divisions(df: pd.DataFrame) -> list[str]:
    return sorted(df["fight_division"].dropna().unique().tolist())


df = get_main_data()
fighter_options = get_fighter_list(df)
decision_options = get_decision_types(df)
division_options = get_divisions(df)

initial_fighter = df.sample(1)["fighter_name"].item()
if not isinstance(initial_fighter, str):
    raise TypeError()

most_recent_event = df["event_date"].max().strftime("%Y-%m-%d")

app = Dash(__name__)
server = app.server

app.layout = dmc.MantineProvider(
    dmc.AppShell(
        [
            dmc.AppShellHeader(
                dmc.Group(
                    [
                        dmc.Title("Panoctagon", c="red", size="h2"),
                        dmc.Badge(
                            f"Data current as of {most_recent_event}",
                            color="gray",
                            variant="light",
                        ),
                    ],
                    justify="space-between",
                    p="md",
                ),
                h=60,
            ),
            dmc.AppShellMain(
                dmc.Container(
                    [
                        dmc.Card(
                            dmc.Grid(
                                [
                                    dmc.GridCol(
                                        dmc.Select(
                                            label="Fighter",
                                            placeholder="Select fighter",
                                            id="fighter-select",
                                            value=initial_fighter,
                                            data=fighter_options,
                                            searchable=True,
                                            clearable=False,
                                        ),
                                        span=3,
                                    ),
                                    dmc.GridCol(
                                        html.Div(
                                            [
                                                dmc.Text("Date Range", size="sm", fw="bold", mb=4),
                                                dcc.DatePickerRange(
                                                    id="date-range",
                                                    start_date=df["event_date"].min().strftime("%Y-%m-%d"),
                                                    end_date=df["event_date"].max().strftime("%Y-%m-%d"),
                                                    display_format="YYYY-MM-DD",
                                                    style={"width": "100%"},
                                                ),
                                            ]
                                        ),
                                        span=3,
                                    ),
                                    dmc.GridCol(
                                        dmc.MultiSelect(
                                            label="Decision Type",
                                            placeholder="All decisions",
                                            id="decision-filter",
                                            data=decision_options,
                                            clearable=True,
                                        ),
                                        span=3,
                                    ),
                                    dmc.GridCol(
                                        dmc.MultiSelect(
                                            label="Division",
                                            placeholder="All divisions",
                                            id="division-filter",
                                            data=division_options,
                                            clearable=True,
                                        ),
                                        span=3,
                                    ),
                                ],
                                gutter="md",
                            ),
                            shadow="sm",
                            withBorder=True,
                            p="lg",
                            mb="md",
                        ),
                        dmc.Tabs(
                            [
                                dmc.TabsList(
                                    [
                                        dmc.TabsTab("Fighter Profile", value="profile"),
                                        dmc.TabsTab("Fight History", value="history"),
                                        dmc.TabsTab("Striking Analytics", value="striking"),
                                    ]
                                ),
                                dmc.TabsPanel(
                                    [
                                        dmc.SimpleGrid(
                                            [
                                                dmc.Card(
                                                    [
                                                        dmc.Text("Total Fights", size="sm", c="gray"),
                                                        dmc.Title(id="total-fights", order=2),
                                                    ],
                                                    shadow="sm",
                                                    withBorder=True,
                                                    p="lg",
                                                ),
                                                dmc.Card(
                                                    [
                                                        dmc.Text("Record", size="sm", c="gray"),
                                                        dmc.Title(id="record", order=2),
                                                    ],
                                                    shadow="sm",
                                                    withBorder=True,
                                                    p="lg",
                                                ),
                                                dmc.Card(
                                                    [
                                                        dmc.Text("Finish Rate", size="sm", c="gray"),
                                                        dmc.Title(id="finish-rate", order=2),
                                                    ],
                                                    shadow="sm",
                                                    withBorder=True,
                                                    p="lg",
                                                ),
                                            ],
                                            cols=3,
                                            spacing="md",
                                            mb="md",
                                        ),
                                        dcc.Graph(id="career-timeline", figure={}),
                                        dcc.Graph(id="win-method-chart", figure={}),
                                    ],
                                    value="profile",
                                    pt="md",
                                ),
                                dmc.TabsPanel(
                                    dash_table.DataTable(
                                        id="fight-history-table",
                                        columns=[],
                                        data=[],
                                        sort_action="native",
                                        filter_action="native",
                                        style_table={
                                            "height": "600px",
                                            "overflowY": "scroll",
                                        },
                                        style_data_conditional=[
                                            {
                                                "if": {"filter_query": "{Result} = W"},
                                                "backgroundColor": "#d4edda",
                                            },
                                            {
                                                "if": {"filter_query": "{Result} = L"},
                                                "backgroundColor": "#f8d7da",
                                            },
                                        ],
                                    ),
                                    value="history",
                                    pt="md",
                                ),
                                dmc.TabsPanel(
                                    [
                                        dcc.Graph(id="accuracy-trend", figure={}),
                                        dcc.Graph(id="target-distribution", figure={}),
                                        dcc.Graph(id="strikes-comparison", figure={}),
                                    ],
                                    value="striking",
                                    pt="md",
                                ),
                            ],
                            value="profile",
                            id="main-tabs",
                        ),
                    ],
                    size="xl",
                    p="md",
                )
            ),
        ],
        header={"height": 60},
    )
)


def filter_data(
    df: pd.DataFrame,
    fighter: str,
    start_date: str | None,
    end_date: str | None,
    decisions: list[str] | None,
    divisions: list[str] | None,
) -> pd.DataFrame:
    filtered = df[df["fighter_name"] == fighter].copy()

    if start_date:
        filtered = filtered[filtered["event_date"] >= pd.to_datetime(start_date)]
    if end_date:
        filtered = filtered[filtered["event_date"] <= pd.to_datetime(end_date)]
    if decisions:
        filtered = filtered[filtered["decision"].isin(decisions)]
    if divisions:
        filtered = filtered[filtered["fight_division"].isin(divisions)]

    return filtered


def get_fighter_summary(df_fighter: pd.DataFrame) -> dict[str, Any]:
    if df_fighter.empty:
        return {"total_fights": 0, "wins": 0, "losses": 0, "draws": 0, "finish_rate": 0}

    fights = df_fighter.groupby("fight_uid").agg({"fighter_result": "first"}).reset_index()

    total_fights = len(fights)
    wins = (fights["fighter_result"] == "W").sum()
    losses = (fights["fighter_result"] == "L").sum()
    draws = (fights["fighter_result"] == "D").sum()

    finish_decisions = ["KO", "TKO", "SUB", "Submission"]
    finishes = df_fighter[df_fighter["decision"].isin(finish_decisions)].groupby("fight_uid").ngroups
    finish_rate = (finishes / total_fights * 100) if total_fights > 0 else 0

    return {
        "total_fights": total_fights,
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "finish_rate": finish_rate,
    }


@callback(
    [
        Output("total-fights", "children"),
        Output("record", "children"),
        Output("finish-rate", "children"),
    ],
    [
        Input("fighter-select", "value"),
        Input("date-range", "start_date"),
        Input("date-range", "end_date"),
        Input("decision-filter", "value"),
        Input("division-filter", "value"),
    ],
)
def update_summary_cards(
    fighter: str,
    start_date: str | None,
    end_date: str | None,
    decisions: list[str] | None,
    divisions: list[str] | None,
):
    df_filtered = filter_data(df, fighter, start_date, end_date, decisions, divisions)
    summary = get_fighter_summary(df_filtered)

    return (
        str(summary["total_fights"]),
        f"{summary['wins']}-{summary['losses']}-{summary['draws']}",
        f"{summary['finish_rate']:.1f}%",
    )


@callback(
    Output("career-timeline", "figure"),
    [
        Input("fighter-select", "value"),
        Input("date-range", "start_date"),
        Input("date-range", "end_date"),
        Input("decision-filter", "value"),
        Input("division-filter", "value"),
    ],
)
def update_career_timeline(
    fighter: str,
    start_date: str | None,
    end_date: str | None,
    decisions: list[str] | None,
    divisions: list[str] | None,
):
    df_filtered = filter_data(df, fighter, start_date, end_date, decisions, divisions)

    if df_filtered.empty:
        fig = px.strip(title=f"No data for {fighter}")
    else:
        fig = px.strip(
            data_frame=df_filtered,
            x="event_date",
            y="total_strikes_landed",
            color="fighter_result",
            title=f"{fighter} - Career Timeline",
            color_discrete_map={"W": "green", "L": "red", "D": "gray"},
        )

    fig.update_layout(height=400)
    return fig


@callback(
    Output("win-method-chart", "figure"),
    [
        Input("fighter-select", "value"),
        Input("date-range", "start_date"),
        Input("date-range", "end_date"),
        Input("decision-filter", "value"),
        Input("division-filter", "value"),
    ],
)
def update_win_method_chart(
    fighter: str,
    start_date: str | None,
    end_date: str | None,
    decisions: list[str] | None,
    divisions: list[str] | None,
):
    df_filtered = filter_data(df, fighter, start_date, end_date, decisions, divisions)
    df_wins = df_filtered[df_filtered["fighter_result"] == "W"]

    if df_wins.empty:
        fig = px.pie(title=f"No wins for {fighter}")
    else:
        win_methods = df_wins.groupby("fight_uid").agg({"decision": "first"}).reset_index()
        method_counts = win_methods["decision"].value_counts()

        fig = px.pie(
            values=method_counts.values,
            names=method_counts.index,
            title=f"{fighter} - Win Method Distribution",
        )

    fig.update_layout(height=400)
    return fig


@callback(
    [
        Output("fight-history-table", "columns"),
        Output("fight-history-table", "data"),
    ],
    [
        Input("fighter-select", "value"),
        Input("date-range", "start_date"),
        Input("date-range", "end_date"),
        Input("decision-filter", "value"),
        Input("division-filter", "value"),
    ],
)
def update_fight_history(
    fighter: str,
    start_date: str | None,
    end_date: str | None,
    decisions: list[str] | None,
    divisions: list[str] | None,
):
    df_filtered = filter_data(df, fighter, start_date, end_date, decisions, divisions)

    if df_filtered.empty:
        return [], []

    table_df = (
        df_filtered.groupby("fight_uid")
        .agg({
            "event_date": "first",
            "opponent_name": "first",
            "fighter_result": "first",
            "decision": "first",
            "decision_round": "first",
            "total_strikes_landed": "sum",
            "total_strikes_attempted": "sum",
            "takedowns_landed": "sum",
        })
        .reset_index()
        .sort_values("event_date", ascending=False)
    )

    table_df["event_date"] = table_df["event_date"].dt.strftime("%Y-%m-%d")
    table_df = table_df.rename(
        columns={
            "event_date": "Date",
            "opponent_name": "Opponent",
            "fighter_result": "Result",
            "decision": "Method",
            "decision_round": "Round",
            "total_strikes_landed": "Strikes Landed",
            "total_strikes_attempted": "Strikes Attempted",
            "takedowns_landed": "Takedowns",
        }
    )

    columns = [{"name": i, "id": i} for i in table_df.columns if i != "fight_uid"]
    data = table_df.drop(columns=["fight_uid"]).to_dict("records")

    return columns, data


@callback(
    Output("accuracy-trend", "figure"),
    [
        Input("fighter-select", "value"),
        Input("date-range", "start_date"),
        Input("date-range", "end_date"),
        Input("decision-filter", "value"),
        Input("division-filter", "value"),
    ],
)
def update_accuracy_trend(
    fighter: str,
    start_date: str | None,
    end_date: str | None,
    decisions: list[str] | None,
    divisions: list[str] | None,
):
    df_filtered = filter_data(df, fighter, start_date, end_date, decisions, divisions)

    if df_filtered.empty:
        fig = px.line(title=f"No data for {fighter}")
    else:
        fight_accuracy = (
            df_filtered.groupby(["fight_uid", "event_date"])
            .agg({
                "total_strikes_landed": "sum",
                "total_strikes_attempted": "sum",
            })
            .reset_index()
        )
        fight_accuracy = fight_accuracy[fight_accuracy["total_strikes_attempted"] > 0]
        fight_accuracy["accuracy"] = (
            fight_accuracy["total_strikes_landed"] / fight_accuracy["total_strikes_attempted"] * 100
        )
        fight_accuracy = fight_accuracy.sort_values("event_date")

        fig = px.line(
            fight_accuracy,
            x="event_date",
            y="accuracy",
            title=f"{fighter} - Striking Accuracy Over Time",
            markers=True,
        )
        fig.update_yaxes(title="Accuracy (%)", range=[0, 100])

    fig.update_layout(height=400)
    return fig


@callback(
    Output("target-distribution", "figure"),
    [
        Input("fighter-select", "value"),
        Input("date-range", "start_date"),
        Input("date-range", "end_date"),
        Input("decision-filter", "value"),
        Input("division-filter", "value"),
    ],
)
def update_target_distribution(
    fighter: str,
    start_date: str | None,
    end_date: str | None,
    decisions: list[str] | None,
    divisions: list[str] | None,
):
    df_filtered = filter_data(df, fighter, start_date, end_date, decisions, divisions)

    if df_filtered.empty:
        fig = px.bar(title=f"No data for {fighter}")
    else:
        strike_targets = (
            df_filtered.groupby(["fight_uid", "event_date"])
            .agg({
                "sig_strikes_head_landed": "sum",
                "sig_strikes_body_landed": "sum",
                "sig_strikes_leg_landed": "sum",
            })
            .reset_index()
            .sort_values("event_date")
        )

        strike_targets["event_date"] = strike_targets["event_date"].dt.strftime("%Y-%m-%d")

        fig = go.Figure()
        fig.add_trace(
            go.Bar(
                x=strike_targets["event_date"],
                y=strike_targets["sig_strikes_head_landed"],
                name="Head",
            )
        )
        fig.add_trace(
            go.Bar(
                x=strike_targets["event_date"],
                y=strike_targets["sig_strikes_body_landed"],
                name="Body",
            )
        )
        fig.add_trace(
            go.Bar(
                x=strike_targets["event_date"],
                y=strike_targets["sig_strikes_leg_landed"],
                name="Leg",
            )
        )

        fig.update_layout(
            barmode="stack",
            title=f"{fighter} - Strike Target Distribution",
            xaxis_title="Fight Date",
            yaxis_title="Strikes Landed",
            height=400,
        )

    return fig


@callback(
    Output("strikes-comparison", "figure"),
    [
        Input("fighter-select", "value"),
        Input("date-range", "start_date"),
        Input("date-range", "end_date"),
        Input("decision-filter", "value"),
        Input("division-filter", "value"),
    ],
)
def update_strikes_comparison(
    fighter: str,
    start_date: str | None,
    end_date: str | None,
    decisions: list[str] | None,
    divisions: list[str] | None,
):
    df_filtered = filter_data(df, fighter, start_date, end_date, decisions, divisions)

    if df_filtered.empty:
        fig = px.bar(title=f"No data for {fighter}")
    else:
        comparison = (
            df_filtered.groupby(["fight_uid", "event_date"])
            .agg({
                "total_strikes_landed": "sum",
                "opponent_strikes_landed": "sum",
            })
            .reset_index()
            .sort_values("event_date")
        )

        comparison["event_date"] = comparison["event_date"].dt.strftime("%Y-%m-%d")

        fig = go.Figure()
        fig.add_trace(
            go.Bar(
                x=comparison["event_date"],
                y=comparison["total_strikes_landed"],
                name="Fighter Strikes Landed",
                marker_color="green",
            )
        )
        fig.add_trace(
            go.Bar(
                x=comparison["event_date"],
                y=comparison["opponent_strikes_landed"],
                name="Opponent Strikes Landed",
                marker_color="red",
            )
        )

        fig.update_layout(
            barmode="group",
            title=f"{fighter} - Strikes Landed vs Absorbed",
            xaxis_title="Fight Date",
            yaxis_title="Strikes Landed",
            height=400,
        )

    return fig


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8050)
