import base64
from pathlib import Path
from typing import Any

import dash_mantine_components as dmc
import networkx as nx
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import ALL, Dash, Input, Output, State, callback, ctx, dash_table, dcc, html

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


def get_roster_stats() -> pd.DataFrame:
    return pd.read_sql_query(
        """
        with
            fighter_details as (
                select
                    fighter_uid,
                    first_name || ' ' || last_name as fighter_name,
                    dob
                from ufc_fighters
            ),
            fight_results_long as (
                select
                    fight_uid,
                    fighter1_uid as fighter_uid,
                    fighter1_result as fighter_result
                from ufc_fights
                union
                select
                    fight_uid,
                    fighter2_uid as fighter_uid,
                    fighter2_result as fighter_result
                from ufc_fights
            ),
            fighter_stats as (
                select
                    fs.fighter_uid,
                    fd.fighter_name,
                    fs.fight_uid,
                    fr.fighter_result,
                    sum(fs.total_strikes_landed) as strikes_landed,
                    sum(fs.total_strikes_attempted) as strikes_attempted,
                    sum(fs.sig_strikes_head_landed) as head_strikes,
                    sum(fs.sig_strikes_body_landed) as body_strikes,
                    sum(fs.sig_strikes_leg_landed) as leg_strikes
                from ufc_fight_stats fs
                inner join fighter_details fd on fs.fighter_uid = fd.fighter_uid
                inner join fight_results_long fr
                    on fs.fight_uid = fr.fight_uid
                    and fs.fighter_uid = fr.fighter_uid
                group by fs.fighter_uid, fd.fighter_name, fs.fight_uid, fr.fighter_result
            ),
            opponent_stats as (
                select
                    fs.fight_uid,
                    fs.fighter_uid as opponent_uid,
                    sum(fs.total_strikes_landed) as opponent_strikes_landed
                from ufc_fight_stats fs
                group by fs.fight_uid, fs.fighter_uid
            ),
            combined as (
                select
                    fs.fighter_uid,
                    fs.fighter_name,
                    fs.fight_uid,
                    fs.fighter_result,
                    fs.strikes_landed,
                    fs.strikes_attempted,
                    fs.head_strikes,
                    fs.body_strikes,
                    fs.leg_strikes,
                    os.opponent_strikes_landed
                from fighter_stats fs
                inner join opponent_stats os
                    on fs.fight_uid = os.fight_uid
                    and fs.fighter_uid != os.opponent_uid
            )
        select
            fighter_uid,
            fighter_name,
            count(distinct fight_uid) as total_fights,
            sum(case when fighter_result = 'WIN' then 1 else 0 end) as wins,
            avg(strikes_landed) as avg_strikes_landed,
            avg(opponent_strikes_landed) as avg_strikes_absorbed,
            sum(head_strikes) as total_head_strikes,
            sum(body_strikes) as total_body_strikes,
            sum(leg_strikes) as total_leg_strikes,
            sum(head_strikes + body_strikes + leg_strikes) as total_sig_strikes
        from combined
        group by fighter_uid, fighter_name
        having count(distinct fight_uid) >= 3
        """,
        get_engine(),
    )


def get_matchup_data() -> pd.DataFrame:
    return pd.read_sql_query(
        """
        with
            fighter_info as (
                select
                    fighter_uid,
                    first_name || ' ' || last_name as fighter_name,
                    dob,
                    reach_inches
                from ufc_fighters
            ),
            fighter_fight_counts as (
                select
                    fighter_uid,
                    fight_uid,
                    row_number() over (partition by fighter_uid order by event_date) as fight_num
                from (
                    select f.fighter1_uid as fighter_uid, f.fight_uid, e.event_date
                    from ufc_fights f
                    inner join ufc_events e on f.event_uid = e.event_uid
                    union all
                    select f.fighter2_uid as fighter_uid, f.fight_uid, e.event_date
                    from ufc_fights f
                    inner join ufc_events e on f.event_uid = e.event_uid
                )
            )
        select
            f.fight_uid,
            e.event_date,
            f.fighter1_uid,
            f1.fighter_name as fighter1_name,
            f1.dob as fighter1_dob,
            f1.reach_inches as fighter1_reach,
            fc1.fight_num as fighter1_fight_num,
            f.fighter1_result,
            f.fighter2_uid,
            f2.fighter_name as fighter2_name,
            f2.dob as fighter2_dob,
            f2.reach_inches as fighter2_reach,
            fc2.fight_num as fighter2_fight_num,
            f.fighter2_result
        from ufc_fights f
        inner join ufc_events e on f.event_uid = e.event_uid
        inner join fighter_info f1 on f.fighter1_uid = f1.fighter_uid
        inner join fighter_info f2 on f.fighter2_uid = f2.fighter_uid
        inner join fighter_fight_counts fc1
            on f.fighter1_uid = fc1.fighter_uid and f.fight_uid = fc1.fight_uid
        inner join fighter_fight_counts fc2
            on f.fighter2_uid = fc2.fighter_uid and f.fight_uid = fc2.fight_uid
        where f.fighter1_result in ('WIN', 'LOSS')
        """,
        get_engine(),
    )


def get_upcoming_fights() -> pd.DataFrame:
    return pd.read_sql_query(
        """
        with fighter_info as (
            select
                fighter_uid,
                first_name || ' ' || last_name as fighter_name,
                dob,
                reach_inches,
                height_inches,
                stance
            from ufc_fighters
        ),
        fighter_records as (
            select
                fighter_uid,
                count(*) as total_fights,
                sum(case when result = 'WIN' then 1 else 0 end) as wins,
                sum(case when result = 'LOSS' then 1 else 0 end) as losses,
                sum(case when result = 'DRAW' then 1 else 0 end) as draws
            from (
                select fighter1_uid as fighter_uid, fighter1_result as result
                from ufc_fights where fighter1_result is not null
                union all
                select fighter2_uid as fighter_uid, fighter2_result as result
                from ufc_fights where fighter2_result is not null
            )
            group by fighter_uid
        )
        select
            f.fight_uid,
            f.event_uid,
            e.title as event_title,
            e.event_date,
            e.event_location,
            f.fight_division,
            f.fight_type,
            f.fighter1_uid,
            f1.fighter_name as fighter1_name,
            f1.dob as fighter1_dob,
            f1.reach_inches as fighter1_reach,
            f1.height_inches as fighter1_height,
            f1.stance as fighter1_stance,
            coalesce(fr1.total_fights, 0) as fighter1_total_fights,
            coalesce(fr1.wins, 0) as fighter1_wins,
            coalesce(fr1.losses, 0) as fighter1_losses,
            coalesce(fr1.draws, 0) as fighter1_draws,
            f.fighter2_uid,
            f2.fighter_name as fighter2_name,
            f2.dob as fighter2_dob,
            f2.reach_inches as fighter2_reach,
            f2.height_inches as fighter2_height,
            f2.stance as fighter2_stance,
            coalesce(fr2.total_fights, 0) as fighter2_total_fights,
            coalesce(fr2.wins, 0) as fighter2_wins,
            coalesce(fr2.losses, 0) as fighter2_losses,
            coalesce(fr2.draws, 0) as fighter2_draws
        from ufc_fights f
        inner join ufc_events e on f.event_uid = e.event_uid
        inner join fighter_info f1 on f.fighter1_uid = f1.fighter_uid
        inner join fighter_info f2 on f.fighter2_uid = f2.fighter_uid
        left join fighter_records fr1 on f.fighter1_uid = fr1.fighter_uid
        left join fighter_records fr2 on f.fighter2_uid = fr2.fighter_uid
        where f.fighter1_result is null
        order by e.event_date asc
        """,
        get_engine(),
    )


def get_fighter_recent_form(fighter_uid: str, n_fights: int = 5) -> pd.DataFrame:
    return pd.read_sql_query(
        f"""
        with fighter_fights as (
            select
                f.fight_uid,
                e.event_date,
                f.fighter1_uid as fighter_uid,
                f.fighter2_uid as opponent_uid,
                f.fighter1_result as result,
                f.decision,
                f.decision_round
            from ufc_fights f
            inner join ufc_events e on f.event_uid = e.event_uid
            where f.fighter1_uid = '{fighter_uid}'
              and f.fighter1_result is not null
            union all
            select
                f.fight_uid,
                e.event_date,
                f.fighter2_uid as fighter_uid,
                f.fighter1_uid as opponent_uid,
                f.fighter2_result as result,
                f.decision,
                f.decision_round
            from ufc_fights f
            inner join ufc_events e on f.event_uid = e.event_uid
            where f.fighter2_uid = '{fighter_uid}'
              and f.fighter2_result is not null
        ),
        fighter_stats_agg as (
            select
                fs.fight_uid,
                fs.fighter_uid,
                sum(fs.total_strikes_landed) as strikes_landed,
                sum(fs.total_strikes_attempted) as strikes_attempted,
                sum(fs.takedowns_landed) as takedowns_landed,
                sum(fs.takedowns_attempted) as takedowns_attempted,
                sum(fs.sig_strikes_landed) as sig_strikes_landed,
                sum(fs.knockdowns) as knockdowns
            from ufc_fight_stats fs
            group by fs.fight_uid, fs.fighter_uid
        )
        select
            ff.fight_uid,
            ff.event_date,
            ff.result,
            ff.decision,
            ff.decision_round,
            opp.first_name || ' ' || opp.last_name as opponent_name,
            fsa.strikes_landed,
            fsa.strikes_attempted,
            fsa.takedowns_landed,
            fsa.takedowns_attempted,
            fsa.sig_strikes_landed,
            fsa.knockdowns
        from fighter_fights ff
        inner join ufc_fighters opp on ff.opponent_uid = opp.fighter_uid
        left join fighter_stats_agg fsa on ff.fight_uid = fsa.fight_uid
            and ff.fighter_uid = fsa.fighter_uid
        order by ff.event_date desc
        limit {n_fights}
        """,
        get_engine(),
    )


def get_fighter_divisions() -> dict[str, str]:
    df = pd.read_sql_query(
        """
        with fighter_division_counts as (
            select
                fighter_uid,
                fight_division,
                count(*) as fight_count
            from (
                select fighter1_uid as fighter_uid, fight_division from ufc_fights
                union all
                select fighter2_uid as fighter_uid, fight_division from ufc_fights
            )
            where fight_division is not null
            group by fighter_uid, fight_division
        ),
        fighter_primary_division as (
            select
                fighter_uid,
                fight_division,
                row_number() over (partition by fighter_uid order by fight_count desc) as rn
            from fighter_division_counts
        )
        select
            f.first_name || ' ' || f.last_name as fighter_name,
            fpd.fight_division
        from fighter_primary_division fpd
        inner join ufc_fighters f on fpd.fighter_uid = f.fighter_uid
        where fpd.rn = 1
        """,
        get_engine(),
    )
    return dict(zip(df["fighter_name"], df["fight_division"]))


DIVISION_COLORS = {
    "Strawweight": "#FF69B4",
    "Women's Strawweight": "#FF1493",
    "Flyweight": "#9370DB",
    "Women's Flyweight": "#8A2BE2",
    "Bantamweight": "#4169E1",
    "Women's Bantamweight": "#0000CD",
    "Featherweight": "#20B2AA",
    "Women's Featherweight": "#008B8B",
    "Lightweight": "#32CD32",
    "Welterweight": "#FFD700",
    "Middleweight": "#FFA500",
    "Light Heavyweight": "#FF6347",
    "Heavyweight": "#DC143C",
    "Super Heavyweight": "#8B0000",
    "Catch Weight": "#808080",
    "Open Weight": "#A9A9A9",
}


def build_fighter_graph(
    network_df: pd.DataFrame, fighter_divisions: dict[str, str]
) -> nx.Graph:
    G = nx.Graph()
    for _, row in network_df.iterrows():
        f1_name = row["fighter1_name"]
        f2_name = row["fighter2_name"]
        if f1_name not in G:
            G.add_node(f1_name, division=fighter_divisions.get(f1_name, "Unknown"))
        if f2_name not in G:
            G.add_node(f2_name, division=fighter_divisions.get(f2_name, "Unknown"))
        G.add_edge(f1_name, f2_name, weight=row["fight_count"])
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
    G: nx.Graph,
    search_fighter: str | None = None,
    highlight_path: list[str] | None = None,
    show_labels: bool = False,
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
        line=dict(width=0.5, color="#cccccc"),
        hoverinfo="none",
        mode="lines",
        showlegend=False,
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
        showlegend=False,
    )

    path_set = set(highlight_path) if highlight_path else set()

    division_nodes: dict[str, dict[str, list]] = {}
    for node in G.nodes():
        division = G.nodes[node].get("division", "Unknown")
        if division not in division_nodes:
            division_nodes[division] = {"x": [], "y": [], "text": [], "sizes": []}

        x, y = pos[node]
        degree = G.degree(node)
        size = max(8, min(30, 6 + degree))

        if node == search_fighter or node in path_set:
            size = max(20, size + 10)

        division_nodes[division]["x"].append(x)
        division_nodes[division]["y"].append(y)
        division_nodes[division]["text"].append(node)
        division_nodes[division]["sizes"].append(size)

    fig = go.Figure()
    fig.add_trace(edge_trace)
    fig.add_trace(highlight_edge_trace)

    division_order = [
        "Strawweight",
        "Women's Strawweight",
        "Flyweight",
        "Women's Flyweight",
        "Bantamweight",
        "Women's Bantamweight",
        "Featherweight",
        "Women's Featherweight",
        "Lightweight",
        "Welterweight",
        "Middleweight",
        "Light Heavyweight",
        "Heavyweight",
        "Super Heavyweight",
        "Catch Weight",
        "Open Weight",
        "Unknown",
    ]

    for division in division_order:
        if division not in division_nodes:
            continue
        data = division_nodes[division]
        color = DIVISION_COLORS.get(division, "#888888")

        show_text = show_labels or (search_fighter and search_fighter in data["text"])
        text_display = data["text"] if show_text else [""] * len(data["text"])

        fig.add_trace(
            go.Scatter(
                x=data["x"],
                y=data["y"],
                mode="markers+text" if show_labels else "markers",
                hoverinfo="text",
                hovertext=data["text"],
                text=text_display,
                textposition="top center",
                textfont=dict(size=8),
                marker=dict(
                    size=data["sizes"],
                    color=color,
                    line=dict(width=1, color="white"),
                ),
                name=division,
                legendgroup=division,
            )
        )

    if search_fighter and search_fighter in pos:
        x, y = pos[search_fighter]
        fig.add_annotation(
            x=x,
            y=y,
            text=search_fighter,
            showarrow=True,
            arrowhead=2,
            arrowsize=1,
            arrowwidth=2,
            arrowcolor="#ff4444",
            font=dict(size=12, color="#ff4444"),
            bgcolor="white",
            bordercolor="#ff4444",
            borderwidth=1,
        )

    fig.update_layout(
        showlegend=True,
        legend=dict(
            orientation="v",
            yanchor="top",
            y=1,
            xanchor="left",
            x=1.02,
            font=dict(size=10),
        ),
        hovermode="closest",
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, showline=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, showline=False),
        height=700,
        margin=dict(l=20, r=150, t=20, b=20),
    )

    return apply_figure_styling(fig)


def create_fighter_clustering_figure(
    roster_df: pd.DataFrame, fighter_divisions: dict[str, str]
) -> go.Figure:
    if roster_df.empty:
        fig = go.Figure()
        fig.update_layout(height=600)
        return apply_figure_styling(fig)

    roster_df = roster_df.copy()
    roster_df["division"] = roster_df["fighter_name"].map(fighter_divisions).fillna("Unknown")
    roster_df["win_pct"] = roster_df["wins"] / roster_df["total_fights"] * 100

    fig = go.Figure()

    for division in DIVISION_COLORS:
        div_data = roster_df[roster_df["division"] == division]
        if div_data.empty:
            continue

        hover_text = [
            f"<b>{row['fighter_name']}</b><br>"
            f"Fights: {row['total_fights']}<br>"
            f"Win%: {row['win_pct']:.1f}%<br>"
            f"Avg Landed: {row['avg_strikes_landed']:.1f}<br>"
            f"Avg Absorbed: {row['avg_strikes_absorbed']:.1f}"
            for _, row in div_data.iterrows()
        ]

        fig.add_trace(
            go.Scatter(
                x=div_data["avg_strikes_landed"],
                y=div_data["avg_strikes_absorbed"],
                mode="markers",
                marker=dict(
                    size=div_data["total_fights"].clip(upper=30) + 5,
                    color=DIVISION_COLORS[division],
                    line=dict(width=1, color="white"),
                    opacity=0.7,
                ),
                name=division,
                hovertext=hover_text,
                hoverinfo="text",
            )
        )

    max_val = max(
        roster_df["avg_strikes_landed"].max(),
        roster_df["avg_strikes_absorbed"].max(),
    )
    fig.add_shape(
        type="line",
        x0=0,
        y0=0,
        x1=max_val,
        y1=max_val,
        line=dict(color="gray", width=1, dash="dash"),
    )

    fig.add_annotation(x=max_val * 0.85, y=max_val * 0.15, text="Precise Strikers", showarrow=False)
    fig.add_annotation(x=max_val * 0.85, y=max_val * 0.85, text="High Volume", showarrow=False)
    fig.add_annotation(x=max_val * 0.15, y=max_val * 0.85, text="Defensive/Grapplers", showarrow=False)
    fig.add_annotation(x=max_val * 0.15, y=max_val * 0.15, text="Low Output", showarrow=False)

    fig.update_layout(
        xaxis_title="Avg Strikes Landed Per Fight",
        yaxis_title="Avg Strikes Absorbed Per Fight",
        height=600,
        legend=dict(
            orientation="v",
            yanchor="top",
            y=1,
            xanchor="left",
            x=1.02,
            font=dict(size=9),
        ),
    )

    return apply_figure_styling(fig)


def create_striking_target_winrate_figure(roster_df: pd.DataFrame) -> go.Figure:
    if roster_df.empty:
        fig = go.Figure()
        fig.update_layout(height=500)
        return apply_figure_styling(fig)

    roster_df = roster_df.copy()
    roster_df = roster_df[roster_df["total_sig_strikes"] > 0]
    roster_df["head_pct"] = roster_df["total_head_strikes"] / roster_df["total_sig_strikes"] * 100
    roster_df["body_pct"] = roster_df["total_body_strikes"] / roster_df["total_sig_strikes"] * 100
    roster_df["leg_pct"] = roster_df["total_leg_strikes"] / roster_df["total_sig_strikes"] * 100
    roster_df["win_pct"] = roster_df["wins"] / roster_df["total_fights"] * 100

    bins = [0, 40, 50, 60, 70, 80, 100]
    labels = ["0-40%", "40-50%", "50-60%", "60-70%", "70-80%", "80-100%"]

    target_data = []
    for target, col in [("Head", "head_pct"), ("Body", "body_pct"), ("Leg", "leg_pct")]:
        roster_df["bin"] = pd.cut(roster_df[col], bins=bins, labels=labels, include_lowest=True)
        for label in labels:
            bin_data = roster_df[roster_df["bin"] == label]
            if len(bin_data) >= 5:
                target_data.append(
                    {
                        "target": target,
                        "bin": label,
                        "avg_win_pct": bin_data["win_pct"].mean(),
                        "count": len(bin_data),
                    }
                )

    if not target_data:
        fig = go.Figure()
        fig.update_layout(height=500)
        return apply_figure_styling(fig)

    target_df = pd.DataFrame(target_data)

    fig = go.Figure()
    colors = {"Head": "#e63946", "Body": "#457b9d", "Leg": "#2a9d8f"}

    for target in ["Head", "Body", "Leg"]:
        t_data = target_df[target_df["target"] == target]
        if t_data.empty:
            continue

        hover_text = [
            f"<b>{target} Strikes: {row['bin']}</b><br>"
            f"Avg Win%: {row['avg_win_pct']:.1f}%<br>"
            f"Fighters: {row['count']}"
            for _, row in t_data.iterrows()
        ]

        fig.add_trace(
            go.Bar(
                x=t_data["bin"],
                y=t_data["avg_win_pct"],
                name=target,
                marker_color=colors[target],
                hovertext=hover_text,
                hoverinfo="text",
            )
        )

    fig.update_layout(
        xaxis_title="% of Sig Strikes to Target",
        yaxis_title="Average Win %",
        barmode="group",
        height=500,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
    )

    return apply_figure_styling(fig)


def create_matchup_discrepancy_figure(matchup_df: pd.DataFrame) -> go.Figure:
    if matchup_df.empty:
        fig = go.Figure()
        fig.update_layout(height=500)
        return apply_figure_styling(fig)

    matchup_df = matchup_df.copy()
    matchup_df["event_date"] = pd.to_datetime(matchup_df["event_date"])
    matchup_df["fighter1_dob"] = pd.to_datetime(matchup_df["fighter1_dob"])
    matchup_df["fighter2_dob"] = pd.to_datetime(matchup_df["fighter2_dob"])

    matchup_df["fighter1_age"] = (
        matchup_df["event_date"] - matchup_df["fighter1_dob"]
    ).dt.days / 365.25
    matchup_df["fighter2_age"] = (
        matchup_df["event_date"] - matchup_df["fighter2_dob"]
    ).dt.days / 365.25

    results = []
    for _, row in matchup_df.iterrows():
        if pd.isna(row["fighter1_age"]) or pd.isna(row["fighter2_age"]):
            continue

        age_diff = row["fighter1_age"] - row["fighter2_age"]
        reach_diff = (row["fighter1_reach"] or 0) - (row["fighter2_reach"] or 0)
        exp_diff = row["fighter1_fight_num"] - row["fighter2_fight_num"]

        f1_won = row["fighter1_result"] == "WIN"
        results.append(
            {"age_diff": age_diff, "reach_diff": reach_diff, "exp_diff": exp_diff, "won": f1_won}
        )

        f2_won = row["fighter2_result"] == "WIN"
        results.append(
            {"age_diff": -age_diff, "reach_diff": -reach_diff, "exp_diff": -exp_diff, "won": f2_won}
        )

    if not results:
        fig = go.Figure()
        fig.update_layout(height=500)
        return apply_figure_styling(fig)

    results_df = pd.DataFrame(results)

    fig = go.Figure()

    age_bins = [-20, -10, -5, -2, 0, 2, 5, 10, 20]
    age_labels = ["-20 to -10", "-10 to -5", "-5 to -2", "-2 to 0", "0 to 2", "2 to 5", "5 to 10", "10 to 20"]
    results_df["age_bin"] = pd.cut(results_df["age_diff"], bins=age_bins, labels=age_labels)
    age_win_rates = results_df.groupby("age_bin", observed=True).agg(
        win_rate=("won", "mean"), count=("won", "count")
    )
    age_win_rates = age_win_rates[age_win_rates["count"] >= 20]

    reach_bins = [-15, -6, -3, -1, 1, 3, 6, 15]
    reach_labels = ["-6+ in", "-3 to -6", "-1 to -3", "Even", "+1 to +3", "+3 to +6", "+6+ in"]
    results_df["reach_bin"] = pd.cut(results_df["reach_diff"], bins=reach_bins, labels=reach_labels)
    reach_win_rates = results_df.groupby("reach_bin", observed=True).agg(
        win_rate=("won", "mean"), count=("won", "count")
    )
    reach_win_rates = reach_win_rates[reach_win_rates["count"] >= 20]

    exp_bins = [-50, -10, -5, -2, 0, 2, 5, 10, 50]
    exp_labels = ["-10+ fights", "-5 to -10", "-2 to -5", "-2 to 0", "0 to 2", "2 to 5", "5 to 10", "10+ fights"]
    results_df["exp_bin"] = pd.cut(results_df["exp_diff"], bins=exp_bins, labels=exp_labels)
    exp_win_rates = results_df.groupby("exp_bin", observed=True).agg(
        win_rate=("won", "mean"), count=("won", "count")
    )
    exp_win_rates = exp_win_rates[exp_win_rates["count"] >= 20]

    fig.add_trace(
        go.Scatter(
            x=list(age_win_rates.index),
            y=age_win_rates["win_rate"] * 100,
            mode="lines+markers",
            name="Age Advantage",
            line=dict(color="#e63946", width=2),
            marker=dict(size=10),
            hovertemplate="Age diff: %{x}<br>Win rate: %{y:.1f}%<br>Fights: %{customdata}<extra></extra>",
            customdata=age_win_rates["count"],
        )
    )

    fig.add_trace(
        go.Scatter(
            x=list(reach_win_rates.index),
            y=reach_win_rates["win_rate"] * 100,
            mode="lines+markers",
            name="Reach Advantage",
            line=dict(color="#457b9d", width=2),
            marker=dict(size=10),
            hovertemplate="Reach diff: %{x}<br>Win rate: %{y:.1f}%<br>Fights: %{customdata}<extra></extra>",
            customdata=reach_win_rates["count"],
            visible="legendonly",
        )
    )

    fig.add_trace(
        go.Scatter(
            x=list(exp_win_rates.index),
            y=exp_win_rates["win_rate"] * 100,
            mode="lines+markers",
            name="Experience Advantage",
            line=dict(color="#2a9d8f", width=2),
            marker=dict(size=10),
            hovertemplate="Exp diff: %{x}<br>Win rate: %{y:.1f}%<br>Fights: %{customdata}<extra></extra>",
            customdata=exp_win_rates["count"],
            visible="legendonly",
        )
    )

    fig.add_hline(y=50, line_dash="dash", line_color="gray", opacity=0.5)

    fig.update_layout(
        xaxis_title="Advantage (negative = disadvantage)",
        yaxis_title="Win %",
        height=500,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
        yaxis=dict(range=[30, 70]),
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


try:
    df = get_main_data()
    network_df = get_network_data()
    fighter_divisions = get_fighter_divisions()
    fighter_graph = build_fighter_graph(network_df, fighter_divisions)
    roster_df = get_roster_stats()
    matchup_df = get_matchup_data()
    fighter_options = get_fighter_list(df)
except Exception:
    df = pd.DataFrame()
    network_df = pd.DataFrame()
    fighter_divisions = {}
    fighter_graph = nx.Graph()
    roster_df = pd.DataFrame()
    matchup_df = pd.DataFrame()
    fighter_options = []

if fighter_options:
    fighter_uid_map = get_fighter_uid_map(df)
    fighter_nickname_map = get_fighter_nickname_map(df)
    fighter_stance_map = get_fighter_stance_map(df)
    fighter_style_map = get_fighter_style_map(df)
    initial_fighter = df.sample(1)["fighter_name"].item()
    if not isinstance(initial_fighter, str):
        raise TypeError()
    most_recent_event = df["event_date"].max().strftime("%Y-%m-%d")
else:
    fighter_uid_map = {}
    fighter_nickname_map = {}
    fighter_stance_map = {}
    fighter_style_map = {}
    initial_fighter = ""
    most_recent_event = "No data"

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
                    label="Search Fighter",
                    placeholder="Search for a fighter",
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
                dmc.Switch(
                    label="Show Labels",
                    id="network-show-labels",
                    checked=False,
                    style={"marginTop": "24px"},
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

roster_analysis_content = html.Div(
    [
        html.Div(
            [
                html.Div(
                    "Fighter Type Clustering",
                    className="plot-title",
                ),
                dmc.Text(
                    "Fighters grouped by striking output vs absorption. "
                    "Size indicates number of fights. Fighters with 3+ fights shown.",
                    size="sm",
                    c="gray",
                    mb="sm",
                ),
                html.Div(
                    dcc.Graph(
                        id="fighter-clustering",
                        figure=create_fighter_clustering_figure(roster_df, fighter_divisions),
                        config={"displayModeBar": False},
                    ),
                    className="plot-container-wrapper",
                ),
            ],
            style={"marginBottom": "2rem"},
        ),
        html.Div(
            [
                html.Div(
                    "Striking Target vs Win Rate",
                    className="plot-title",
                ),
                dmc.Text(
                    "How does targeting different areas correlate with winning? "
                    "Grouped by % of significant strikes to each target.",
                    size="sm",
                    c="gray",
                    mb="sm",
                ),
                html.Div(
                    dcc.Graph(
                        id="striking-target-winrate",
                        figure=create_striking_target_winrate_figure(roster_df),
                        config={"displayModeBar": False},
                    ),
                    className="plot-container-wrapper",
                ),
            ],
            style={"marginBottom": "2rem"},
        ),
        html.Div(
            [
                html.Div(
                    "Matchup Discrepancy Analysis",
                    className="plot-title",
                ),
                dmc.Text(
                    "Win rate based on age, reach, and experience advantages. "
                    "Click legend to toggle metrics. 50% line = no advantage.",
                    size="sm",
                    c="gray",
                    mb="sm",
                ),
                html.Div(
                    dcc.Graph(
                        id="matchup-discrepancy",
                        figure=create_matchup_discrepancy_figure(matchup_df),
                        config={"displayModeBar": False},
                    ),
                    className="plot-container-wrapper",
                ),
            ],
        ),
    ]
)

def create_matchup_card(
    fight: dict,
    fighter_num: int,
    opponent_num: int,
) -> dmc.Card:
    fighter_name = fight[f"fighter{fighter_num}_name"]
    fighter_uid = fight[f"fighter{fighter_num}_uid"]
    fighter_record = f"{fight[f'fighter{fighter_num}_wins']}-{fight[f'fighter{fighter_num}_losses']}-{fight[f'fighter{fighter_num}_draws']}"
    fighter_reach = fight[f"fighter{fighter_num}_reach"]
    fighter_height = fight[f"fighter{fighter_num}_height"]
    fighter_stance = fight[f"fighter{fighter_num}_stance"]
    fighter_dob = fight[f"fighter{fighter_num}_dob"]

    opponent_reach = fight[f"fighter{opponent_num}_reach"]
    opponent_height = fight[f"fighter{opponent_num}_height"]

    reach_diff = None
    if fighter_reach and opponent_reach:
        reach_diff = fighter_reach - opponent_reach

    height_diff = None
    if fighter_height and opponent_height:
        height_diff = fighter_height - opponent_height

    def format_diff(diff: int | None, unit: str = "") -> str:
        if diff is None:
            return "-"
        sign = "+" if diff > 0 else ""
        return f"{sign}{diff}{unit}"

    headshot_src = get_headshot_base64(fighter_uid)

    return dmc.Card(
        [
            dmc.Group(
                [
                    html.Img(
                        src=headshot_src,
                        style={
                            "width": "100px",
                            "height": "63px",
                            "objectFit": "cover",
                            "borderRadius": "4px",
                        },
                    ),
                    html.Div(
                        [
                            dmc.Text(fighter_name, fw=700, size="lg"),
                            dmc.Text(fighter_record, size="sm", c="gray"),
                        ]
                    ),
                ],
                gap="md",
            ),
            dmc.Divider(my="sm"),
            dmc.SimpleGrid(
                [
                    html.Div(
                        [
                            dmc.Text("Reach", size="xs", c="gray"),
                            dmc.Text(
                                f"{fighter_reach or '-'}\"",
                                size="sm",
                            ),
                            dmc.Text(
                                format_diff(reach_diff, "\""),
                                size="xs",
                                c="teal" if reach_diff and reach_diff > 0 else "salmon" if reach_diff and reach_diff < 0 else "gray",
                            ),
                        ]
                    ),
                    html.Div(
                        [
                            dmc.Text("Height", size="xs", c="gray"),
                            dmc.Text(
                                f"{fighter_height or '-'}\"",
                                size="sm",
                            ),
                            dmc.Text(
                                format_diff(height_diff, "\""),
                                size="xs",
                                c="teal" if height_diff and height_diff > 0 else "salmon" if height_diff and height_diff < 0 else "gray",
                            ),
                        ]
                    ),
                    html.Div(
                        [
                            dmc.Text("Stance", size="xs", c="gray"),
                            dmc.Text(fighter_stance or "-", size="sm"),
                        ]
                    ),
                ],
                cols=3,
            ),
        ],
        shadow="sm",
        withBorder=True,
        p="md",
        style={"minWidth": "280px"},
    )


def create_matchup_row(fight: dict) -> html.Div:
    fighter1_card = create_matchup_card(fight, 1, 2)
    fighter2_card = create_matchup_card(fight, 2, 1)

    return html.Div(
        [
            dmc.Group(
                [
                    fighter1_card,
                    html.Div(
                        [
                            dmc.Text("VS", fw=700, size="xl", c="gray"),
                        ],
                        style={"textAlign": "center", "minWidth": "60px"},
                    ),
                    fighter2_card,
                ],
                align="stretch",
                justify="center",
                gap="lg",
            ),
            dmc.Group(
                [
                    dmc.Button(
                        f"View {fight['fighter1_name'].split()[-1]}",
                        id={"type": "view-fighter-btn", "index": fight["fighter1_name"]},
                        variant="light",
                        size="xs",
                    ),
                    dmc.Button(
                        f"View {fight['fighter2_name'].split()[-1]}",
                        id={"type": "view-fighter-btn", "index": fight["fighter2_name"]},
                        variant="light",
                        size="xs",
                    ),
                ],
                justify="center",
                mt="sm",
            ),
        ],
        style={"marginBottom": "1.5rem"},
    )


def create_upcoming_fights_content() -> html.Div:
    try:
        upcoming_df = get_upcoming_fights()
    except Exception:
        upcoming_df = pd.DataFrame()

    if upcoming_df.empty:
        return html.Div(
            [
                dmc.Alert(
                    "No upcoming fights found. Upcoming fights will appear here after scraping events with unfinished matchups.",
                    color="gray",
                    variant="light",
                ),
            ]
        )

    upcoming_df["event_date"] = pd.to_datetime(upcoming_df["event_date"])
    events = upcoming_df.groupby(["event_uid", "event_title", "event_date", "event_location"])

    event_sections = []
    for (event_uid, event_title, event_date, event_location), fights in events:
        event_date_str = event_date.strftime("%B %d, %Y")
        fights_list = fights.to_dict("records")

        matchup_rows = [create_matchup_row(fight) for fight in fights_list]

        event_section = html.Div(
            [
                dmc.Paper(
                    [
                        dmc.Group(
                            [
                                html.Div(
                                    [
                                        dmc.Title(event_title, order=3),
                                        dmc.Text(f"{event_date_str} - {event_location}", c="gray", size="sm"),
                                    ]
                                ),
                                dmc.Badge(
                                    f"{len(fights_list)} fights",
                                    color="blue",
                                    variant="light",
                                ),
                            ],
                            justify="space-between",
                        ),
                    ],
                    p="md",
                    mb="md",
                    withBorder=True,
                ),
                html.Div(matchup_rows),
            ],
            style={"marginBottom": "2rem"},
        )
        event_sections.append(event_section)

    return html.Div(
        [
            dmc.Text(
                "Upcoming UFC events with scheduled matchups. Click fighter names to view detailed analysis.",
                c="gray",
                size="sm",
                mb="md",
            ),
            html.Div(event_sections),
        ]
    )


upcoming_fights_content = create_upcoming_fights_content()

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
                                        dmc.TabsTab("Upcoming Fights", value="upcoming"),
                                        dmc.TabsTab("Fighter Analysis", value="analysis"),
                                        dmc.TabsTab("Fighter Network", value="network"),
                                        dmc.TabsTab("Roster Analysis", value="roster"),
                                    ]
                                ),
                                dmc.TabsPanel(
                                    upcoming_fights_content,
                                    value="upcoming",
                                    pt="md",
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
                                dmc.TabsPanel(
                                    roster_analysis_content,
                                    value="roster",
                                    pt="md",
                                ),
                            ],
                            value="upcoming",
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
        Input("network-show-labels", "checked"),
    ],
)
def update_network_graph(
    search_fighter: str | None, target_fighter: str | None, show_labels: bool
):
    highlight_path = None
    path_info = ""

    if search_fighter and target_fighter and search_fighter != target_fighter:
        if search_fighter in fighter_graph and target_fighter in fighter_graph:
            try:
                path = nx.shortest_path(fighter_graph, search_fighter, target_fighter)
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
            except nx.NetworkXNoPath:
                path_info = dmc.Alert(
                    f"No path found between {search_fighter} and {target_fighter}",
                    color="red",
                    variant="light",
                )
        elif search_fighter not in fighter_graph:
            path_info = dmc.Alert(
                f"{search_fighter} not found in the network",
                color="orange",
                variant="light",
            )
        elif target_fighter not in fighter_graph:
            path_info = dmc.Alert(
                f"{target_fighter} not found in the network",
                color="orange",
                variant="light",
            )

    fig = create_network_figure(fighter_graph, search_fighter, highlight_path, show_labels)
    return fig, path_info


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


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8050)
