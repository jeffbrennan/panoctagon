import dash_mantine_components as dmc
import networkx as nx
import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, callback, dcc, html

from panoctagon.common import get_engine
from panoctagon.dashboard.common import apply_figure_styling, get_fighter_divisions


def build_fighter_graph(
    network_df: pd.DataFrame, fighter_divisions: dict[str, str]
) -> tuple[
    nx.DiGraph,
    dict[str, dict[str, dict[str, list[str]]]],
    dict[str, dict[str, int]],
    dict[tuple[str, str], int],
]:
    G = nx.DiGraph()
    fighter_opponents_by_year: dict[str, dict[str, list[str]]] = {}
    fighter_stats: dict[str, dict[str, int]] = {}
    fighter_matchups: dict[tuple[str, str], int] = {}

    for _, row in network_df.iterrows():
        f1_name = row["fighter1_name"]
        f2_name = row["fighter2_name"]
        f1_result = row["fighter1_result"]
        f2_result = row["fighter2_result"]
        fight_year = row["fight_year"]

        if f1_name not in G:
            G.add_node(f1_name, division=fighter_divisions.get(f1_name, "Unknown"))
            fighter_stats[f1_name] = {"wins": 0, "losses": 0}
        if f2_name not in G:
            G.add_node(f2_name, division=fighter_divisions.get(f2_name, "Unknown"))
            fighter_stats[f2_name] = {"wins": 0, "losses": 0}

        if f1_result == "WIN":
            winner = f1_name
            loser = f2_name
            fighter_stats[f1_name]["wins"] += 1
            fighter_stats[f2_name]["losses"] += 1
        elif f2_result == "WIN":
            winner = f2_name
            loser = f1_name
            fighter_stats[f2_name]["wins"] += 1
            fighter_stats[f1_name]["losses"] += 1
        else:
            continue

        if G.has_edge(loser, winner):
            G[loser][winner]["weight"] += 1
        else:
            G.add_edge(loser, winner, weight=1)

        matchup_key = tuple(sorted([f1_name, f2_name]))
        fighter_matchups[matchup_key] = fighter_matchups.get(matchup_key, 0) + 1

        if f1_name not in fighter_opponents_by_year:
            fighter_opponents_by_year[f1_name] = {}
        if fight_year not in fighter_opponents_by_year[f1_name]:
            fighter_opponents_by_year[f1_name][fight_year] = {"wins": [], "losses": [], "draws": []}

        if f1_result == "WIN":
            fighter_opponents_by_year[f1_name][fight_year]["wins"].append(f2_name)
        elif f2_result == "WIN":
            fighter_opponents_by_year[f1_name][fight_year]["losses"].append(f2_name)
        else:
            fighter_opponents_by_year[f1_name][fight_year]["draws"].append(f2_name)

        if f2_name not in fighter_opponents_by_year:
            fighter_opponents_by_year[f2_name] = {}
        if fight_year not in fighter_opponents_by_year[f2_name]:
            fighter_opponents_by_year[f2_name][fight_year] = {"wins": [], "losses": [], "draws": []}

        if f2_result == "WIN":
            fighter_opponents_by_year[f2_name][fight_year]["wins"].append(f1_name)
        elif f1_result == "WIN":
            fighter_opponents_by_year[f2_name][fight_year]["losses"].append(f1_name)
        else:
            fighter_opponents_by_year[f2_name][fight_year]["draws"].append(f1_name)

    return G, fighter_opponents_by_year, fighter_stats, fighter_matchups


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
    G: nx.DiGraph,
    opponents_by_year: dict[str, dict[str, dict[str, list[str]]]],
    fighter_stats: dict[str, dict[str, int]],
    fighter_matchups: dict[tuple[str, str], int],
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

    if len(G.nodes()) > 300:
        pos = nx.kamada_kawai_layout(G)
    else:
        pos = nx.spring_layout(G.to_undirected(), k=0.5, iterations=100, seed=42)

    edge_traces = []
    for loser, winner in G.edges():
        x0, y0 = pos[loser]
        x1, y1 = pos[winner]

        matchup_key = tuple(sorted([loser, winner]))
        total_fights = fighter_matchups.get(matchup_key, 1)

        edge_trace = go.Scatter(
            x=[x0, x1],
            y=[y0, y1],
            mode="lines",
            line=dict(width=max(0.5, total_fights), color="rgba(33, 33, 33, 0.5)"),
            hoverinfo="none",
            showlegend=False,
        )
        edge_traces.append(edge_trace)

        dx = x1 - x0
        dy = y1 - y0
        length = (dx**2 + dy**2) ** 0.5
        if length > 0:
            arrow_x = x1 - 0.05 * dx / length
            arrow_y = y1 - 0.05 * dy / length

            import math

            angle = math.degrees(math.atan2(dy, dx)) - 90

            arrow_trace = go.Scatter(
                x=[arrow_x],
                y=[arrow_y],
                mode="markers",
                marker=dict(
                    size=10,
                    color="rgba(80, 80, 80, 0.7)",
                    symbol="arrow",
                    angleref="previous",
                    angle=angle,
                ),
                hoverinfo="none",
                showlegend=False,
            )
            edge_traces.append(arrow_trace)

    opponent_strength = {}
    for node in G.nodes():
        beaten_opponents = list(G.predecessors(node))
        total_opponent_wins = sum(
            fighter_stats.get(opp, {}).get("wins", 0) for opp in beaten_opponents
        )
        opponent_strength[node] = total_opponent_wins

    max_opponent_strength = max(opponent_strength.values()) if opponent_strength.values() else 1

    node_x = []
    node_y = []
    node_text = []
    node_sizes = []
    node_colors = []

    for node in G.nodes():
        x, y = pos[node]
        node_x.append(x)
        node_y.append(y)

        wins = fighter_stats.get(node, {}).get("wins", 0)
        losses = fighter_stats.get(node, {}).get("losses", 0)
        total = wins + losses
        win_pct = (wins / total * 100) if total > 0 else 0

        beaten_opponents = list(G.predecessors(node))
        beaten_wins = sum(fighter_stats.get(opp, {}).get("wins", 0) for opp in beaten_opponents)
        beaten_losses = sum(fighter_stats.get(opp, {}).get("losses", 0) for opp in beaten_opponents)

        hover_lines = [f"<b>{node}</b> {wins}W {losses}L ({win_pct:.1f}%)"]
        if beaten_opponents:
            hover_lines.append(f"Defeated opponent record: {beaten_wins}W {beaten_losses}L")
        hover_lines.append("")

        if node in opponents_by_year:
            years_sorted = sorted(opponents_by_year[node].keys(), reverse=True)
            for year in years_sorted:
                year_fights = opponents_by_year[node][year]
                year_lines = [f"<b>{year}</b>"]

                if year_fights["wins"]:
                    wins_text = ", ".join(sorted(year_fights["wins"]))
                    year_lines.append(f"  W: {wins_text}")

                if year_fights["losses"]:
                    losses_text = ", ".join(sorted(year_fights["losses"]))
                    year_lines.append(f"  L: {losses_text}")

                if year_fights["draws"]:
                    draws_text = ", ".join(sorted(year_fights["draws"]))
                    year_lines.append(f"  D: {draws_text}")

                hover_lines.extend(year_lines)

        node_text.append("<br>".join(hover_lines))

        if total == 1:
            node_size = 8
        elif total == 2:
            node_size = 12
        else:
            node_size = max(16, min(35, 12 + wins * 2))

        node_sizes.append(node_size)
        opp_strength_normalized = (
            (opponent_strength[node] / max_opponent_strength * 100)
            if max_opponent_strength > 0
            else 0
        )
        node_colors.append(opp_strength_normalized)

    node_trace = go.Scatter(
        x=node_x,
        y=node_y,
        mode="markers",
        hoverinfo="text",
        text=node_text,
        marker=dict(
            size=node_sizes,
            color=node_colors,
            colorscale=[[0, "#f3776b"], [0.5, "#b4dcd1"], [1, "#049464"]],
            cmin=0,
            cmax=100,
            opacity=1.0,
            line=dict(width=1, color="rgb(33,33,33)"),
            colorbar=dict(
                title="Opposition<br>Strength",
                thickness=15,
                len=0.5,
                x=1.02,
            ),
        ),
        showlegend=False,
    )

    fig = go.Figure(data=[*edge_traces, node_trace])

    fig.update_layout(
        showlegend=False,
        hovermode="closest",
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        height=700,
        margin=dict(l=20, r=80, t=20, b=20),
        plot_bgcolor="rgb(242, 240, 227)",
        paper_bgcolor="rgb(242, 240, 227)",
        font=dict(family="JetBrains Mono, monospace", color="#1a1a1a"),
    )

    return fig


def get_network_data() -> pd.DataFrame:
    return pd.read_sql_query(
        """
        select
            a.fighter1_uid,
            a.fighter2_uid,
            f1.first_name || ' ' || f1.last_name as fighter1_name,
            f2.first_name || ' ' || f2.last_name as fighter2_name,
            a.fighter1_result,
            a.fighter2_result,
            a.fight_division,
            e.event_date,
            strftime(cast(e.event_date as date), '%Y') as fight_year
        from ufc_fights a
        inner join ufc_fighters f1 on a.fighter1_uid = f1.fighter_uid
        inner join ufc_fighters f2 on a.fighter2_uid = f2.fighter_uid
        inner join ufc_events e on a.event_uid = e.event_uid
        where a.fight_division is not null
        """,
        get_engine(),
    )


@callback(
    Output("fighter-network-graph", "figure"),
    [
        Input("top-level-tabs", "value"),
        Input("network-division-dropdown", "value"),
        Input("network-year-slider", "value"),
    ],
)
def update_network_graph(tab: str, division: str, year_range: list[int]):
    if tab != "network":
        return go.Figure()

    min_year, max_year = year_range
    filtered_network_df = network_df[
        (network_df["fight_division"] == division)
        & (network_df["fight_year"].astype(int) >= min_year)
        & (network_df["fight_year"].astype(int) <= max_year)
    ]

    if filtered_network_df.empty:
        fig = go.Figure()
        fig.update_layout(
            annotations=[
                dict(
                    text="No fights in selected division/year range",
                    xref="paper",
                    yref="paper",
                    x=0.5,
                    y=0.5,
                    showarrow=False,
                    font=dict(size=20),
                )
            ],
            plot_bgcolor="rgb(242, 240, 227)",
            paper_bgcolor="rgb(242, 240, 227)",
        )
        return fig

    filtered_graph, filtered_opponents_by_year, filtered_stats, filtered_matchups = (
        build_fighter_graph(filtered_network_df, fighter_divisions)
    )

    fig = create_network_figure(
        filtered_graph, filtered_opponents_by_year, filtered_stats, filtered_matchups
    )
    return fig


network_df = get_network_data()
initial_network_df = network_df[network_df["fight_division"] == "HEAVYWEIGHT"]
fighter_divisions = get_fighter_divisions()
fighter_graph, fighter_opponents_by_year, fighter_stats, fighter_matchups = build_fighter_graph(
    initial_network_df, fighter_divisions
)
fighter_network_content = html.Div(
    [
        html.Div(
            [
                html.Div(
                    [
                        dmc.Text("Division", size="sm", fw=500, mb="xs", c="#1a1a1a"),
                        dmc.Select(
                            id="network-division-dropdown",
                            data=[
                                {"value": "HEAVYWEIGHT", "label": "Heavyweight"},
                                {"value": "LIGHT_HEAVYWEIGHT", "label": "Light Heavyweight"},
                                {"value": "MIDDLEWEIGHT", "label": "Middleweight"},
                                {"value": "WELTERWEIGHT", "label": "Welterweight"},
                                {"value": "LIGHTWEIGHT", "label": "Lightweight"},
                                {"value": "FEATHERWEIGHT", "label": "Featherweight"},
                                {"value": "BANTAMWEIGHT", "label": "Bantamweight"},
                                {"value": "FLYWEIGHT", "label": "Flyweight"},
                                {"value": "WOMENS_FEATHERWEIGHT", "label": "Women's Featherweight"},
                                {"value": "WOMENS_BANTAMWEIGHT", "label": "Women's Bantamweight"},
                                {"value": "WOMENS_FLYWEIGHT", "label": "Women's Flyweight"},
                                {"value": "WOMENS_STRAWWEIGHT", "label": "Women's Strawweight"},
                            ],
                            value="HEAVYWEIGHT",
                            searchable=True,
                            clearable=False,
                        ),
                    ],
                    style={"width": "25%", "paddingRight": "1rem"},
                ),
                html.Div(
                    [
                        dmc.Text("Year Range", size="sm", fw=500, mb="xs", c="#1a1a1a"),
                        dcc.RangeSlider(
                            id="network-year-slider",
                            min=1997,
                            max=2026,
                            value=[2021, 2026],
                            marks={year: str(year) for year in range(1997, 2027, 3)},
                            step=1,
                            tooltip={"placement": "bottom", "always_visible": True},
                        ),
                    ],
                    style={"width": "50%", "paddingLeft": "1rem"},
                ),
            ],
            style={
                "display": "flex",
                "marginBottom": "2rem",
                "paddingLeft": "1rem",
                "paddingRight": "1rem",
            },
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
