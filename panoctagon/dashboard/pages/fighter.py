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
from panoctagon.enums import format_decision, format_result


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
                "decision",
                "closing_odds",
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
        "NO_CONTEST": PLOT_COLORS["l3"],
    }
    border_map = {
        "WIN": PLOT_COLORS["loss"],
        "LOSS": PLOT_COLORS["win"],
        "DRAW": PLOT_COLORS["win"],
        "NO_CONTEST": PLOT_COLORS["win"],
    }

    marker_colors = [
        color_map.get(result, "gray") for result in fight_timeline["fighter_result"].to_list()
    ]
    border_colors = [
        border_map.get(result, "gray") for result in fight_timeline["fighter_result"].to_list()
    ]

    result_map = {
        "WIN": "Beat",
        "LOSS": "Defeated by",
        "DRAW": "Draw vs",
        "NO_CONTEST": "No Contest vs",
    }

    decision_abbrev = {
        "KO": "KO",
        "TKO": "TKO",
        "SUB": "SUB",
        "UNANIMOUS_DECISION": "UD",
        "SPLIT_DECISION": "SD",
        "MAJORITY_DECISION": "MD",
        "DQ": "DQ",
        "DOC": "DOC",
    }

    def format_odds_hover(odds: int | None) -> str:
        if odds is None:
            return ""
        odds_str = f"+{odds}" if odds > 0 else str(odds)
        return f"<br>Odds: {odds_str}"

    hover_text = [
        f"<b>{row['title']}</b> | {row['event_date']}"
        f"<br>{result_map.get(row['fighter_result'])} <b>{row['opponent_name']}</b>"
        f" ({decision_abbrev.get(row['decision'], row['decision'])})"
        f"<br>+{row['opponent_strikes_landed']:,} strikes ({row['cumulative_absorbed']:,} total)"
        f"{format_odds_hover(row['closing_odds'])}"
        for row in fight_timeline.iter_rows(named=True)
    ]

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=fight_timeline["event_date"].to_list(),
            y=fight_timeline["cumulative_absorbed"].to_list(),
            mode="lines+markers",
            line=dict(color=PLOT_COLORS["l1"], shape="spline", width=1),
            fill="tozeroy",
            fillcolor=PLOT_COLORS["l1"],
            marker=dict(size=18, color=marker_colors, line=dict(width=2, color=border_colors)),
            showlegend=False,
            hovertext=hover_text,
            hoverinfo="text",
        )
    )

    for row in fight_timeline.iter_rows(named=True):
        odds = row["closing_odds"]
        if odds is not None:
            label = "FAV" if odds < 0 else "DOG"
            fig.add_annotation(
                x=row["event_date"],
                y=row["cumulative_absorbed"],
                text=label,
                showarrow=False,
                yshift=18,
                font=dict(size=9, color=PLOT_COLORS["l4"]),
            )

    for result in fight_timeline["fighter_result"].unique().to_list():
        fig.add_trace(
            go.Scatter(
                x=[None],
                y=[None],
                mode="markers",
                marker=dict(
                    size=10,
                    color=color_map.get(result, "gray"),
                    line=dict(width=2, color=PLOT_COLORS["l1"]),
                ),
                name=result,
            )
        )

    fig.update_layout(
        yaxis_title="Cumulative Strikes Absorbed",
        height=400,
    )

    return apply_figure_styling(fig)


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

    fights = (
        df_filtered.group_by("fight_uid")
        .agg(
            [
                pl.col("decision").first(),
                pl.col("fighter_result").first(),
                pl.col("opponent_name").first(),
                pl.col("event_date").first(),
            ]
        )
        .with_columns(pl.col("event_date").dt.year().cast(pl.String).alias("year"))
    )

    df_wins = fights.filter(pl.col("fighter_result") == "WIN")
    df_losses = fights.filter(pl.col("fighter_result") == "LOSS")

    win_counts = df_wins.group_by("decision").len()
    loss_counts = df_losses.group_by("decision").len()
    win_count_map = dict(zip(win_counts["decision"].to_list(), win_counts["len"].to_list()))
    loss_count_map = dict(zip(loss_counts["decision"].to_list(), loss_counts["len"].to_list()))

    method_colors = {
        "KO": PLOT_COLORS["l1"],
        "DOC": PLOT_COLORS["l1"],
        "TKO": PLOT_COLORS["l3"],
        "SUB": PLOT_COLORS["l5"],
        "UNANIMOUS_DECISION": PLOT_COLORS["l6"],
        "SPLIT_DECISION": PLOT_COLORS["l7"],
        "MAJORITY_DECISION": PLOT_COLORS["l7"],
        "DQ": PLOT_COLORS["l7"],
    }

    method_labels = {
        "KO": "KO",
        "TKO": "TKO",
        "SUB": "Submission",
        "UNANIMOUS_DECISION": "Unanimous Decision",
        "SPLIT_DECISION": "Split Decision",
        "MAJORITY_DECISION": "Majority Decision",
        "DQ": "DQ",
        "DOC": "Doctor",
    }

    def build_method_hover(method: str, method_fights: pl.DataFrame) -> str:
        subset = method_fights.filter(pl.col("decision") == method)
        lines = [f"<b>{method_labels[method]}</b> ({subset.height})", ""]
        by_year = (
            subset.group_by("year")
            .agg(pl.col("opponent_name").sort())
            .sort("year", descending=True)
        )
        for row in by_year.iter_rows(named=True):
            lines.append(f"<b>{row['year']}</b>")
            lines.append(f"  {', '.join(row['opponent_name'])}")
        return "<br>".join(lines)

    fig = go.Figure()

    for method in method_colors:
        if method in win_count_map:
            fig.add_trace(
                go.Bar(
                    y=["Wins"],
                    x=[win_count_map[method]],
                    name=method_labels[method],
                    orientation="h",
                    marker_color=method_colors[method],
                    hovertext=[build_method_hover(method, df_wins)],
                    hoverinfo="text",
                )
            )
        if method in loss_count_map:
            fig.add_trace(
                go.Bar(
                    y=["Losses"],
                    x=[loss_count_map[method]],
                    name=method_labels[method],
                    orientation="h",
                    showlegend=method not in win_count_map,
                    marker_color=method_colors[method],
                    hovertext=[build_method_hover(method, df_losses)],
                    hoverinfo="text",
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
                pl.col("closing_odds").first(),
            ]
        )
        .sort("event_date", descending=True)
    )

    def format_odds(odds: float | None) -> str:
        if odds is None:
            return "-"
        odds_int = int(odds)
        return f"+{odds_int}" if odds_int > 0 else str(odds_int)

    table_df = table_df.with_columns(
        [
            pl.col("event_date").dt.to_string("%Y-%m-%d"),
            pl.col("decision").map_elements(format_decision, return_dtype=pl.String),
            pl.col("fighter_result").map_elements(format_result, return_dtype=pl.String),
            pl.col("closing_odds").map_elements(format_odds, return_dtype=pl.String).alias("closing_odds"),
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
            "closing_odds": "Odds",
        }
    )

    column_order = [
        "",
        "Date",
        "Opponent",
        "Odds",
        "Method",
        "Round",
        "Strikes Landed",
        "Strikes Attempted",
        "Takedowns",
    ]
    table_df = table_df.select(column_order)

    columns = [{"name": col, "id": col} for col in column_order]

    data = table_df.to_dicts()

    style_conditional = [
        {"if": {"row_index": "odd"}, "backgroundColor": PLOT_COLORS["win"]},
        {"if": {"row_index": "even"}, "backgroundColor": PLOT_COLORS["win"]},
    ]
    for i, row in enumerate(data):
        result = row.get("", "")
        if result == "W":
            style_conditional.append(
                {
                    "if": {"row_index": i, "column_id": ""},
                    "backgroundColor": PLOT_COLORS["win"],
                    "color": PLOT_COLORS["loss"],
                    "fontWeight": "bold",
                }
            )
        elif result in ["L", "D", "NC"]:
            style_conditional.append(
                {
                    "if": {"row_index": i, "column_id": ""},
                    "backgroundColor": PLOT_COLORS["loss"],
                    "color": PLOT_COLORS["win"],
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
        fig = go.Figure()
    else:
        fight_accuracy = (
            df_filtered.group_by(["fight_uid", "event_date"])
            .agg(
                [
                    pl.col("title").first(),
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

        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=fight_accuracy["event_date"].to_list(),
                y=fight_accuracy["accuracy"].to_list(),
                mode="lines+markers",
                line=dict(color=PLOT_COLORS["l1"]),
                marker=dict(color=PLOT_COLORS["l1"]),
                showlegend=False,
                customdata=list(
                    zip(
                        fight_accuracy["title"].to_list(),
                        fight_accuracy["total_strikes_landed"].to_list(),
                        fight_accuracy["total_strikes_attempted"].to_list(),
                    )
                ),
                hovertemplate="<b>%{customdata[0]}</b> | %{x}<br>Accuracy: %{y:.1f}%<br>Strikes: %{customdata[1]} / %{customdata[2]}<extra></extra>",
            )
        )
        fig.update_yaxes(title="Accuracy (%)", range=[0, 100])
        fig.update_xaxes(title=None)

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
                    pl.col("title").first(),
                    pl.col("fighter_result").first(),
                    pl.col("opponent_name").first(),
                    pl.col("sig_strikes_head_landed").sum(),
                    pl.col("sig_strikes_body_landed").sum(),
                    pl.col("sig_strikes_leg_landed").sum(),
                ]
            )
            .sort("event_date")
            .with_columns(
                pl.col("event_date").dt.to_string("%Y-%m-%d"),
                pl.col("fighter_result")
                .replace(
                    {
                        "WIN": "Beat",
                        "LOSS": "Defeated by",
                        "DRAW": "Draw vs",
                        "NO_CONTEST": "No Contest vs",
                    }
                )
                .alias("result_label"),
            )
        )

        customdata = list(
            zip(
                strike_targets["title"].to_list(),
                strike_targets["result_label"].to_list(),
                strike_targets["opponent_name"].to_list(),
            )
        )

        fig = go.Figure()
        fig.add_trace(
            go.Bar(
                x=strike_targets["event_date"].to_list(),
                y=strike_targets["sig_strikes_leg_landed"].to_list(),
                name="Leg",
                marker_color=PLOT_COLORS["leg"],
                customdata=customdata,
                hovertemplate="<b>%{customdata[0]}</b> | %{x}<br>%{customdata[1]} <b>%{customdata[2]}</b><br>Leg: %{y}<extra></extra>",
            )
        )
        fig.add_trace(
            go.Bar(
                x=strike_targets["event_date"].to_list(),
                y=strike_targets["sig_strikes_body_landed"].to_list(),
                name="Body",
                marker_color=PLOT_COLORS["body"],
                customdata=customdata,
                hovertemplate="<b>%{customdata[0]}</b> | %{x}<br>%{customdata[1]} <b>%{customdata[2]}</b><br>Body: %{y}<extra></extra>",
            )
        )
        fig.add_trace(
            go.Bar(
                x=strike_targets["event_date"].to_list(),
                y=strike_targets["sig_strikes_head_landed"].to_list(),
                name="Head",
                marker_color=PLOT_COLORS["head"],
                customdata=customdata,
                hovertemplate="<b>%{customdata[0]}</b> | %{x}<br>%{customdata[1]} <b>%{customdata[2]}</b><br>Head: %{y}<extra></extra>",
            )
        )

        fig.update_layout(
            barmode="stack",
            yaxis_title="Strikes Landed",
            height=400,
            legend=dict(traceorder="reversed"),
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
                            "backgroundColor": "#1a1a1a",
                            "color": "rgb(242, 240, 227)",
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
