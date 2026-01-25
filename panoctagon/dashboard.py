import base64
from pathlib import Path
from typing import Any

import dash_mantine_components as dmc
import networkx as nx
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


def create_plot_with_title(title: str, graph_id: str, margin_bottom: bool = False) -> html.Div:
    return html.Div(
        [
            html.Div(
                title,
                className="plot-title",
            ),
            html.Div(
                dcc.Graph(
                    id=graph_id,
                    figure={},
                    config={"displayModeBar": False},
                ),
                className="plot-container-wrapper",
            ),
        ],
        style={"marginBottom": "2rem"} if margin_bottom else {},
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
                    nickname,
                    stance,
                    style,
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
                    b.nickname,
                    b.stance,
                    b.style,
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
            fs.nickname,
            fs.stance,
            fs.style,
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


def get_network_data() -> pd.DataFrame:
    return pd.read_sql_query(
        """
        select
            a.fighter1_uid,
            a.fighter2_uid,
            f1.first_name || ' ' || f1.last_name as fighter1_name,
            f2.first_name || ' ' || f2.last_name as fighter2_name,
            count(*) as fight_count
        from ufc_fights a
        inner join ufc_fighters f1 on a.fighter1_uid = f1.fighter_uid
        inner join ufc_fighters f2 on a.fighter2_uid = f2.fighter_uid
        group by a.fighter1_uid, a.fighter2_uid, fighter1_name, fighter2_name
        """,
        get_engine(),
    )


def build_fighter_graph(network_df: pd.DataFrame) -> nx.Graph:
    G = nx.Graph()
    for _, row in network_df.iterrows():
        G.add_edge(
            row["fighter1_name"],
            row["fighter2_name"],
            weight=row["fight_count"],
        )
    return G


def get_subgraph_for_fighter(G: nx.Graph, fighter_name: str, depth: int = 2) -> nx.Graph:
    if fighter_name not in G:
        return nx.Graph()

    nodes = {fighter_name}
    current_level = {fighter_name}

    for _ in range(depth):
        next_level = set()
        for node in current_level:
            next_level.update(G.neighbors(node))
        nodes.update(next_level)
        current_level = next_level

    return G.subgraph(nodes).copy()


def create_network_figure(
    G: nx.Graph, center_fighter: str | None = None, highlight_path: list[str] | None = None
) -> go.Figure:
    if len(G.nodes()) == 0:
        fig = go.Figure()
        fig.update_layout(
            annotations=[
                dict(
                    text="No connections found",
                    xref="paper",
                    yref="paper",
                    x=0.5,
                    y=0.5,
                    showarrow=False,
                    font=dict(size=20),
                )
            ]
        )
        return apply_figure_styling(fig)

    pos = nx.spring_layout(G, k=2, iterations=50, seed=42)

    edge_x = []
    edge_y = []
    for edge in G.edges():
        x0, y0 = pos[edge[0]]
        x1, y1 = pos[edge[1]]
        edge_x.extend([x0, x1, None])
        edge_y.extend([y0, y1, None])

    edge_trace = go.Scatter(
        x=edge_x,
        y=edge_y,
        line=dict(width=1, color="#888"),
        hoverinfo="none",
        mode="lines",
    )

    highlight_edge_x = []
    highlight_edge_y = []
    if highlight_path and len(highlight_path) > 1:
        for i in range(len(highlight_path) - 1):
            if highlight_path[i] in pos and highlight_path[i + 1] in pos:
                x0, y0 = pos[highlight_path[i]]
                x1, y1 = pos[highlight_path[i + 1]]
                highlight_edge_x.extend([x0, x1, None])
                highlight_edge_y.extend([y0, y1, None])

    highlight_edge_trace = go.Scatter(
        x=highlight_edge_x,
        y=highlight_edge_y,
        line=dict(width=4, color="#ff4444"),
        hoverinfo="none",
        mode="lines",
    )

    node_x = []
    node_y = []
    node_text = []
    node_colors = []
    node_sizes = []

    path_set = set(highlight_path) if highlight_path else set()

    for node in G.nodes():
        x, y = pos[node]
        node_x.append(x)
        node_y.append(y)
        node_text.append(node)

        degree = G.degree(node)
        node_sizes.append(max(15, min(40, 10 + degree * 2)))

        if node == center_fighter:
            node_colors.append("#ff4444")
        elif node in path_set:
            node_colors.append("#ff8888")
        else:
            node_colors.append("#1a1a1a")

    node_trace = go.Scatter(
        x=node_x,
        y=node_y,
        mode="markers+text",
        hoverinfo="text",
        text=node_text,
        textposition="top center",
        textfont=dict(size=10),
        marker=dict(
            size=node_sizes,
            color=node_colors,
            line=dict(width=2, color="white"),
        ),
    )

    fig = go.Figure(data=[edge_trace, highlight_edge_trace, node_trace])

    fig.update_layout(
        showlegend=False,
        hovermode="closest",
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, showline=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, showline=False),
        height=700,
        margin=dict(l=20, r=20, t=20, b=20),
    )

    return apply_figure_styling(fig)


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


def get_fighter_nickname_map(df: pd.DataFrame) -> dict[str, str | None]:
    return (
        df.groupby("fighter_name")
        .agg({"nickname": "first"})
        .reset_index()
        .set_index("fighter_name")["nickname"]
        .to_dict()
    )


def get_fighter_stance_map(df: pd.DataFrame) -> dict[str, str | None]:
    return (
        df.groupby("fighter_name")
        .agg({"stance": "first"})
        .reset_index()
        .set_index("fighter_name")["stance"]
        .to_dict()
    )


def get_fighter_style_map(df: pd.DataFrame) -> dict[str, str | None]:
    return (
        df.groupby("fighter_name")
        .agg({"style": "first"})
        .reset_index()
        .set_index("fighter_name")["style"]
        .to_dict()
    )


PLACEHOLDER_IMAGE = (
    "data:image/svg+xml,"
    "%3Csvg xmlns='http://www.w3.org/2000/svg' width='237' height='150' viewBox='0 0 237 150'%3E"
    "%3Crect fill='%23e0ded3' width='237' height='150'/%3E"
    "%3Ccircle cx='118' cy='55' r='30' fill='%23a0a0a0'/%3E"
    "%3Cellipse cx='118' cy='130' rx='45' ry='35' fill='%23a0a0a0'/%3E"
    "%3C/svg%3E"
)


def get_headshot_base64(fighter_uid: str) -> str:
    headshot_path = HEADSHOTS_DIR / f"{fighter_uid}_headshot.png"
    if not headshot_path.exists():
        return PLACEHOLDER_IMAGE
    with open(headshot_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")
    return f"data:image/png;base64,{encoded}"


df = get_main_data()
network_df = get_network_data()
fighter_graph = build_fighter_graph(network_df)

fighter_options = get_fighter_list(df)
fighter_uid_map = get_fighter_uid_map(df)
fighter_nickname_map = get_fighter_nickname_map(df)
fighter_stance_map = get_fighter_stance_map(df)
fighter_style_map = get_fighter_style_map(df)

initial_fighter = df.sample(1)["fighter_name"].item()
if not isinstance(initial_fighter, str):
    raise TypeError()

most_recent_event = df["event_date"].max().strftime("%Y-%m-%d")

assets_path = Path(__file__).parent / "assets"
app = Dash(__name__, assets_folder=str(assets_path))
server = app.server

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
                            "Fighter Profile",
                            value="profile",
                        ),
                        dmc.TabsTab("Fight History", value="history"),
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
    ]
)

fighter_network_content = html.Div(
    [
        dmc.Group(
            [
                dmc.Select(
                    label="Center Fighter",
                    placeholder="Select a fighter to center the graph",
                    id="network-fighter-select",
                    data=fighter_options,
                    searchable=True,
                    clearable=True,
                    style={"width": "250px"},
                ),
                dmc.Select(
                    label="Find Path To",
                    placeholder="Select second fighter",
                    id="network-fighter-target",
                    data=fighter_options,
                    searchable=True,
                    clearable=True,
                    style={"width": "250px"},
                ),
                dmc.NumberInput(
                    label="Connection Depth",
                    id="network-depth",
                    value=2,
                    min=1,
                    max=4,
                    style={"width": "150px"},
                ),
            ],
            align="flex-end",
            gap="md",
            mb="md",
        ),
        html.Div(
            id="network-path-info",
            style={"marginBottom": "1rem"},
        ),
        html.Div(
            dcc.Graph(
                id="fighter-network-graph",
                figure={},
                config={"displayModeBar": False},
            ),
            className="plot-container-wrapper",
        ),
    ]
)

app.layout = dmc.MantineProvider(
    html.Div(
        id="panoctagon-page",
        children=dmc.AppShell(
            [
                dmc.AppShellHeader(
                    dmc.Group(
                        [
                            dmc.Title("panoctagon", c="red", size="h2"),
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
                        dmc.Tabs(
                            [
                                dmc.TabsList(
                                    [
                                        dmc.TabsTab("Fighter Analysis", value="analysis"),
                                        dmc.TabsTab("Fighter Network", value="network"),
                                    ]
                                ),
                                dmc.TabsPanel(
                                    fighter_analysis_content,
                                    value="analysis",
                                    pt="md",
                                ),
                                dmc.TabsPanel(
                                    fighter_network_content,
                                    value="network",
                                    pt="md",
                                ),
                            ],
                            value="analysis",
                            id="top-level-tabs",
                        ),
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

    fights = df_fighter.groupby("fight_uid").agg({"fighter_result": "first"}).reset_index()

    total_fights = len(fights)
    wins = (fights["fighter_result"] == "WIN").sum()
    losses = (fights["fighter_result"] == "LOSS").sum()
    draws = (fights["fighter_result"] == "DRAW").sum()
    no_contests = (fights["fighter_result"] == "NO_CONTEST").sum()

    finish_decisions = ["KO", "TKO", "SUB", "Submission"]
    finishes = (
        df_fighter[df_fighter["decision"].isin(finish_decisions)].groupby("fight_uid").ngroups
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
    [
        Output("fighter-headshot", "src"),
        Output("fighter-nickname", "children"),
        Output("fighter-stance", "children"),
        Output("fighter-style", "children"),
    ],
    [Input("fighter-select", "value")],
)
def update_headshot(fighter: str):
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

    fight_timeline["cumulative_absorbed"] = fight_timeline["opponent_strikes_landed"].cumsum()

    color_map = {
        "WIN": "#7370ff",
        "LOSS": "#ff7e70",
        "DRAW": "gray",
        "NO_CONTEST": "orange",
    }
    marker_colors = [color_map.get(result, "gray") for result in fight_timeline["fighter_result"]]

    result_map = {
        "WIN": "Beat",
        "LOSS": "Defeated by",
        "DRAW": "Draw vs",
        "NO_CONTEST": "No Contest vs",
    }

    hover_text = [
        f"<b>{row['title']}</b> | {row['event_date'].strftime('%Y-%m-%d')}"
        f"<br>{result_map.get(row['fighter_result'])} <b>{row['opponent_name']}</b>"
        f"<br>+{row['opponent_strikes_landed']:,} strikes ({row['cumulative_absorbed']:,} total)"
        for _, row in fight_timeline.iterrows()
    ]

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=fight_timeline["event_date"],
            y=fight_timeline["cumulative_absorbed"],
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

    if df_filtered.empty:
        fig = go.Figure()
        fig.update_layout(height=400)
        return apply_figure_styling(fig)

    df_wins = df_filtered[df_filtered["fighter_result"] == "WIN"]
    df_losses = df_filtered[df_filtered["fighter_result"] == "LOSS"]

    win_methods = df_wins.groupby("fight_uid").agg({"decision": "first"}).reset_index()
    win_counts = win_methods["decision"].value_counts()

    loss_methods = df_losses.groupby("fight_uid").agg({"decision": "first"}).reset_index()
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
        fight_accuracy = fight_accuracy[fight_accuracy["total_strikes_attempted"] > 0]
        fight_accuracy["accuracy"] = (
            fight_accuracy["total_strikes_landed"] / fight_accuracy["total_strikes_attempted"] * 100
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
            barmode="stack",
            yaxis_title="Strikes Landed",
            height=400,
        )

    return apply_figure_styling(fig)


@callback(
    [
        Output("fighter-network-graph", "figure"),
        Output("network-path-info", "children"),
    ],
    [
        Input("network-fighter-select", "value"),
        Input("network-fighter-target", "value"),
        Input("network-depth", "value"),
    ],
)
def update_network_graph(center_fighter: str | None, target_fighter: str | None, depth: int):
    if not center_fighter:
        fig = create_network_figure(nx.Graph())
        return fig, ""

    subgraph = get_subgraph_for_fighter(fighter_graph, center_fighter, depth)

    highlight_path = None
    path_info = ""

    if target_fighter and target_fighter != center_fighter:
        if target_fighter in fighter_graph:
            try:
                path = nx.shortest_path(fighter_graph, center_fighter, target_fighter)
                highlight_path = path
                path_length = len(path) - 1
                path_str = " -> ".join(path)
                path_info = dmc.Alert(
                    [
                        dmc.Text(f"Shortest path ({path_length} fights): ", fw=700, span=True),
                        dmc.Text(path_str, span=True),
                    ],
                    color="blue",
                    variant="light",
                )
                for node in path:
                    if node not in subgraph:
                        subgraph = fighter_graph.subgraph(
                            set(subgraph.nodes()) | set(path)
                        ).copy()
                        break
            except nx.NetworkXNoPath:
                path_info = dmc.Alert(
                    f"No path found between {center_fighter} and {target_fighter}",
                    color="red",
                    variant="light",
                )
        else:
            path_info = dmc.Alert(
                f"{target_fighter} not found in the network",
                color="orange",
                variant="light",
            )

    fig = create_network_figure(subgraph, center_fighter, highlight_path)
    return fig, path_info


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8050)
