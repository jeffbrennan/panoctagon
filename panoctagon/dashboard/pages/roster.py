import polars as pl
import plotly.express as px
import plotly.graph_objects as go
from dash import Input, Output, callback, dcc, html

from panoctagon.common import get_engine
from panoctagon.dashboard.common import (
    DIVISION_COLORS,
    PLOT_COLORS,
    apply_figure_styling,
    filter_data,
    get_fighter_divisions,
    get_main_data,
)


def get_matchup_data() -> pl.DataFrame:
    engine = get_engine()
    with engine.connect() as conn:
        return pl.read_database(
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
            connection=conn,
        )


def get_roster_stats() -> pl.DataFrame:
    engine = get_engine()
    with engine.connect() as conn:
        return pl.read_database(
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
            connection=conn,
        )


@callback(
    Output("strikes-comparison", "figure"),
    [Input("fighter-select", "value")],
)
def update_strikes_comparison(fighter: str):
    df_filtered = filter_data(df, fighter)

    if df_filtered.height == 0:
        fig = px.bar()
    else:
        comparison = (
            df_filtered.group_by(["fight_uid", "event_date"])
            .agg(
                [
                    pl.col("total_strikes_landed").sum(),
                    pl.col("opponent_strikes_landed").sum(),
                ]
            )
            .sort("event_date")
            .with_columns(pl.col("event_date").dt.to_string("%Y-%m-%d"))
        )

        fig = go.Figure()
        fig.add_trace(
            go.Bar(
                x=comparison["event_date"].to_list(),
                y=comparison["total_strikes_landed"].to_list(),
                name="Fighter Strikes Landed",
                marker_color=PLOT_COLORS["primary"],
            )
        )
        fig.add_trace(
            go.Bar(
                x=comparison["event_date"].to_list(),
                y=comparison["opponent_strikes_landed"].to_list(),
                name="Opponent Strikes Landed",
                marker_color=PLOT_COLORS["tertiary"],
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
    roster_df: pl.DataFrame, fighter_divisions: dict[str, str]
) -> go.Figure:
    if roster_df.height == 0:
        fig = go.Figure()
        fig.update_layout(height=600)
        return apply_figure_styling(fig)

    roster_df = roster_df.with_columns(
        [
            pl.col("fighter_name")
            .map_elements(lambda x: normalize_division(fighter_divisions.get(x, "Unknown")), return_dtype=pl.String)
            .alias("division"),
            (pl.col("wins") / pl.col("total_fights") * 100).alias("win_pct"),
        ]
    )

    fig = go.Figure()

    for division in DIVISION_COLORS:
        div_data = roster_df.filter(pl.col("division") == division)
        if div_data.height == 0:
            continue

        hover_text = [
            f"<b>{row['fighter_name']}</b><br>"
            f"Fights: {row['total_fights']}<br>"
            f"Win%: {row['win_pct']:.1f}%<br>"
            f"Median Landed: {row['avg_strikes_landed']:.1f}<br>"
            f"Median Absorbed: {row['avg_strikes_absorbed']:.1f}"
            for row in div_data.iter_rows(named=True)
        ]

        fig.add_trace(
            go.Scatter(
                x=div_data["avg_strikes_landed"].to_list(),
                y=div_data["avg_strikes_absorbed"].to_list(),
                mode="markers",
                marker=dict(
                    size=(div_data["total_fights"].clip(upper_bound=30) + 5).to_list(),
                    color=DIVISION_COLORS[division],
                    line=dict(width=1, color="white"),
                    opacity=0.7,
                ),
                name=division,
                hovertext=hover_text,
                hoverinfo="text",
            )
        )

    max_landed = roster_df["avg_strikes_landed"].max()
    max_absorbed = roster_df["avg_strikes_absorbed"].max()
    max_val = float(max(max_landed if max_landed is not None else 0, max_absorbed if max_absorbed is not None else 0))  # type: ignore[arg-type]
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


def create_matchup_discrepancy_figure(matchup_df: pl.DataFrame) -> go.Figure:
    if matchup_df.height == 0:
        fig = go.Figure()
        fig.update_layout(height=500)
        return apply_figure_styling(fig)

    date_columns = ["event_date", "fighter1_dob", "fighter2_dob"]
    for col in date_columns:
        if matchup_df[col].dtype == pl.String:
            matchup_df = matchup_df.with_columns(
                pl.col(col).str.strptime(pl.Date, "%Y-%m-%d")
            )

    matchup_df = matchup_df.with_columns(
        [
            ((pl.col("event_date") - pl.col("fighter1_dob")).dt.total_days() / 365.25).alias(
                "fighter1_age"
            ),
            ((pl.col("event_date") - pl.col("fighter2_dob")).dt.total_days() / 365.25).alias(
                "fighter2_age"
            ),
        ]
    )

    results = []
    for row in matchup_df.iter_rows(named=True):
        if row["fighter1_age"] is None or row["fighter2_age"] is None:
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

    results_df = pl.DataFrame(results)

    fig = go.Figure()

    age_bins = [-20, -10, -5, -2, 0, 2, 5, 10, 20]
    results_df = results_df.with_columns(
        pl.col("age_diff").cut(breaks=age_bins).alias("age_bin_cat")
    ).with_columns(pl.col("age_bin_cat").cast(pl.String).alias("age_bin"))

    age_bin_mapping = {
        "(-20.0, -10.0]": "-20 to -10",
        "(-10.0, -5.0]": "-10 to -5",
        "(-5.0, -2.0]": "-5 to -2",
        "(-2.0, 0.0]": "-2 to 0",
        "(0.0, 2.0]": "0 to 2",
        "(2.0, 5.0]": "2 to 5",
        "(5.0, 10.0]": "5 to 10",
        "(10.0, 20.0]": "10 to 20",
    }
    results_df = results_df.with_columns(
        pl.col("age_bin")
        .map_elements(lambda x: age_bin_mapping.get(x, x), return_dtype=pl.String)
        .alias("age_bin")
    )
    age_win_rates = (
        results_df.group_by("age_bin")
        .agg([pl.col("won").mean().alias("win_rate"), pl.col("won").len().alias("count")])
        .filter(pl.col("count") >= 20)
    )

    reach_bins = [-15, -6, -3, -1, 1, 3, 6, 15]
    results_df = results_df.with_columns(
        pl.col("reach_diff").cut(breaks=reach_bins).alias("reach_bin_cat")
    ).with_columns(pl.col("reach_bin_cat").cast(pl.String).alias("reach_bin"))

    reach_bin_mapping = {
        "(-15.0, -6.0]": "-6+ in",
        "(-6.0, -3.0]": "-3 to -6",
        "(-3.0, -1.0]": "-1 to -3",
        "(-1.0, 1.0]": "Even",
        "(1.0, 3.0]": "+1 to +3",
        "(3.0, 6.0]": "+3 to +6",
        "(6.0, 15.0]": "+6+ in",
    }
    results_df = results_df.with_columns(
        pl.col("reach_bin")
        .map_elements(lambda x: reach_bin_mapping.get(x, x), return_dtype=pl.String)
        .alias("reach_bin")
    )
    reach_win_rates = (
        results_df.group_by("reach_bin")
        .agg([pl.col("won").mean().alias("win_rate"), pl.col("won").len().alias("count")])
        .filter(pl.col("count") >= 20)
    )

    exp_bins = [-50, -10, -5, -2, 0, 2, 5, 10, 50]
    results_df = results_df.with_columns(
        pl.col("exp_diff").cut(breaks=exp_bins).alias("exp_bin_cat")
    ).with_columns(pl.col("exp_bin_cat").cast(pl.String).alias("exp_bin"))

    exp_bin_mapping = {
        "(-50.0, -10.0]": "-10+ fights",
        "(-10.0, -5.0]": "-5 to -10",
        "(-5.0, -2.0]": "-2 to -5",
        "(-2.0, 0.0]": "-2 to 0",
        "(0.0, 2.0]": "0 to 2",
        "(2.0, 5.0]": "2 to 5",
        "(5.0, 10.0]": "5 to 10",
        "(10.0, 50.0]": "10+ fights",
    }
    results_df = results_df.with_columns(
        pl.col("exp_bin")
        .map_elements(lambda x: exp_bin_mapping.get(x, x), return_dtype=pl.String)
        .alias("exp_bin")
    )
    exp_win_rates = (
        results_df.group_by("exp_bin")
        .agg([pl.col("won").mean().alias("win_rate"), pl.col("won").len().alias("count")])
        .filter(pl.col("count") >= 20)
    )

    fig.add_trace(
        go.Scatter(
            x=age_win_rates["age_bin"].to_list(),
            y=(age_win_rates["win_rate"] * 100).to_list(),
            mode="lines+markers",
            name="Age Advantage",
            line=dict(color=PLOT_COLORS["primary"], width=2),
            marker=dict(size=10),
            hovertemplate="Age diff: %{x}<br>Win rate: %{y:.1f}%<br>Fights: %{customdata}<extra></extra>",
            customdata=age_win_rates["count"].to_list(),
        )
    )

    fig.add_trace(
        go.Scatter(
            x=reach_win_rates["reach_bin"].to_list(),
            y=(reach_win_rates["win_rate"] * 100).to_list(),
            mode="lines+markers",
            name="Reach Advantage",
            line=dict(color=PLOT_COLORS["secondary"], width=2),
            marker=dict(size=10),
            hovertemplate="Reach diff: %{x}<br>Win rate: %{y:.1f}%<br>Fights: %{customdata}<extra></extra>",
            customdata=reach_win_rates["count"].to_list(),
            visible="legendonly",
        )
    )

    fig.add_trace(
        go.Scatter(
            x=exp_win_rates["exp_bin"].to_list(),
            y=(exp_win_rates["win_rate"] * 100).to_list(),
            mode="lines+markers",
            name="Experience Advantage",
            line=dict(color=PLOT_COLORS["tertiary"], width=2),
            marker=dict(size=10),
            hovertemplate="Exp diff: %{x}<br>Win rate: %{y:.1f}%<br>Fights: %{customdata}<extra></extra>",
            customdata=exp_win_rates["count"].to_list(),
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


def create_striking_target_winrate_figure(roster_df: pl.DataFrame) -> go.Figure:
    if roster_df.height == 0:
        fig = go.Figure()
        fig.update_layout(height=500)
        return apply_figure_styling(fig)

    roster_df = (
        roster_df.filter(pl.col("total_sig_strikes") > 0)
        .with_columns(
            [
                (pl.col("total_head_strikes") / pl.col("total_sig_strikes") * 100).alias("head_pct"),
                (pl.col("total_body_strikes") / pl.col("total_sig_strikes") * 100).alias("body_pct"),
                (pl.col("total_leg_strikes") / pl.col("total_sig_strikes") * 100).alias("leg_pct"),
                (pl.col("wins") / pl.col("total_fights") * 100).alias("win_pct"),
            ]
        )
    )

    bins = [0, 40, 50, 60, 70, 80, 100]
    labels = ["0-40%", "40-50%", "50-60%", "60-70%", "70-80%", "80-100%"]

    target_data = []
    for target, col in [("Head", "head_pct"), ("Body", "body_pct"), ("Leg", "leg_pct")]:
        temp_df = roster_df.with_columns(
            pl.col(col).cut(breaks=bins).alias("bin_cat")
        ).with_columns(
            pl.col("bin_cat").cast(pl.String).alias("bin")
        )

        bin_mapping = {
            "(-inf, 0.0]": None,
            "(0.0, 40.0]": "0-40%",
            "(40.0, 50.0]": "40-50%",
            "(50.0, 60.0]": "50-60%",
            "(60.0, 70.0]": "60-70%",
            "(70.0, 80.0]": "70-80%",
            "(80.0, 100.0]": "80-100%",
            "(100.0, inf]": None,
        }

        for bin_str, label in bin_mapping.items():
            if label is None:
                continue
            bin_data = temp_df.filter(pl.col("bin") == bin_str)
            if bin_data.height >= 5:
                target_data.append(
                    {
                        "target": target,
                        "bin": label,
                        "avg_win_pct": bin_data["win_pct"].mean(),
                        "count": bin_data.height,
                    }
                )

    if not target_data:
        fig = go.Figure()
        fig.update_layout(height=500)
        return apply_figure_styling(fig)

    target_df = pl.DataFrame(target_data)

    fig = go.Figure()
    colors = {"Head": PLOT_COLORS["head"], "Body": PLOT_COLORS["body"], "Leg": PLOT_COLORS["leg"]}

    for target in ["Head", "Body", "Leg"]:
        t_data = target_df.filter(pl.col("target") == target)
        if t_data.height == 0:
            continue

        hover_text = [
            f"<b>{target} Strikes: {row['bin']}</b><br>"
            f"Avg Win%: {row['avg_win_pct']:.1f}%<br>"
            f"Fighters: {row['count']}"
            for row in t_data.iter_rows(named=True)
        ]

        fig.add_trace(
            go.Bar(
                x=t_data["bin"].to_list(),
                y=t_data["avg_win_pct"].to_list(),
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
                html.Div("Striking Type", className="plot-title"),
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
                html.Div("Matchup Discrepancy", className="plot-title"),
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
