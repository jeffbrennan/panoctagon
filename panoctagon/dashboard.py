import base64
from pathlib import Path
from typing import Any

import dash_mantine_components as dmc
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import Dash, Input, Output, callback, dash_table, dcc, html

from panoctagon.common import get_engine

HEADSHOTS_DIR = Path(__file__).parent.parent / "data" / "raw" / "ufc" / "fighter_headshots"


def apply_figure_styling(fig: go.Figure) -> go.Figure:
    fig.update_layout(
        plot_bgcolor="rgb(242, 240, 227)",
        paper_bgcolor="rgb(242, 240, 227)",
        font=dict(family="JetBrains Mono, monospace", color="#1a1a1a"),
        title=None,
        margin=dict(l=10, r=10, t=0, b=10),
    )
    fig.update_xaxes(
        showgrid=False,
        zeroline=False,
        showline=True,
        linewidth=2,
        linecolor="black",
        mirror=True,
    )
    fig.update_yaxes(
        showgrid=False,
        zeroline=False,
        showline=True,
        linewidth=2,
        linecolor="black",
        mirror=True,
    )
    return fig


def create_plot_with_title(
    title: str, graph_id: str, margin_bottom: bool = False
) -> html.Div:
    return html.Div(
        [
            html.Div(
                title,
                className="plot-title",
            ),
            html.Div(
                dcc.Graph(id=graph_id, figure={}),
                className="plot-container-wrapper",
            ),
        ],
        style={"marginBottom": "0rem"} if margin_bottom else {},
    )


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
            fs.fighter_uid,
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


def get_fighter_uid_map(df: pd.DataFrame) -> dict[str, str]:
    return (
        df.groupby("fighter_name")
        .agg({"fighter_uid": "first"})
        .reset_index()
        .set_index("fighter_name")["fighter_uid"]
        .to_dict()
    )


def get_headshot_base64(fighter_uid: str) -> str | None:
    headshot_path = HEADSHOTS_DIR / f"{fighter_uid}_headshot.png"
    if not headshot_path.exists():
        return None
    with open(headshot_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")
    return f"data:image/png;base64,{encoded}"


df = get_main_data()
fighter_options = get_fighter_list(df)
fighter_uid_map = get_fighter_uid_map(df)

initial_fighter = df.sample(1)["fighter_name"].item()
if not isinstance(initial_fighter, str):
    raise TypeError()

most_recent_event = df["event_date"].max().strftime("%Y-%m-%d")

assets_path = Path(__file__).parent / "assets"
app = Dash(__name__, assets_folder=str(assets_path))
server = app.server

app.layout = dmc.MantineProvider(
    html.Div(
        id="panoctagon-page",
        children=dmc.AppShell(
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
                            dmc.Group(
                                [
                                    html.Img(
                                        id="fighter-headshot",
                                        style={
                                            "height": "150px",
                                            "border": "2px solid #1a1a1a",
                                            "borderRadius": "4px",
                                        },
                                    ),
                                    dmc.Select(
                                        label="Fighter",
                                        placeholder="Select fighter",
                                        id="fighter-select",
                                        value=initial_fighter,
                                        data=fighter_options,
                                        searchable=True,
                                        clearable=False,
                                        style={"width": "250px"},
                                    ),
                                ],
                                align="flex-start",
                                gap="lg",
                                mb="md",
                            ),
                            dmc.Tabs(
                                [
                                    dmc.TabsList(
                                        [
                                            dmc.TabsTab(
                                                "Fighter Profile",
                                                value="profile",
                                            ),
                                            dmc.TabsTab(
                                                "Fight History", value="history"
                                            ),
                                            dmc.TabsTab(
                                                "Striking Analytics",
                                                value="striking",
                                            ),
                                        ]
                                    ),
                                    dmc.TabsPanel(
                                        [
                                            dmc.SimpleGrid(
                                                [
                                                    dmc.Card(
                                                        [
                                                            dmc.Text(
                                                                "Total Fights",
                                                                size="sm",
                                                                c="gray",
                                                            ),
                                                            dmc.Title(
                                                                id="total-fights",
                                                                order=2,
                                                            ),
                                                        ],
                                                        shadow="sm",
                                                        withBorder=True,
                                                        p="lg",
                                                    ),
                                                    dmc.Card(
                                                        [
                                                            dmc.Text(
                                                                "Record",
                                                                size="sm",
                                                                c="gray",
                                                            ),
                                                            dmc.Title(
                                                                id="record",
                                                                order=2,
                                                            ),
                                                        ],
                                                        shadow="sm",
                                                        withBorder=True,
                                                        p="lg",
                                                    ),
                                                    dmc.Card(
                                                        [
                                                            dmc.Text(
                                                                "Finish Rate",
                                                                size="sm",
                                                                c="gray",
                                                            ),
                                                            dmc.Title(
                                                                id="finish-rate",
                                                                order=2,
                                                            ),
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
                                            create_plot_with_title(
                                                "Career Timeline",
                                                "career-timeline",
                                                margin_bottom=True,
                                            ),
                                            create_plot_with_title(
                                                "Fight Outcome Distribution",
                                                "win-method-chart",
                                            ),
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
                                                "height": "800px",
                                                "overflowY": "scroll",
                                            },
                                            style_data={
                                                "border": "none",
                                            },
                                            style_cell_conditional=[
                                                {
                                                    "if": {"column_id": ""},
                                                    "width": "40px",
                                                    "textAlign": "center",
                                                },
                                            ],
                                            style_data_conditional=[],
                                            style_header={
                                                "backgroundColor": "#e9ecef",
                                                "fontWeight": "bold",
                                                "border": "none",
                                            },
                                        ),
                                        value="history",
                                        pt="md",
                                    ),
                                    dmc.TabsPanel(
                                        [
                                            create_plot_with_title(
                                                "Striking Accuracy Over Time",
                                                "accuracy-trend",
                                                margin_bottom=True,
                                            ),
                                            create_plot_with_title(
                                                "Strike Target Distribution",
                                                "target-distribution",
                                                margin_bottom=True,
                                            ),
                                            create_plot_with_title(
                                                "Strikes Landed vs Absorbed",
                                                "strikes-comparison",
                                            ),
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
        ),
    )
)


def format_decision(decision: str) -> str:
    decision_map = {
        "UNANIMOUS_DECISION": "Unanimous Decision",
        "SPLIT_DECISION": "Split Decision",
        "MAJORITY_DECISION": "Majority Decision",
        "TKO": "TKO",
        "KO": "KO",
        "SUB": "Submission",
        "DQ": "DQ",
        "DOC": "Doctor Stoppage",
        "OVERTURNED": "Overturned",
        "COULD_NOT_CONTINUE": "Could Not Continue",
        "OTHER": "Other",
    }
    return decision_map.get(decision, decision)


def format_result(result: str) -> str:
    result_map = {
        "WIN": "W",
        "LOSS": "L",
        "DRAW": "D",
        "NO_CONTEST": "NC",
    }
    return result_map.get(result, result)


def filter_data(df: pd.DataFrame, fighter: str) -> pd.DataFrame:
    return df[df["fighter_name"] == fighter].copy()


def get_fighter_summary(df_fighter: pd.DataFrame) -> dict[str, Any]:
    if df_fighter.empty:
        return {
            "total_fights": 0,
            "wins": 0,
            "losses": 0,
            "draws": 0,
            "no_contests": 0,
            "finish_rate": 0,
        }

    fights = (
        df_fighter.groupby("fight_uid")
        .agg({"fighter_result": "first"})
        .reset_index()
    )

    total_fights = len(fights)
    wins = (fights["fighter_result"] == "WIN").sum()
    losses = (fights["fighter_result"] == "LOSS").sum()
    draws = (fights["fighter_result"] == "DRAW").sum()
    no_contests = (fights["fighter_result"] == "NO_CONTEST").sum()

    finish_decisions = ["KO", "TKO", "SUB", "Submission"]
    finishes = (
        df_fighter[df_fighter["decision"].isin(finish_decisions)]
        .groupby("fight_uid")
        .ngroups
    )
    finish_rate = (finishes / total_fights * 100) if total_fights > 0 else 0

    return {
        "total_fights": total_fights,
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "no_contests": no_contests,
        "finish_rate": finish_rate,
    }


@callback(
    Output("fighter-headshot", "src"),
    [Input("fighter-select", "value")],
)
def update_headshot(fighter: str):
    fighter_uid = fighter_uid_map.get(fighter)
    if not fighter_uid:
        return ""
    headshot = get_headshot_base64(fighter_uid)
    return headshot if headshot else ""


@callback(
    [
        Output("total-fights", "children"),
        Output("record", "children"),
        Output("finish-rate", "children"),
    ],
    [Input("fighter-select", "value")],
)
def update_summary_cards(fighter: str):
    df_filtered = filter_data(df, fighter)
    summary = get_fighter_summary(df_filtered)

    record = f"{summary['wins']}-{summary['losses']}-{summary['draws']}"
    if summary["no_contests"] > 0:
        record += f" ({summary['no_contests']} NC)"

    return (
        str(summary["total_fights"]),
        record,
        f"{summary['finish_rate']:.1f}%",
    )


@callback(
    Output("career-timeline", "figure"),
    [Input("fighter-select", "value")],
)
def update_career_timeline(fighter: str):
    df_filtered = filter_data(df, fighter)

    if df_filtered.empty:
        fig = go.Figure()
        fig.update_layout(height=400)
        return apply_figure_styling(fig)

    fight_timeline = (
        df_filtered.groupby(
            [
                "fight_uid",
                "event_date",
                "fighter_result",
                "title",
                "opponent_name",
            ]
        )
        .agg(
            {
                "opponent_strikes_landed": "sum",
            }
        )
        .reset_index()
        .sort_values("event_date")  # type: ignore
    )

    color_map = {
        "WIN": "green",
        "LOSS": "red",
        "DRAW": "gray",
        "NO_CONTEST": "orange",
    }
    marker_colors = [
        color_map.get(result, "gray")
        for result in fight_timeline["fighter_result"]
    ]

    result_map = {
        "WIN": "Beat",
        "LOSS": "Defeated by",
        "DRAW": "Draw vs",
        "NO_CONTEST": "No Contest vs",
    }

    hover_text = [
        f"<b>{row['title']}</b> | {row['event_date'].strftime('%Y-%m-%d')}"
        f"<br>{result_map.get(row['fighter_result'])} <b>{row['opponent_name']}</b>"
        f"<br>absorbed <b>{row['opponent_strikes_landed']}</b> strikes"
        for _, row in fight_timeline.iterrows()
    ]

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=fight_timeline["event_date"],
            y=fight_timeline["opponent_strikes_landed"],
            mode="lines+markers",
            line=dict(color="lightgray", shape="spline", width=2),
            marker=dict(
                size=10, color=marker_colors, line=dict(width=1, color="white")
            ),
            showlegend=False,
            hovertext=hover_text,
            hoverinfo="text",
        )
    )

    for result in fight_timeline["fighter_result"].unique():
        fig.add_trace(
            go.Scatter(
                x=[None],
                y=[None],
                mode="markers",
                marker=dict(size=10, color=color_map.get(result, "gray")),
                name=result,
            )
        )

    fig.update_layout(
        yaxis_title="Strikes Absorbed",
        height=400,
    )

    return apply_figure_styling(fig)


@callback(
    Output("win-method-chart", "figure"),
    [Input("fighter-select", "value")],
)
def update_win_method_chart(fighter: str):
    df_filtered = filter_data(df, fighter)

    if df_filtered.empty:
        fig = go.Figure()
        fig.update_layout(height=400)
        return apply_figure_styling(fig)

    df_wins = df_filtered[df_filtered["fighter_result"] == "WIN"]
    df_losses = df_filtered[df_filtered["fighter_result"] == "LOSS"]

    win_methods = (
        df_wins.groupby("fight_uid").agg({"decision": "first"}).reset_index()
    )
    win_counts = win_methods["decision"].value_counts()

    loss_methods = (
        df_losses.groupby("fight_uid").agg({"decision": "first"}).reset_index()
    )
    loss_counts = loss_methods["decision"].value_counts()

    fig = go.Figure()

    if not win_counts.empty:
        for method in win_counts.index:
            fig.add_trace(
                go.Bar(
                    y=["Wins"],
                    x=[win_counts[method]],
                    name=method,
                    orientation="h",
                    text=f"{method} ({win_counts[method]})",
                    textposition="inside",
                )
            )

    if not loss_counts.empty:
        for method in loss_counts.index:
            fig.add_trace(
                go.Bar(
                    y=["Losses"],
                    x=[loss_counts[method]],
                    name=method,
                    orientation="h",
                    text=f"{method} ({loss_counts[method]})",
                    textposition="inside",
                    showlegend=method not in win_counts.index,
                )
            )

    fig.update_layout(
        barmode="stack",
        height=400,
        showlegend=True,
        legend=dict(
            orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.02
        ),
    )

    return apply_figure_styling(fig)


@callback(
    [
        Output("fight-history-table", "columns"),
        Output("fight-history-table", "data"),
        Output("fight-history-table", "style_data_conditional"),
    ],
    [Input("fighter-select", "value")],
)
def update_fight_history(fighter: str):
    df_filtered = filter_data(df, fighter)

    if df_filtered.empty:
        return [], [], []

    table_df = (
        df_filtered.groupby("fight_uid")
        .agg(
            {
                "event_date": "first",
                "opponent_name": "first",
                "fighter_result": "first",
                "decision": "first",
                "decision_round": "first",
                "total_strikes_landed": "sum",
                "total_strikes_attempted": "sum",
                "takedowns_landed": "sum",
            }
        )
        .reset_index()
        .sort_values("event_date", ascending=False)
    )

    table_df["event_date"] = table_df["event_date"].dt.strftime("%Y-%m-%d")
    table_df["decision"] = table_df["decision"].apply(format_decision)
    table_df["fighter_result"] = table_df["fighter_result"].apply(format_result)
    table_df = table_df.rename(
        columns={
            "event_date": "Date",
            "opponent_name": "Opponent",
            "fighter_result": "",
            "decision": "Method",
            "decision_round": "Round",
            "total_strikes_landed": "Strikes Landed",
            "total_strikes_attempted": "Strikes Attempted",
            "takedowns_landed": "Takedowns",
        }
    )

    column_order = [
        "",
        "Date",
        "Opponent",
        "Method",
        "Round",
        "Strikes Landed",
        "Strikes Attempted",
        "Takedowns",
    ]
    table_df = table_df[column_order]

    columns = [{"name": col, "id": col} for col in column_order]

    data = table_df.to_dict("records")

    style_conditional = [
        {"if": {"row_index": "odd"}, "backgroundColor": "rgba(0,0,0,0.03)"}
    ]

    for i, row in enumerate(data):
        result = row.get("", "")
        if result == "W":
            style_conditional.append(
                {
                    "if": {"row_index": i, "column_id": ""},
                    "backgroundColor": "#d4edda",
                    "color": "darkgreen",
                    "fontWeight": "bold",
                }
            )
        elif result == "L":
            style_conditional.append(
                {
                    "if": {"row_index": i, "column_id": ""},
                    "backgroundColor": "#f8d7da",
                    "color": "darkred",
                    "fontWeight": "bold",
                }
            )

    return columns, data, style_conditional


@callback(
    Output("accuracy-trend", "figure"),
    [Input("fighter-select", "value")],
)
def update_accuracy_trend(fighter: str):
    df_filtered = filter_data(df, fighter)

    if df_filtered.empty:
        fig = px.line()
    else:
        fight_accuracy = (
            df_filtered.groupby(["fight_uid", "event_date"])
            .agg(
                {
                    "total_strikes_landed": "sum",
                    "total_strikes_attempted": "sum",
                }
            )
            .reset_index()
        )
        fight_accuracy = fight_accuracy[
            fight_accuracy["total_strikes_attempted"] > 0
        ]
        fight_accuracy["accuracy"] = (
            fight_accuracy["total_strikes_landed"]
            / fight_accuracy["total_strikes_attempted"]
            * 100
        )
        fight_accuracy = fight_accuracy.sort_values("event_date")  # type: ignore

        fig = px.line(
            fight_accuracy,
            x="event_date",
            y="accuracy",
            markers=True,
        )
        fig.update_yaxes(title="Accuracy (%)", range=[0, 100])

    fig.update_layout(height=400)
    return apply_figure_styling(fig)


@callback(
    Output("target-distribution", "figure"),
    [Input("fighter-select", "value")],
)
def update_target_distribution(fighter: str):
    df_filtered = filter_data(df, fighter)

    if df_filtered.empty:
        fig = px.bar()
    else:
        strike_targets = (
            df_filtered.groupby(["fight_uid", "event_date"])
            .agg(
                {
                    "sig_strikes_head_landed": "sum",
                    "sig_strikes_body_landed": "sum",
                    "sig_strikes_leg_landed": "sum",
                }
            )
            .reset_index()
            .sort_values("event_date")  # type: ignore
        )

        strike_targets["event_date"] = strike_targets["event_date"].dt.strftime(
            "%Y-%m-%d"
        )

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
            yaxis_title="Strikes Landed",
            height=400,
        )

    return apply_figure_styling(fig)


@callback(
    Output("strikes-comparison", "figure"),
    [Input("fighter-select", "value")],
)
def update_strikes_comparison(fighter: str):
    df_filtered = filter_data(df, fighter)

    if df_filtered.empty:
        fig = px.bar()
    else:
        comparison = (
            df_filtered.groupby(["fight_uid", "event_date"])
            .agg(
                {
                    "total_strikes_landed": "sum",
                    "opponent_strikes_landed": "sum",
                }
            )
            .reset_index()
            .sort_values("event_date")  # type: ignore
        )

        comparison["event_date"] = comparison["event_date"].dt.strftime(
            "%Y-%m-%d"
        )

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
            barmode="stack",
            yaxis_title="Strikes Landed",
            height=400,
        )

    return apply_figure_styling(fig)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8050)
