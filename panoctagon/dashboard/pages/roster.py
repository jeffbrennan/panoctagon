import dash_mantine_components as dmc
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import Input, Output, callback, dcc, html

from panoctagon.common import get_engine
from panoctagon.dashboard.common import (
    DIVISION_COLORS,
    apply_figure_styling,
    filter_data,
    get_fighter_divisions,
    get_main_data,
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
            round_stats as (
                select
                    fs.fighter_uid,
                    fd.fighter_name,
                    fs.fight_uid,
                    fs.round_num,
                    fr.fighter_result,
                    fs.total_strikes_landed,
                    sum(fs.total_strikes_landed) over (partition by fs.fighter_uid, fs.fight_uid) as fight_strikes_landed,
                    sum(fs.sig_strikes_head_landed) over (partition by fs.fighter_uid, fs.fight_uid) as fight_head_strikes,
                    sum(fs.sig_strikes_body_landed) over (partition by fs.fighter_uid, fs.fight_uid) as fight_body_strikes,
                    sum(fs.sig_strikes_leg_landed) over (partition by fs.fighter_uid, fs.fight_uid) as fight_leg_strikes
                from ufc_fight_stats fs
                inner join fighter_details fd on fs.fighter_uid = fd.fighter_uid
                inner join fight_results_long fr
                    on fs.fight_uid = fr.fight_uid
                    and fs.fighter_uid = fr.fighter_uid
            ),
            opponent_round_stats as (
                select
                    fs.fight_uid,
                    fs.fighter_uid as opponent_uid,
                    fs.round_num,
                    fs.total_strikes_landed as opponent_strikes_landed
                from ufc_fight_stats fs
            ),
            combined_rounds as (
                select
                    rs.fighter_uid,
                    rs.fighter_name,
                    rs.fight_uid,
                    rs.fighter_result,
                    rs.total_strikes_landed,
                    ors.opponent_strikes_landed,
                    rs.fight_strikes_landed,
                    rs.fight_head_strikes,
                    rs.fight_body_strikes,
                    rs.fight_leg_strikes
                from round_stats rs
                inner join opponent_round_stats ors
                    on rs.fight_uid = ors.fight_uid
                    and rs.round_num = ors.round_num
                    and rs.fighter_uid != ors.opponent_uid
            )
        select
            fighter_uid,
            fighter_name,
            count(distinct fight_uid) as total_fights,
            count(distinct case when fighter_result = 'WIN' then fight_uid end) as wins,
            percentile_cont(0.5) within group (order by total_strikes_landed) as avg_strikes_landed,
            percentile_cont(0.5) within group (order by opponent_strikes_landed) as avg_strikes_absorbed,
            sum(fight_head_strikes) as total_head_strikes,
            sum(fight_body_strikes) as total_body_strikes,
            sum(fight_leg_strikes) as total_leg_strikes,
            sum(fight_head_strikes + fight_body_strikes + fight_leg_strikes) as total_sig_strikes
        from combined_rounds
        group by fighter_uid, fighter_name
        having count(distinct fight_uid) >= 5
        """,
        get_engine(),
    )


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


def normalize_division(db_division: str) -> str:
    mapping = {
        "LIGHTWEIGHT": "Lightweight",
        "WELTERWEIGHT": "Welterweight",
        "MIDDLEWEIGHT": "Middleweight",
        "LIGHT_HEAVYWEIGHT": "Light Heavyweight",
        "HEAVYWEIGHT": "Heavyweight",
        "FLYWEIGHT": "Flyweight",
        "BANTAMWEIGHT": "Bantamweight",
        "FEATHERWEIGHT": "Featherweight",
        "STRAWWEIGHT": "Strawweight",
        "WOMENS_STRAWWEIGHT": "Women's Strawweight",
        "WOMENS_FLYWEIGHT": "Women's Flyweight",
        "WOMENS_BANTAMWEIGHT": "Women's Bantamweight",
        "WOMENS_FEATHERWEIGHT": "Women's Featherweight",
        "CATCH_WEIGHT": "Catch Weight",
        "OPEN_WEIGHT": "Open Weight",
        "SUPER_HEAVYWEIGHT": "Super Heavyweight",
    }
    return mapping.get(db_division, "Unknown")


def create_fighter_clustering_figure(
    roster_df: pd.DataFrame, fighter_divisions: dict[str, str]
) -> go.Figure:
    if roster_df.empty:
        fig = go.Figure()
        fig.update_layout(height=600)
        return apply_figure_styling(fig)

    roster_df = roster_df.copy()
    roster_df["division"] = (
        roster_df["fighter_name"].map(fighter_divisions).apply(normalize_division).fillna("Unknown")
    )
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
            f"Median Landed: {row['avg_strikes_landed']:.1f}<br>"
            f"Median Absorbed: {row['avg_strikes_absorbed']:.1f}"
            for _, row in div_data.iterrows()
        ]

        fig.add_trace(
            go.Scatter(
                x=div_data["avg_strikes_landed"].tolist(),
                y=div_data["avg_strikes_absorbed"].tolist(),
                mode="markers",
                marker=dict(
                    size=(div_data["total_fights"].clip(upper=30) + 5).tolist(),
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

    fig.add_annotation(x=max_val * 0.95, y=max_val * 0.01, text="Slick Strikers", showarrow=False)
    fig.add_annotation(x=max_val * 0.95, y=max_val * 0.99, text="Brawlers", showarrow=False)
    fig.add_annotation(x=max_val * 0.1, y=max_val * 0.99, text="Punching Bags", showarrow=False)
    fig.add_annotation(x=max_val * 0.1, y=max_val * 0.01, text="Cautious Strikers", showarrow=False)

    fig.update_layout(
        xaxis_title="Median Strikes Landed Per Round",
        yaxis_title="Median Strikes Absorbed Per Round",
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
    age_labels = [
        "-20 to -10",
        "-10 to -5",
        "-5 to -2",
        "-2 to 0",
        "0 to 2",
        "2 to 5",
        "5 to 10",
        "10 to 20",
    ]
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
    exp_labels = [
        "-10+ fights",
        "-5 to -10",
        "-2 to -5",
        "-2 to 0",
        "0 to 2",
        "2 to 5",
        "5 to 10",
        "10+ fights",
    ]
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


fighter_divisions = get_fighter_divisions()
roster_df = get_roster_stats()
matchup_df = get_matchup_data()
df = get_main_data()
roster_analysis_content = html.Div(
    [
        html.Div(
            [
                html.Div(
                    "Fighter Type Clustering",
                    className="plot-title",
                ),
                dmc.Text(
                    "Fighters grouped by median strikes landed vs absorbed per round. "
                    "Size indicates number of fights. Fighters with 5+ fights shown.",
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
