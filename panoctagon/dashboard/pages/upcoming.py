import dash_mantine_components as dmc
import pandas as pd
from dash import html

from panoctagon.common import get_engine
from panoctagon.dashboard.common import get_headshot_base64


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


def create_matchup_card(
    fight: dict,
    fighter_num: int,
    opponent_num: int,
) -> dmc.Card:
    fighter_name = fight[f"fighter{fighter_num}_name"]
    fighter_uid = fight[f"fighter{fighter_num}_uid"]
    fighter_wins = fight[f"fighter{fighter_num}_wins"]
    fighter_losses = fight[f"fighter{fighter_num}_losses"]
    fighter_draws = fight[f"fighter{fighter_num}_draws"]
    fighter_record = f"{fighter_wins}-{fighter_losses}-{fighter_draws}"
    fighter_total_fights = fight[f"fighter{fighter_num}_total_fights"]
    fighter_reach = fight[f"fighter{fighter_num}_reach"]
    fighter_height = fight[f"fighter{fighter_num}_height"]
    fighter_stance = fight[f"fighter{fighter_num}_stance"]

    opponent_reach = fight[f"fighter{opponent_num}_reach"]
    opponent_height = fight[f"fighter{opponent_num}_height"]
    opponent_total_fights = fight[f"fighter{opponent_num}_total_fights"]

    reach_diff = None
    if fighter_reach and opponent_reach:
        reach_diff = fighter_reach - opponent_reach

    height_diff = None
    if fighter_height and opponent_height:
        height_diff = fighter_height - opponent_height

    exp_diff = fighter_total_fights - opponent_total_fights

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
                            "width": "110px",
                            "height": "70px",
                            "objectFit": "cover",
                            "borderRadius": "4px",
                        },
                    ),
                    html.Div(
                        [
                            dmc.Text(fighter_name, fw=700, size="xl"),
                            dmc.Text(fighter_record, size="md", c="gray"),
                        ]
                    ),
                ],
                gap="md",
            ),
            dmc.Divider(my="md"),
            dmc.SimpleGrid(
                [
                    html.Div(
                        [
                            dmc.Text("Reach", size="xs", c="gray"),
                            dmc.Text(
                                f'{fighter_reach or "-"}"',
                                size="sm",
                                fw=500,
                            ),
                            dmc.Text(
                                format_diff(reach_diff, '"'),
                                size="xs",
                                c="teal"
                                if reach_diff and reach_diff > 0
                                else "salmon"
                                if reach_diff and reach_diff < 0
                                else "gray",
                            ),
                        ]
                    ),
                    html.Div(
                        [
                            dmc.Text("Height", size="xs", c="gray"),
                            dmc.Text(
                                f'{fighter_height or "-"}"',
                                size="sm",
                                fw=500,
                            ),
                            dmc.Text(
                                format_diff(height_diff, '"'),
                                size="xs",
                                c="teal"
                                if height_diff and height_diff > 0
                                else "salmon"
                                if height_diff and height_diff < 0
                                else "gray",
                            ),
                        ]
                    ),
                    html.Div(
                        [
                            dmc.Text("Stance", size="xs", c="gray"),
                            dmc.Text(fighter_stance or "-", size="sm", fw=500),
                        ]
                    ),
                    html.Div(
                        [
                            dmc.Text("UFC Fights", size="xs", c="gray"),
                            dmc.Text(str(fighter_total_fights), size="sm", fw=500),
                            dmc.Text(
                                format_diff(exp_diff),
                                size="xs",
                                c="teal" if exp_diff > 0 else "salmon" if exp_diff < 0 else "gray",
                            ),
                        ]
                    ),
                ],
                cols=4,
            ),
            dmc.Button(
                f"View {fighter_name.split()[-1]} Profile",
                id={"type": "view-fighter-btn", "index": fighter_name},
                variant="default",
                size="xs",
                fullWidth=True,
                mt="md",
            ),
        ],
        shadow="sm",
        withBorder=True,
        p="lg",
        style={"minWidth": "320px", "flex": "1"},
    )


def create_matchup_row(fight: dict) -> html.Div:
    fighter1_card = create_matchup_card(fight, 1, 2)
    fighter2_card = create_matchup_card(fight, 2, 1)

    division = fight.get("fight_division") or "Unknown"
    division_display = division.replace("_", " ").title() if division else "TBD"
    fight_type = fight.get("fight_type") or ""

    badges = [
        dmc.Badge(
            division_display,
            color="gray",
            variant="light",
            size="lg",
        )
    ]

    if fight_type and "title" in fight_type.lower():
        badges.append(
            dmc.Badge(
                "Title Fight",
                color="dark",
                variant="outline",
                size="sm",
            )
        )

    return dmc.Paper(
        [
            dmc.Group(badges, gap="xs", mb="md"),
            dmc.Group(
                [
                    fighter1_card,
                    html.Div(
                        [
                            dmc.Text("VS", fw=700, size="xl", c="gray"),
                        ],
                        style={"textAlign": "center", "minWidth": "50px"},
                    ),
                    fighter2_card,
                ],
                align="stretch",
                justify="center",
                gap="md",
                wrap="wrap",
            ),
        ],
        shadow="xs",
        p="lg",
        radius="md",
        withBorder=True,
        style={"marginBottom": "1rem"},
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
                                        dmc.Title(event_title, order=2),
                                        dmc.Group(
                                            [
                                                dmc.Text(event_date_str, size="sm", fw=500),
                                                dmc.Text("-", size="sm", c="gray"),
                                                dmc.Text(event_location, size="sm", c="gray"),
                                            ],
                                            gap="xs",
                                        ),
                                    ]
                                ),
                                dmc.Badge(
                                    f"{len(fights_list)} {'fight' if len(fights_list) == 1 else 'fights'}",
                                    color="gray",
                                    variant="light",
                                    size="lg",
                                ),
                            ],
                            justify="space-between",
                            align="flex-start",
                        ),
                    ],
                    p="lg",
                    mb="lg",
                    withBorder=True,
                    radius="md",
                    shadow="sm",
                ),
                html.Div(matchup_rows),
            ],
            style={"marginBottom": "2.5rem"},
        )
        event_sections.append(event_section)

    return html.Div(
        [
            dmc.Text(
                "Upcoming UFC events with scheduled matchups. View fighter profiles for detailed analysis.",
                c="gray",
                size="sm",
                mb="lg",
            ),
            html.Div(event_sections),
        ]
    )
