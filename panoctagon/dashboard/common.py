import base64
from pathlib import Path

import plotly.graph_objects as go
import polars as pl
from dash import dcc, html

from panoctagon.common import get_engine


def apply_figure_styling(fig: go.Figure) -> go.Figure:
    fig.update_layout(
        plot_bgcolor="rgb(242, 240, 227)",
        paper_bgcolor="rgb(242, 240, 227)",
        font=dict(family="JetBrains Mono, monospace", color="#1a1a1a"),
        title=None,
        margin=dict(l=68, r=10, t=0, b=10),
        hoverlabel=dict(
            bgcolor=PLOT_COLORS["loss"],
            font=dict(color=PLOT_COLORS["win"]),
        ),
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
    title: str, graph_id: str, margin_bottom: bool = False, has_top_legend: bool = False
) -> html.Div:
    title_class = "plot-title plot-title-with-legend" if has_top_legend else "plot-title"
    return html.Div(
        [
            html.Div(
                title,
                className=title_class,
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
        style={"width": "100%", "marginBottom": "2rem"} if margin_bottom else {"width": "100%"},
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
    HEADSHOTS_DIR = Path(__file__).parents[2] / "data" / "raw" / "ufc" / "fighter_headshots"

    image_extensions = [".png", ".jpg", ".jpeg", ".webp"]
    headshot_path = None
    mime_type = "image/png"

    for ext in image_extensions:
        candidate_path = HEADSHOTS_DIR / f"{fighter_uid}_headshot{ext}"
        if candidate_path.exists():
            headshot_path = candidate_path
            if ext in [".jpg", ".jpeg"]:
                mime_type = "image/jpeg"
            elif ext == ".webp":
                mime_type = "image/webp"
            break

    if headshot_path is None:
        return PLACEHOLDER_IMAGE

    with open(headshot_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}"


def get_main_data() -> pl.DataFrame:
    engine = get_engine()
    with engine.connect() as conn:
        df = pl.read_database(
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
            connection=conn,
        )
    if df["event_date"].dtype == pl.String:
        df = df.with_columns(pl.col("event_date").str.strptime(pl.Date, "%Y-%m-%d"))
    return df


def filter_data(df: pl.DataFrame, fighter: str) -> pl.DataFrame:
    return df.filter(pl.col("fighter_name") == fighter)


def get_fighter_divisions() -> dict[str, str]:
    engine = get_engine()
    with engine.connect() as conn:
        df = pl.read_database(
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
            connection=conn,
        )
    return dict(zip(df["fighter_name"].to_list(), df["fight_division"].to_list()))


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

PLOT_COLORS = {
    "l1": "#1a1a1a",
    "l2": "#3a3a3a",
    "l3": "#5c5c5c",
    "l4": "#7a7a7a",
    "l5": "#9a9a9a",
    "l6": "#b8b8b8",
    "l7": "#d0d0d0",
    "win": "rgb(242, 240, 227)",
    "loss": "rgb(26,26,26)",
    "win_transparent": "rgba(242, 240, 227, 0.7)",
    "loss_transparent": "rgba(26, 26, 26, 1.0)",
    "draw": "#5c5c5c",
    "neutral": "#5c5c5c",
    "head": "#1a1a1a",
    "body": "#5c5c5c",
    "leg": "#9a9a9a",
}

PLOT_COLOR_SEQUENCE = [
    "#1a1a1a",
    "#3a3a3a",
    "#5c5c5c",
    "#7a7a7a",
    "#9a9a9a",
    "#b8b8b8",
    "#d0d0d0",
]
