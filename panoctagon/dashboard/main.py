from pathlib import Path

import dash_mantine_components as dmc
import pandas as pd
from dash import Dash, Input, Output, callback, dcc, html

from panoctagon.common import get_read_engine, ttl_cache
from panoctagon.dashboard.pages.fighter import fighter_analysis_content
from panoctagon.dashboard.pages.network import (
    fighter_network_content,
)
from panoctagon.dashboard.pages.roster import (
    roster_analysis_content,
)
from panoctagon.dashboard.pages.upcoming import create_upcoming_fights_content


@ttl_cache(seconds=120)
def get_last_refresh() -> str:
    return (
        pd.read_sql_query(
            "select max(downloaded_ts::DATE) AS downloaded FROM ufc_events", get_read_engine()
        )["downloaded"]
        .iloc[0]
        .strftime("%Y-%m-%d")
    )


assets_path = Path(__file__).parents[1] / "assets"
app = Dash(__name__, assets_folder=str(assets_path))
server = app.server

app.layout = dmc.MantineProvider(
    html.Div(
        id="panoctagon-page",
        children=dmc.AppShell(
            [
                dcc.Interval(
                    id="data-refresh-interval", interval=1000, max_intervals=1, n_intervals=0
                ),
                dmc.AppShellHeader(
                    dmc.Group(
                        [
                            html.A(
                                dmc.Title("panoctagon", c="#1a1a1a", size="h2"),
                                id="title-link",
                                style={"textDecoration": "none", "cursor": "pointer"},
                            ),
                            dmc.Badge(
                                id="last-refresh-badge",
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
                                        dmc.TabsTab("Upcoming", value="upcoming"),
                                        dmc.TabsTab("Fighters", value="analysis"),
                                        dmc.TabsTab("Network", value="network"),
                                        dmc.TabsTab("Roster", value="roster"),
                                    ]
                                ),
                                dmc.TabsPanel(
                                    html.Div(id="upcoming-fights-container"),
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


@callback(
    Output("top-level-tabs", "value", allow_duplicate=True),
    Input("title-link", "n_clicks"),
    prevent_initial_call=True,
)
def reset_to_upcoming(_: int | None) -> str:
    return "upcoming"


@callback(
    Output("last-refresh-badge", "children"),
    Output("upcoming-fights-container", "children"),
    Input("data-refresh-interval", "n_intervals"),
)
def refresh_dashboard_data(_: int) -> tuple[str, html.Div]:
    return f"Data current as of {get_last_refresh()}", create_upcoming_fights_content()


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8050)
