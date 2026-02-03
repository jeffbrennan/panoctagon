import dash_mantine_components as dmc
import plotly.express as px
import plotly.graph_objects as go
import polars as pl
from dash import Input, Output, callback, dcc, html

from panoctagon.common import get_engine
from panoctagon.dashboard.common import (
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
                f.fight_division,
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
                    pl.col("title").first(),
                    pl.col("fighter_result").first(),
                    pl.col("opponent_name").first(),
                    pl.col("total_strikes_landed").sum(),
                    pl.col("opponent_strikes_landed").sum(),
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
                comparison["title"].to_list(),
                comparison["result_label"].to_list(),
                comparison["opponent_name"].to_list(),
            )
        )

        fig = go.Figure()
        fig.add_trace(
            go.Bar(
                x=comparison["event_date"].to_list(),
                y=comparison["total_strikes_landed"].to_list(),
                name="Landed",
                marker_line_color=PLOT_COLORS["l1"],
                marker_line_width=2,
                marker_color=PLOT_COLORS["win"],
                customdata=customdata,
                hovertemplate="<b>%{customdata[0]}</b> | %{x}<br>%{customdata[1]} <b>%{customdata[2]}</b><br>Landed: %{y}<extra></extra>",
            )
        )
        fig.add_trace(
            go.Bar(
                x=comparison["event_date"].to_list(),
                y=comparison["opponent_strikes_landed"].to_list(),
                name="Absorbed",
                marker_line_color=PLOT_COLORS["l1"],
                marker_line_width=2,
                marker_color=PLOT_COLORS["loss"],
                customdata=customdata,
                hovertemplate="<b>%{customdata[0]}</b> | %{x}<br>%{customdata[1]} <b>%{customdata[2]}</b><br>Absorbed: %{y}<extra></extra>",
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


def create_fighter_clustering_figure(roster_df: pl.DataFrame) -> go.Figure:
    if roster_df.height == 0:
        fig = go.Figure()
        fig.update_layout(height=600)
        return apply_figure_styling(fig)

    engine = get_engine()
    with engine.connect() as conn:
        opposition_df = pl.read_database(
            """
            WITH fight_results AS (
                SELECT
                    fighter1_uid AS fighter_uid,
                    fighter2_uid AS opponent_uid,
                    fighter1_result AS result
                FROM ufc_fights
                WHERE fighter1_result IN ('WIN', 'LOSS')
                UNION ALL
                SELECT
                    fighter2_uid AS fighter_uid,
                    fighter1_uid AS opponent_uid,
                    fighter2_result AS result
                FROM ufc_fights
                WHERE fighter2_result IN ('WIN', 'LOSS')
            ),
            opponent_records AS (
                SELECT
                    fighter_uid,
                    COUNT(CASE WHEN result = 'WIN' THEN 1 END) AS wins
                FROM fight_results
                GROUP BY fighter_uid
            ),
            beaten_opponents AS (
                SELECT
                    fr.fighter_uid,
                    SUM(COALESCE(op.wins, 0)) AS opposition_strength
                FROM fight_results fr
                LEFT JOIN opponent_records op ON fr.opponent_uid = op.fighter_uid
                WHERE fr.result = 'WIN'
                GROUP BY fr.fighter_uid
            )
            SELECT
                f.first_name || ' ' || f.last_name AS fighter_name,
                COALESCE(bo.opposition_strength, 0) AS opposition_strength
            FROM ufc_fighters f
            LEFT JOIN beaten_opponents bo ON f.fighter_uid = bo.fighter_uid
            """,
            connection=conn,
        )

    roster_df = roster_df.join(opposition_df, on="fighter_name", how="left")
    roster_df = roster_df.with_columns(pl.col("opposition_strength").fill_null(0))

    roster_df = roster_df.with_columns(
        [
            (pl.col("wins") / pl.col("total_fights") * 100).alias("win_pct"),
            (
                (pl.col("opposition_strength").rank() - 1)
                / (pl.col("opposition_strength").len() - 1)
                * 100
            ).alias("opposition_strength_normalized"),
        ]
    )

    hover_text = [
        f"<b>{row['fighter_name']}</b><br>"
        f"Fights: {row['total_fights']}<br>"
        f"Win%: {row['win_pct']:.1f}%<br>"
        f"Median Landed: {row['avg_strikes_landed']:.1f}<br>"
        f"Median Absorbed: {row['avg_strikes_absorbed']:.1f}<br>"
        f"Opposition Strength: {row['opposition_strength']}"
        for row in roster_df.iter_rows(named=True)
    ]

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=roster_df["avg_strikes_landed"].to_list(),
            y=roster_df["avg_strikes_absorbed"].to_list(),
            mode="markers",
            marker=dict(
                size=(roster_df["total_fights"].clip(upper_bound=30) + 5).to_list(),
                color=roster_df["opposition_strength_normalized"].to_list(),
                colorscale=[[0, "#c8c8c8"], [0.5, "#7a7a7a"], [1, "#1a1a1a"]],
                cmin=0,
                cmax=100,
                line=dict(width=1, color="rgb(33,33,33)"),
                opacity=1,
                colorbar=dict(
                    title="Opposition<br>Strength",
                    thickness=15,
                    len=0.5,
                    x=1.02,
                ),
            ),
            hovertext=hover_text,
            hoverinfo="text",
            showlegend=False,
        )
    )

    max_landed = roster_df["avg_strikes_landed"].max()
    max_absorbed = roster_df["avg_strikes_absorbed"].max()
    max_val = float(
        max(
            max_landed if max_landed is not None else 0,
            max_absorbed if max_absorbed is not None else 0,
        )
    )  # type: ignore[arg-type]
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
            matchup_df = matchup_df.with_columns(pl.col(col).str.strptime(pl.Date, "%Y-%m-%d"))

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

    age_bin_order = [
        "-20 to -10",
        "-10 to -5",
        "-5 to -2",
        "-2 to 0",
        "0 to 2",
        "2 to 5",
        "5 to 10",
        "10 to 20",
    ]
    results_df = results_df.with_columns(
        pl.col("age_bin")
        .replace_strict(
            [
                "(-20, -10]",
                "(-10, -5]",
                "(-5, -2]",
                "(-2, 0]",
                "(0, 2]",
                "(2, 5]",
                "(5, 10]",
                "(10, 20]",
            ],
            age_bin_order,
            default=None,
        )
        .alias("age_bin")
    )
    age_win_rates = (
        results_df.group_by("age_bin")
        .agg([pl.col("won").mean().alias("win_rate"), pl.col("won").len().alias("count")])
        .filter(pl.col("count") >= 20)
        .with_columns(
            pl.col("age_bin")
            .replace_strict(age_bin_order, list(range(len(age_bin_order))), default=99)
            .alias("_sort")
        )
        .sort("_sort")
        .drop("_sort")
    )

    reach_bins = [-15, -6, -3, -1, 1, 3, 6, 15]
    results_df = results_df.with_columns(
        pl.col("reach_diff").cut(breaks=reach_bins).alias("reach_bin_cat")
    ).with_columns(pl.col("reach_bin_cat").cast(pl.String).alias("reach_bin"))

    reach_bin_order = [
        "-6+ in",
        "-6+ in",
        "-3 to -6",
        "-1 to -3",
        "Even",
        "+1 to +3",
        "+3 to +6",
        "+6+ in",
        "+6+ in",
    ]
    results_df = results_df.with_columns(
        pl.col("reach_bin")
        .replace_strict(
            [
                "(-inf, -15]",
                "(-15, -6]",
                "(-6, -3]",
                "(-3, -1]",
                "(-1, 1]",
                "(1, 3]",
                "(3, 6]",
                "(6, 15]",
                "(15, inf]",
            ],
            reach_bin_order,
            default=None,
        )
        .alias("reach_bin")
    )
    reach_bin_sort_order = [
        "-6+ in",
        "-3 to -6",
        "-1 to -3",
        "Even",
        "+1 to +3",
        "+3 to +6",
        "+6+ in",
    ]
    reach_win_rates = (
        results_df.group_by("reach_bin")
        .agg([pl.col("won").mean().alias("win_rate"), pl.col("won").len().alias("count")])
        .filter(pl.col("count") >= 20)
        .with_columns(
            pl.col("reach_bin")
            .replace_strict(
                reach_bin_sort_order, list(range(len(reach_bin_sort_order))), default=99
            )
            .alias("_sort")
        )
        .sort("_sort")
        .drop("_sort")
    )

    exp_bins = [-50, -10, -5, -2, 0, 2, 5, 10, 50]
    results_df = results_df.with_columns(
        pl.col("exp_diff").cut(breaks=exp_bins).alias("exp_bin_cat")
    ).with_columns(pl.col("exp_bin_cat").cast(pl.String).alias("exp_bin"))

    exp_bin_order = [
        "-10+ fights",
        "-5 to -10",
        "-2 to -5",
        "-2 to 0",
        "0 to 2",
        "2 to 5",
        "5 to 10",
        "10+ fights",
    ]
    results_df = results_df.with_columns(
        pl.col("exp_bin")
        .replace_strict(
            [
                "(-50, -10]",
                "(-10, -5]",
                "(-5, -2]",
                "(-2, 0]",
                "(0, 2]",
                "(2, 5]",
                "(5, 10]",
                "(10, 50]",
            ],
            exp_bin_order,
            default=None,
        )
        .alias("exp_bin")
    )
    exp_win_rates = (
        results_df.group_by("exp_bin")
        .agg([pl.col("won").mean().alias("win_rate"), pl.col("won").len().alias("count")])
        .filter(pl.col("count") >= 20)
        .with_columns(
            pl.col("exp_bin")
            .replace_strict(exp_bin_order, list(range(len(exp_bin_order))), default=99)
            .alias("_sort")
        )
        .sort("_sort")
        .drop("_sort")
    )

    fig.add_trace(
        go.Scatter(
            x=age_win_rates["age_bin"].to_list(),
            y=(age_win_rates["win_rate"] * 100).to_list(),
            mode="lines+markers",
            name="Age Advantage",
            line=dict(color=PLOT_COLORS["l1"], width=2),
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
            line=dict(color=PLOT_COLORS["l2"], width=2),
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
            line=dict(color=PLOT_COLORS["l3"], width=2),
            marker=dict(size=10),
            hovertemplate="Exp diff: %{x}<br>Win rate: %{y:.1f}%<br>Fights: %{customdata}<extra></extra>",
            customdata=exp_win_rates["count"].to_list(),
            visible="legendonly",
        )
    )

    fig.add_hline(y=50, line_dash="dash", line_color="gray", opacity=0.5)

    fig.update_layout(
        xaxis_title="Advantage",
        yaxis_title="Win %",
        height=500,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5),
        yaxis=dict(range=[30, 70]),
    )

    return apply_figure_styling(fig)


def create_striking_target_winrate_figure(division: str) -> go.Figure:
    engine = get_engine()
    with engine.connect() as conn:
        target_df = pl.read_database(
            """
            WITH base AS (
                SELECT
                    e.title AS event_name,
                    e.event_date,
                    f.event_uid,
                    f.fight_uid,
                    f.fight_division,
                    f.fighter1_uid AS fighter_uid,
                    f.fighter1_result AS result
                FROM ufc_fights f
                INNER JOIN ufc_events e ON f.event_uid = e.event_uid
                UNION ALL
                SELECT
                    e.title AS event_name,
                    e.event_date,
                    f.event_uid,
                    f.fight_uid,
                    f.fight_division,
                    f.fighter2_uid AS fighter_uid,
                    f.fighter2_result AS result
                FROM ufc_fights f
                INNER JOIN ufc_events e ON f.event_uid = e.event_uid
            ),
            counts AS (
                SELECT
                    fight_uid,
                    fighter_uid,
                    sum(sig_strikes_landed) AS sig_strikes_landed,
                    sum(sig_strikes_head_landed) AS sig_strikes_head_landed,
                    sum(sig_strikes_body_landed) AS sig_strikes_body_landed,
                    sum(sig_strikes_leg_landed) AS sig_strikes_leg_landed
                FROM ufc_fight_stats
                GROUP BY fight_uid, fighter_uid
            ),
            pcts AS (
                SELECT
                    fight_uid,
                    fighter_uid,
                    sig_strikes_landed AS total_strikes,
                    sig_strikes_head_landed / NULLIF(sig_strikes_landed, 0) AS head_pct,
                    sig_strikes_body_landed / NULLIF(sig_strikes_landed, 0) AS body_pct,
                    sig_strikes_leg_landed / NULLIF(sig_strikes_landed, 0) AS leg_pct
                FROM counts
                WHERE sig_strikes_landed > 0
            ),
            final AS (
                SELECT
                    base.event_name,
                    base.event_date,
                    base.event_uid,
                    base.fight_uid,
                    base.fight_division,
                    base.fighter_uid,
                    fi.first_name || ' ' || fi.last_name AS fighter_name,
                    base.result,
                    pcts.head_pct,
                    pcts.body_pct,
                    pcts.leg_pct
                FROM base
                INNER JOIN pcts
                ON base.fight_uid = pcts.fight_uid
                AND base.fighter_uid = pcts.fighter_uid
                INNER JOIN ufc_fighters fi ON base.fighter_uid = fi.fighter_uid
            )
            SELECT * FROM final
            WHERE result in ('WIN', 'LOSS')
            AND head_pct IS NOT NULL
            AND body_pct IS NOT NULL
            AND leg_pct IS NOT NULL
            """,
            connection=conn,
        )

    if division != "ALL":
        target_df = target_df.filter(pl.col("fight_division") == division)
    target_df = target_df.drop("fight_division")

    if target_df.height == 0:
        fig = go.Figure()
        fig.update_layout(height=500)
        return apply_figure_styling(fig)

    target_df = target_df.unpivot(
        index=[
            "event_name",
            "event_date",
            "event_uid",
            "fight_uid",
            "fighter_uid",
            "fighter_name",
            "result",
        ],
        on=["head_pct", "body_pct", "leg_pct"],
        variable_name="target",
        value_name="pct",
    )

    target_df = target_df.with_columns(
        [
            pl.col("target").replace({"head_pct": "Head", "body_pct": "Body", "leg_pct": "Leg"}),
        ]
    )

    if target_df["event_date"].dtype == pl.String:
        target_df = target_df.with_columns(pl.col("event_date").str.strptime(pl.Date, "%Y-%m-%d"))

    target_df = target_df.with_columns(
        pl.col("event_date").dt.to_string("%Y-%m-%d").alias("event_date_str")
    )

    cat_positions = {"Head": 0, "Body": 1, "Leg": 2}
    result_offsets = {"WIN": -0.2, "LOSS": 0.2}
    result_fill_colors = {
        "WIN": PLOT_COLORS["win"],
        "LOSS": PLOT_COLORS["loss"],
    }
    legend_shown: set[str] = set()

    fig = go.Figure()

    for result in ["WIN", "LOSS"]:
        for target in ["Head", "Body", "Leg"]:
            subset = target_df.filter((pl.col("target") == target) & (pl.col("result") == result))
            if subset.height == 0:
                continue

            y_pos = cat_positions[target] + result_offsets[result]
            show = result not in legend_shown
            if show:
                legend_shown.add(result)

            pct = subset["pct"]
            q1 = pct.quantile(0.25, interpolation="linear")
            q3 = pct.quantile(0.75, interpolation="linear")
            med = pct.median()
            assert q1 is not None and q3 is not None and med is not None
            iqr = q3 - q1

            fence_low = q1 - 1.5 * iqr
            fence_high = q3 + 1.5 * iqr
            whisker_low = pct.filter(pct >= fence_low).min()
            whisker_high = pct.filter(pct <= fence_high).max()
            assert whisker_low is not None and whisker_high is not None

            fig.add_trace(
                go.Box(
                    q1=[q1],
                    median=[med],
                    q3=[q3],
                    lowerfence=[whisker_low],
                    upperfence=[whisker_high],
                    y=[y_pos],
                    name=result,
                    legendgroup=result,
                    showlegend=show,
                    fillcolor=result_fill_colors[result],
                    line_color=PLOT_COLORS["l1"],
                    orientation="h",
                    hoverinfo="none",
                )
            )

            outliers = subset.filter((pl.col("pct") < fence_low) | (pl.col("pct") > fence_high))

            if outliers.height > 0:
                fig.add_trace(
                    go.Scatter(
                        x=outliers["pct"].to_list(),
                        y=[y_pos] * outliers.height,
                        mode="markers",
                        marker=dict(size=6, color=PLOT_COLORS["l1"]),
                        showlegend=False,
                        customdata=outliers.select(
                            ["fighter_name", "event_name", "event_date_str"]
                        ).rows(),
                        hovertemplate=(
                            "<b>%{customdata[0]}</b><br>"
                            "%{customdata[1]}<br>"
                            "%{customdata[2]}<br>"
                            "Target %: %{x:.1%}<br>"
                            "<extra></extra>"
                        ),
                    )
                )

    fig.update_layout(
        xaxis_title="% of Significant Strikes",
        yaxis=dict(
            title="Target",
            tickvals=[0, 1, 2],
            ticktext=["Head", "Body", "Leg"],
            range=[-0.5, 2.5],
        ),
        height=500,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="center",
            x=0.5,
            title=None,
        ),
    )

    return apply_figure_styling(fig)


fighter_divisions = get_fighter_divisions()
roster_df = get_roster_stats()
matchup_df = get_matchup_data()
df = get_main_data()


@callback(
    Output("fighter-clustering", "figure"),
    Input("roster-division-dropdown", "value"),
)
def update_fighter_clustering(division: str):
    filtered_df = roster_df
    if division != "ALL":
        fighters_in_division = [name for name, div in fighter_divisions.items() if div == division]
        filtered_df = filtered_df.filter(pl.col("fighter_name").is_in(fighters_in_division))
    return create_fighter_clustering_figure(filtered_df)


@callback(
    Output("striking-target-winrate", "figure"),
    Input("roster-division-dropdown", "value"),
)
def update_striking_target(division: str):
    return create_striking_target_winrate_figure(division)


@callback(
    Output("matchup-discrepancy", "figure"),
    Input("roster-division-dropdown", "value"),
)
def update_matchup_discrepancy(division: str):
    filtered_df = matchup_df
    if division != "ALL":
        filtered_df = filtered_df.filter(pl.col("fight_division") == division)
    return create_matchup_discrepancy_figure(filtered_df)


roster_analysis_content = html.Div(
    [
        html.Div(
            [
                dmc.Text("Division", size="sm", mb="xs", style={"color": "#1a1a1a"}),
                dmc.Select(
                    id="roster-division-dropdown",
                    data=[  # pyright: ignore[reportArgumentType]
                        {"value": "ALL", "label": "All"},
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
                    value="MIDDLEWEIGHT",
                    searchable=True,
                    clearable=False,
                ),
            ],
            style={"width": "25%", "marginBottom": "1.5rem"},
        ),
        html.Div(
            [
                html.Div("Striking Type", className="plot-title"),
                html.Div(
                    dcc.Graph(
                        id="fighter-clustering",
                        figure={},
                        config={"displayModeBar": False},
                        responsive=True,
                    ),
                    className="plot-container-wrapper",
                ),
            ],
            style={"width": "100%", "marginBottom": "2rem"},
        ),
        html.Div(
            [
                html.Div(
                    "Striking Target vs Win Rate",
                    className="plot-title plot-title-with-legend",
                ),
                html.Div(
                    dcc.Graph(
                        id="striking-target-winrate",
                        figure={},
                        config={"displayModeBar": False},
                        responsive=True,
                    ),
                    className="plot-container-wrapper",
                ),
            ],
            style={"width": "100%", "marginBottom": "2rem"},
        ),
        html.Div(
            [
                html.Div("Matchup Discrepancy", className="plot-title plot-title-with-legend"),
                html.Div(
                    dcc.Graph(
                        id="matchup-discrepancy",
                        figure={},
                        config={"displayModeBar": False},
                        responsive=True,
                    ),
                    className="plot-container-wrapper",
                ),
            ],
            style={"width": "100%"},
        ),
    ]
)
