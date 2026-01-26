from pathlib import Path

import dash_mantine_components as dmc
import pandas as pd
from dash import Dash, html

from panoctagon.common import get_engine
from panoctagon.dashboard.pages.fighter import fighter_analysis_content
from panoctagon.dashboard.pages.network import (
    fighter_network_content,
)
from panoctagon.dashboard.pages.roster import (
    roster_analysis_content,
)
from panoctagon.dashboard.pages.upcoming import create_upcoming_fights_content


def get_last_refresh() -> str:
    return (
        pd.read_sql_query(
            "select max(event_date::DATE) AS event_date FROM ufc_events", get_engine()
        )["event_date"]
        .iloc[0]
        .strftime("%Y-%m-%d")
    )


assets_path = Path(__file__).parent / "assets"
app = Dash(__name__, assets_folder=str(assets_path))
server = app.server

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
                                f"Data current as of {get_last_refresh()}",
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


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8050)
