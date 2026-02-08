from panoctagon.ufc.scrape.bets import BFOMatchup, parse_matchups_from_fighter_html


FIGHTER_HTML = """
<table class="team-stats-table">
<tbody>
<tr class="event-header item-mobile-only-row">
  <td colspan="8"><a href="/events/ufc-300-pereira-vs-hill-2856">UFC 300</a> Apr 13th 2024</td>
</tr>
<tr class="main-row">
  <th class="oppcell"><a href="/fighters/Fighter-A-100">Fighter A</a></th>
  <td class="chart-cell" data-li="[12345,1]" rowspan="2"></td>
</tr>
<tr>
  <th class="oppcell"><a href="/fighters/Fighter-B-200">Fighter B</a></th>
</tr>
<tr class="event-header item-mobile-only-row">
  <td colspan="8"><a href="/events/ufc-299-omalley-vs-vera-2800">UFC 299</a> Mar 9th 2024</td>
</tr>
<tr class="main-row">
  <th class="oppcell"><a href="/fighters/Fighter-A-100">Fighter A</a></th>
  <td class="chart-cell" data-li="[67890,1]" rowspan="2"></td>
</tr>
<tr>
  <th class="oppcell"><a href="/fighters/Fighter-C-300">Fighter C</a></th>
</tr>
</tbody>
</table>
"""


def test_parse_matchups_from_fighter_html():
    matchups = parse_matchups_from_fighter_html(FIGHTER_HTML)
    assert len(matchups) == 2
    assert matchups[0] == BFOMatchup(
        match_id=12345, fighter1_name="Fighter A", fighter2_name="Fighter B"
    )
    assert matchups[1] == BFOMatchup(
        match_id=67890, fighter1_name="Fighter A", fighter2_name="Fighter C"
    )


FUTURE_EVENTS_HTML = """
<table class="team-stats-table">
<tbody>
<tr class="event-header item-mobile-only-row">
  <td colspan="8"><a href="/events/future-events">Future Events</a></td>
</tr>
<tr class="main-row">
  <th class="oppcell"><a href="/fighters/Fighter-A-100">Fighter A</a></th>
  <td class="chart-cell" data-li="[99999,1]" rowspan="2"></td>
</tr>
<tr>
  <th class="oppcell"><a href="/fighters/Fighter-B-200">Fighter B</a></th>
</tr>
</tbody>
</table>
"""


def test_future_events_skipped():
    matchups = parse_matchups_from_fighter_html(FUTURE_EVENTS_HTML)
    assert len(matchups) == 0


NO_DATA_LI_HTML = """
<table class="team-stats-table">
<tbody>
<tr class="main-row">
  <th class="oppcell"><a href="/fighters/Fighter-A-100">Fighter A</a></th>
  <td class="chart-cell" rowspan="2"></td>
</tr>
<tr>
  <th class="oppcell"><a href="/fighters/Fighter-B-200">Fighter B</a></th>
</tr>
</tbody>
</table>
"""


def test_rows_without_data_li_skipped():
    matchups = parse_matchups_from_fighter_html(NO_DATA_LI_HTML)
    assert len(matchups) == 0


def test_real_fighter_page():
    """Test against the actual A.J. Cunningham fighter page HTML structure."""
    html = """
<table class="team-stats-table" cellspacing="0">
<thead><tr><th>Matchup</th></tr></thead>
<tbody>
<tr class="event-header item-mobile-only-row">
  <td colspan="8" scope="row"><a href="/events/lfa-102-johns-vs-souza-2114">LFA 102: Johns vs. Souza</a> Mar 19th 2021</td>
</tr>
<tr class="main-row">
  <th class="oppcell"><a href="/fighters/A-J-Cunningham-10916">A.J. Cunningham</a></th>
  <td class="moneyline"><span>-500</span></td>
  <td class="chart-cell" data-sparkline="1.2, 1.28" data-li="[22240,1]" rowspan="2"></td>
</tr>
<tr>
  <th class="oppcell"><a href="/fighters/Javier-Garcia-10917">Javier Garcia</a></th>
  <td class="moneyline"><span>+375</span></td>
</tr>
</tbody>
</table>
"""
    matchups = parse_matchups_from_fighter_html(html)
    assert len(matchups) == 1
    assert matchups[0] == BFOMatchup(
        match_id=22240,
        fighter1_name="A.J. Cunningham",
        fighter2_name="Javier Garcia",
    )
