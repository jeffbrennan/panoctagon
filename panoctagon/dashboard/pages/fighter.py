from typing import Any

import dash_mantine_components as dmc
import plotly.express as px
import plotly.graph_objects as go
import polars as pl
from dash import ALL, Input, Output, callback, ctx, dash_table, html

from panoctagon.dashboard.common import (
    PLACEHOLDER_IMAGE,
    PLOT_COLORS,
    apply_figure_styling,
    create_plot_with_title,
    filter_data,
    get_headshot_base64,
    get_main_data,
)


def get_fighter_uid_map(df: pl.DataFrame) -> dict[str, str]:
    result = (
        df.group_by("fighter_name")
        .agg(pl.col("fighter_uid").first())
        .select(["fighter_name", "fighter_uid"])
        .to_dict(as_series=False)
    )
    return dict(zip(result["fighter_name"], result["fighter_uid"]))


def get_fighter_summary(df_fighter: pl.DataFrame) -> dict[str, Any]:
    if df_fighter.height == 0:
        return {
            "total_fights": 0,
            "wins": 0,
            "losses": 0,
            "draws": 0,
            "no_contests": 0,
            "finish_rate": 0,
        }

    fights = df_fighter.group_by("fight_uid").agg(pl.col("fighter_result").first())

    total_fights = len(fights)
    wins = (fights["fighter_result"] == "WIN").sum()
    losses = (fights["fighter_result"] == "LOSS").sum()
    draws = (fights["fighter_result"] == "DRAW").sum()
    no_contests = (fights["fighter_result"] == "NO_CONTEST").sum()

    finish_decisions = ["KO", "TKO", "SUB", "Submission"]
    finishes = (
        df_fighter.filter(pl.col("decision").is_in(finish_decisions)).select("fight_uid").n_unique()
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


def get_fighter_list(df: pl.DataFrame) -> list[str]:
    fighter_counts = (
        df.group_by("fighter_name")
        .agg(pl.col("fight_uid").n_unique().alias("fight_count"))
        .sort("fight_count", descending=True)
    )

    return fighter_counts["fighter_name"].to_list()


def get_fighter_nickname_map(df: pl.DataFrame) -> dict[str, str | None]:
    result = (
        df.group_by("fighter_name")
        .agg(pl.col("nickname").first())
        .select(["fighter_name", "nickname"])
        .to_dict(as_series=False)
    )
    return dict(zip(result["fighter_name"], result["nickname"]))


def get_fighter_stance_map(df: pl.DataFrame) -> dict[str, str | None]:
    result = (
        df.group_by("fighter_name")
        .agg(pl.col("stance").first())
        .select(["fighter_name", "stance"])
        .to_dict(as_series=False)
    )
    return dict(zip(result["fighter_name"], result["stance"]))


def get_fighter_style_map(df: pl.DataFrame) -> dict[str, str | None]:
    result = (
        df.group_by("fighter_name")
        .agg(pl.col("style").first())
        .select(["fighter_name", "style"])
        .to_dict(as_series=False)
    )
    return dict(zip(result["fighter_name"], result["style"]))


@callback(
    [
        Output("fighter-headshot", "src"),
        Output("fighter-nickname", "children"),
        Output("fighter-stance", "children"),
        Output("fighter-style", "children"),
    ],
    [Input("fighter-select", "value")],
)
def update_headshot(fighter: str):
    fighter_uid_map = get_fighter_uid_map(df)
    fighter_nickname_map = get_fighter_nickname_map(df)
    fighter_stance_map = get_fighter_stance_map(df)
    fighter_style_map = get_fighter_style_map(df)

    fighter_uid = fighter_uid_map.get(fighter)
    nickname = fighter_nickname_map.get(fighter)
    stance = fighter_stance_map.get(fighter)
    style = fighter_style_map.get(fighter)

    if not fighter_uid:
        return PLACEHOLDER_IMAGE, "", "", ""

    headshot = get_headshot_base64(fighter_uid)
    nickname_text = nickname if nickname else ""
    stance_text = stance if stance else ""
    style_text = style if style else ""
    return headshot, nickname_text, stance_text, style_text


@callback(
    [
        Output("total-fights", "children"),
        Output("record", "children"),
        Output("finish-rate", "children"),
        Output("strikes-landed", "children"),
        Output("strikes-absorbed", "children"),
    ],
    [Input("fighter-select", "value")],
)
def update_summary_cards(fighter: str):
    df_filtered = filter_data(df, fighter)
    summary = get_fighter_summary(df_filtered)

    record = f"{summary['wins']}-{summary['losses']}-{summary['draws']}"
    if summary["no_contests"] > 0:
        record += f" ({summary['no_contests']} NC)"

    strikes_landed = int(df_filtered["total_strikes_landed"].sum())
    strikes_absorbed = int(df_filtered["opponent_strikes_landed"].sum())

    return (
        str(summary["total_fights"]),
        record,
        f"{summary['finish_rate']:.1f}%",
        f"{strikes_landed:,}",
        f"{strikes_absorbed:,}",
    )


@callback(
    Output("career-timeline", "figure"),
    [Input("fighter-select", "value")],
)
def update_career_timeline(fighter: str):
    df_filtered = filter_data(df, fighter)

    if df_filtered.height == 0:
        fig = go.Figure()
        fig.update_layout(height=400)
        return apply_figure_styling(fig)

    fight_timeline = (
        df_filtered.group_by(
            [
                "fight_uid",
                "event_date",
                "fighter_result",
                "title",
                "opponent_name",
            ]
        )
        .agg(pl.col("opponent_strikes_landed").sum())
        .sort("event_date")
    )

    fight_timeline = fight_timeline.with_columns(
        pl.col("opponent_strikes_landed").cum_sum().alias("cumulative_absorbed")
    )

    color_map = {
        "WIN": PLOT_COLORS["win"],
        "LOSS": PLOT_COLORS["loss"],
        "DRAW": PLOT_COLORS["draw"],
        "NO_CONTEST": PLOT_COLORS["tertiary"],
    }
    marker_colors = [
        color_map.get(result, "gray") for result in fight_timeline["fighter_result"].to_list()
    ]

    result_map = {
        "WIN": "Beat",
        "LOSS": "Defeated by",
        "DRAW": "Draw vs",
        "NO_CONTEST": "No Contest vs",
    }

    hover_text = [
        f"<b>{row['title']}</b> | {row['event_date']}"
        f"<br>{result_map.get(row['fighter_result'])} <b>{row['opponent_name']}</b>"
        f"<br>+{row['opponent_strikes_landed']:,} strikes ({row['cumulative_absorbed']:,} total)"
        for row in fight_timeline.iter_rows(named=True)
    ]

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=fight_timeline["event_date"].to_list(),
            y=fight_timeline["cumulative_absorbed"].to_list(),
            mode="lines+markers",
            line=dict(color="#1a1a1a", shape="spline", width=1),
            fill="tozeroy",
            fillcolor="rgba(26, 26, 26, 1)",
            marker=dict(size=18, color=marker_colors),
            showlegend=False,
            hovertext=hover_text,
            hoverinfo="text",
        )
    )

    for result in fight_timeline["fighter_result"].unique().to_list():
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
        yaxis_title="Cumulative Strikes Absorbed",
        height=400,
    )

    return apply_figure_styling(fig)


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


@callback(
    Output("win-method-chart", "figure"),
    [Input("fighter-select", "value")],
)
def update_win_method_chart(fighter: str):
    df_filtered = filter_data(df, fighter)

    if df_filtered.height == 0:
        fig = go.Figure()
        fig.update_layout(height=400)
        return apply_figure_styling(fig)

    df_wins = df_filtered.filter(pl.col("fighter_result") == "WIN")
    df_losses = df_filtered.filter(pl.col("fighter_result") == "LOSS")

    win_methods = df_wins.group_by("fight_uid").agg(pl.col("decision").first())
    win_counts = win_methods.group_by("decision").len().sort("len", descending=True)

    loss_methods = df_losses.group_by("fight_uid").agg(pl.col("decision").first())
    loss_counts = loss_methods.group_by("decision").len().sort("len", descending=True)

    fig = go.Figure()

    method_colors = {
        "KO": PLOT_COLORS["primary"],
        "TKO": PLOT_COLORS["secondary"],
        "SUB": PLOT_COLORS["tertiary"],
        "Submission": PLOT_COLORS["tertiary"],
        "UNANIMOUS_DECISION": PLOT_COLORS["quaternary"],
        "SPLIT_DECISION": "#b8b8b8",
        "MAJORITY_DECISION": "#c8c8c8",
        "DQ": PLOT_COLORS["neutral"],
        "DOC": PLOT_COLORS["neutral"],
    }

    if win_counts.height > 0:
        for row in win_counts.iter_rows(named=True):
            method = row["decision"]
            count = row["len"]
            fig.add_trace(
                go.Bar(
                    y=["Wins"],
                    x=[count],
                    name=method,
                    orientation="h",
                    text=f"{method} ({count})",
                    textposition="inside",
                    marker_color=method_colors.get(method, PLOT_COLORS["neutral"]),
                )
            )

    if loss_counts.height > 0:
        win_methods_set = set(win_counts["decision"].to_list())
        for row in loss_counts.iter_rows(named=True):
            method = row["decision"]
            count = row["len"]
            fig.add_trace(
                go.Bar(
                    y=["Losses"],
                    x=[count],
                    name=method,
                    orientation="h",
                    text=f"{method} ({count})",
                    textposition="inside",
                    showlegend=method not in win_methods_set,
                    marker_color=method_colors.get(method, PLOT_COLORS["neutral"]),
                )
            )

    fig.update_layout(
        barmode="stack",
        height=400,
        showlegend=True,
        legend=dict(orientation="v", yanchor="middle", y=0.5, xanchor="left", x=1.02),
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

    if df_filtered.height == 0:
        return [], [], []

    table_df = (
        df_filtered.group_by("fight_uid")
        .agg(
            [
                pl.col("event_date").first(),
                pl.col("opponent_name").first(),
                pl.col("fighter_result").first(),
                pl.col("decision").first(),
                pl.col("decision_round").first(),
                pl.col("total_strikes_landed").sum(),
                pl.col("total_strikes_attempted").sum(),
                pl.col("takedowns_landed").sum(),
            ]
        )
        .sort("event_date", descending=True)
    )

    table_df = table_df.with_columns(
        [
            pl.col("event_date").dt.to_string("%Y-%m-%d"),
            pl.col("decision").map_elements(format_decision, return_dtype=pl.String),
            pl.col("fighter_result").map_elements(format_result, return_dtype=pl.String),
        ]
    )

    table_df = table_df.rename(
        {
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
    table_df = table_df.select(column_order)

    columns = [{"name": col, "id": col} for col in column_order]

    data = table_df.to_dicts()

    style_conditional = [{"if": {"row_index": "odd"}, "backgroundColor": "rgba(0,0,0,0.03)"}]

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

    if df_filtered.height == 0:
        fig = px.line()
    else:
        fight_accuracy = (
            df_filtered.group_by(["fight_uid", "event_date"])
            .agg(
                [
                    pl.col("total_strikes_landed").sum(),
                    pl.col("total_strikes_attempted").sum(),
                ]
            )
            .filter(pl.col("total_strikes_attempted") > 0)
            .with_columns(
                (pl.col("total_strikes_landed") / pl.col("total_strikes_attempted") * 100).alias(
                    "accuracy"
                )
            )
            .sort("event_date")
        )

        fig = px.line(
            fight_accuracy.to_pandas(),
            x="event_date",
            y="accuracy",
            markers=True,
        )
        fig.update_traces(
            line_color=PLOT_COLORS["primary"],
            marker_color=PLOT_COLORS["primary"],
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

    if df_filtered.height == 0:
        fig = px.bar()
    else:
        strike_targets = (
            df_filtered.group_by(["fight_uid", "event_date"])
            .agg(
                [
                    pl.col("sig_strikes_head_landed").sum(),
                    pl.col("sig_strikes_body_landed").sum(),
                    pl.col("sig_strikes_leg_landed").sum(),
                ]
            )
            .sort("event_date")
            .with_columns(pl.col("event_date").dt.to_string("%Y-%m-%d"))
        )

        fig = go.Figure()
        fig.add_trace(
            go.Bar(
                x=strike_targets["event_date"].to_list(),
                y=strike_targets["sig_strikes_head_landed"].to_list(),
                name="Head",
                marker_color=PLOT_COLORS["head"],
            )
        )
        fig.add_trace(
            go.Bar(
                x=strike_targets["event_date"].to_list(),
                y=strike_targets["sig_strikes_body_landed"].to_list(),
                name="Body",
                marker_color=PLOT_COLORS["body"],
            )
        )
        fig.add_trace(
            go.Bar(
                x=strike_targets["event_date"].to_list(),
                y=strike_targets["sig_strikes_leg_landed"].to_list(),
                name="Leg",
                marker_color=PLOT_COLORS["leg"],
            )
        )

        fig.update_layout(
            barmode="stack",
            yaxis_title="Strikes Landed",
            height=400,
        )

    return apply_figure_styling(fig)


@callback(
    [
        Output("top-level-tabs", "value"),
        Output("fighter-select", "value"),
    ],
    Input({"type": "view-fighter-btn", "index": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def navigate_to_fighter(n_clicks):
    if not any(n_clicks):
        return "upcoming", initial_fighter

    triggered = ctx.triggered_id
    if triggered and isinstance(triggered, dict):
        fighter_name = triggered["index"]
        if fighter_name in fighter_options:
            return "analysis", fighter_name

    return "upcoming", initial_fighter


df = get_main_data()
initial_fighter = df.sample(1)["fighter_name"].item()
fighter_options = get_fighter_list(df)

fighter_analysis_content = html.Div(
    [
        dmc.Group(
            [
                html.Img(
                    id="fighter-headshot",
                    style={
                        "width": "237px",
                        "height": "150px",
                        "border": "2px solid #1a1a1a",
                        "borderRadius": "4px",
                    },
                ),
                html.Div(
                    [
                        dmc.Select(
                            label="",
                            placeholder="Select fighter",
                            id="fighter-select",
                            value=initial_fighter,
                            data=fighter_options,
                            searchable=True,
                            clearable=False,
                            style={"width": "250px"},
                        ),
                        dmc.Group(
                            [
                                html.Div(
                                    [
                                        dmc.Text(
                                            "Nickname",
                                            size="xs",
                                            c="gray",
                                            style={"height": "14px"},
                                        ),
                                        dmc.Text(
                                            id="fighter-nickname",
                                            size="sm",
                                            style={"minHeight": "18px"},
                                        ),
                                    ]
                                ),
                                html.Div(
                                    [
                                        dmc.Text(
                                            "Stance",
                                            size="xs",
                                            c="gray",
                                            style={"height": "14px"},
                                        ),
                                        dmc.Text(
                                            id="fighter-stance",
                                            size="sm",
                                            style={"minHeight": "18px"},
                                        ),
                                    ]
                                ),
                                html.Div(
                                    [
                                        dmc.Text(
                                            "Style",
                                            size="xs",
                                            c="gray",
                                            style={"height": "14px"},
                                        ),
                                        dmc.Text(
                                            id="fighter-style",
                                            size="sm",
                                            style={"minHeight": "18px"},
                                        ),
                                    ]
                                ),
                            ],
                            gap="md",
                            mt="md",
                        ),
                    ]
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
                            "Profile",
                            value="profile",
                        ),
                        dmc.TabsTab("History", value="history"),
                        dmc.TabsTab(
                            "Striking",
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
                                dmc.Card(
                                    [
                                        dmc.Text(
                                            "Strikes Landed",
                                            size="sm",
                                            c="gray",
                                        ),
                                        dmc.Title(
                                            id="strikes-landed",
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
                                            "Strikes Absorbed",
                                            size="sm",
                                            c="gray",
                                        ),
                                        dmc.Title(
                                            id="strikes-absorbed",
                                            order=2,
                                        ),
                                    ],
                                    shadow="sm",
                                    withBorder=True,
                                    p="lg",
                                ),
                            ],
                            cols=5,
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
                        style_cell_conditional=[  # type: ignore[arg-type]
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
    ]
)
