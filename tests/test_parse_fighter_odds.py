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


def test_future_events_included():
    matchups = parse_matchups_from_fighter_html(FUTURE_EVENTS_HTML)
    assert len(matchups) == 1
    assert matchups[0] == BFOMatchup(
        match_id=99999, fighter1_name="Fighter A", fighter2_name="Fighter B"
    )


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


def test_full_page():
    html = """
    <!DOCTYPE html>
    <html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en">
    <body>
    <div id="page-wrapper" style="max-width: 800px;"><div id="page-container"><div class="content-header team-stats-header"><h1 id="team-name">Ilia Topuria</h1></div><div id="page-inner-wrapper"><div id="page-content"><div id="team-stats-container" style="display: inline-block"><table class="team-stats-table" cellspacing="0" summary="Odds history for Ilia Topuria"><thead><tr><th>Matchup</th><th style="text-align: right; padding-right: 4px;">Open</th><th style="text-align: center; width: 110px;" colspan="3">Closing range</th><th class="header-movement">Movement</th><th></th><th class="item-non-mobile" style="padding-left: 20px">Event</th></tr></thead><tbody><tr class="event-header item-mobile-only-row"><td colspan="8" scope="row"><a href="/events/future-events-197">Future Events</a></td></tr><tr class="main-row"><th class="oppcell"><a href="/fighters/Ilia-Topuria-8322">Ilia Topuria</a></td><td class="moneyline" style="padding-right: 4px;"><span id="oID0">-500</span></td><td class="moneyline"><span id="oID1">-600</span></td><td class="dash-cell">...</td><td class="moneyline" style="text-align: left; padding-left: 0; padding-right: 7px;"><span id="oID2">-600</span></td><td class="chart-cell" data-sparkline="1.2, 1.16667" data-li="[41453,1]" rowspan="2"></td><td rowspan="2" class="change-cell"><span class="teamPercChange" data-li="[41453,1]">
                                                        -2.9%<span style="color: #E93524;position:relative; margin-left: 0">▼</span></span></td><td class="item-non-mobile" scope="row" style="padding-left: 20px"><a href="/events/future-events-197" >Future Events</a></td></tr><tr><th class="oppcell"><a href="/fighters/Justin-Gaethje-3964">Justin Gaethje</a></td><td class="moneyline" style="padding-right: 4px;"><span id="oID3">+385</span></td><td class="moneyline"><span id="oID4">+400</span></td><td class="dash-cell">...</td><td class="moneyline" style="text-align: left; padding-left: 0"><span id="oID5">+400</span></td><td class="item-non-mobile" style="padding-left: 20px; color: #767676"></td></tr><tr class="event-header item-mobile-only-row"><td colspan="8" scope="row"><a href="/events/future-events-197">Future Events</a></td></tr><tr class="main-row"><th class="oppcell"><a href="/fighters/Ilia-Topuria-8322">Ilia Topuria</a></td><td class="moneyline" style="padding-right: 4px;"><span id="oID6">-200</span></td><td class="moneyline"><span id="oID7">-190</span></td><td class="dash-cell">...</td><td class="moneyline" style="text-align: left; padding-left: 0; padding-right: 7px;"><span id="oID8">-190</span></td><td class="chart-cell" data-sparkline="1.5, 1.54054, 1.52632" data-li="[39265,2]" rowspan="2"></td><td rowspan="2" class="change-cell"><span class="teamPercChange" data-li="[39265,2]">
                                                        +1.7%<span style="color: #4BCA02;position:relative; margin-left: 0">▲</span></span></td><td class="item-non-mobile" scope="row" style="padding-left: 20px"><a href="/events/future-events-197" >Future Events</a></td></tr><tr><th class="oppcell"><a href="/fighters/Arman-Tsarukyan-9034">Arman Tsarukyan</a></td><td class="moneyline" style="padding-right: 4px;"><span id="oID9">+170</span></td><td class="moneyline"><span id="oID10">+165</span></td><td class="dash-cell">...</td><td class="moneyline" style="text-align: left; padding-left: 0"><span id="oID11">+165</span></td><td class="item-non-mobile" style="padding-left: 20px; color: #767676"></td></tr><tr class="event-header item-mobile-only-row"><td colspan="8" scope="row"><a href="/events/future-events-197">Future Events</a></td></tr><tr class="main-row"><th class="oppcell"><a href="/fighters/Ilia-Topuria-8322">Ilia Topuria</a></td><td class="moneyline" style="padding-right: 4px;"><span id="oID12">+170</span></td><td class="moneyline"><span id="oID13">+199</span></td><td class="dash-cell">...</td><td class="moneyline" style="text-align: left; padding-left: 0; padding-right: 7px;"><span id="oID14">+199</span></td><td class="chart-cell" data-sparkline="2.7, 2.99" data-li="[39258,1]" rowspan="2"></td><td rowspan="2" class="change-cell"><span class="teamPercChange" data-li="[39258,1]">
                                                        +9.7%<span style="color: #4BCA02;position:relative; margin-left: 0">▲</span></span></td><td class="item-non-mobile" scope="row" style="padding-left: 20px"><a href="/events/future-events-197" >Future Events</a></td></tr><tr><th class="oppcell"><a href="/fighters/Islam-Makhachev-5541">Islam Makhachev</a></td><td class="moneyline" style="padding-right: 4px;"><span id="oID15">-200</span></td><td class="moneyline"><span id="oID16">-234</span></td><td class="dash-cell">...</td><td class="moneyline" style="text-align: left; padding-left: 0"><span id="oID17">-234</span></td><td class="item-non-mobile" style="padding-left: 20px; color: #767676"></td></tr><tr class="event-header item-mobile-only-row"><td colspan="8" scope="row"><a href="/events/future-events-197">Future Events</a></td></tr><tr class="main-row"><th class="oppcell"><a href="/fighters/Ilia-Topuria-8322">Ilia Topuria</a></td><td class="moneyline" style="padding-right: 4px;"><span id="oID18">-150</span></td><td class="moneyline"><span id="oID19">-175</span></td><td class="dash-cell">...</td><td class="moneyline" style="text-align: left; padding-left: 0; padding-right: 7px;"><span id="oID20">-155</span></td><td class="chart-cell" data-sparkline="1.66667, 1.45455, 1.5, 1.58824, 1.625, 1.63314, 1.61019, 1.6095514285714, 1.6319571428571, 1.61731" data-li="[28832,2]" rowspan="2"></td><td rowspan="2" class="change-cell"><span class="teamPercChange" data-li="[28832,2]">
                                                        -3.1%<span style="color: #E93524;position:relative; margin-left: 0">▼</span></span></td><td class="item-non-mobile" scope="row" style="padding-left: 20px"><a href="/events/future-events-197" >Future Events</a></td></tr><tr><th class="oppcell"><a href="/fighters/Bryce-Mitchell-6135">Bryce Mitchell</a></td><td class="moneyline" style="padding-right: 4px;"><span id="oID21">+130</span></td><td class="moneyline"><span id="oID22">+130</span></td><td class="dash-cell">...</td><td class="moneyline" style="text-align: left; padding-left: 0"><span id="oID23">+150</span></td><td class="item-non-mobile" style="padding-left: 20px; color: #767676"></td></tr><tr class="event-header item-mobile-only-row"><td colspan="8" scope="row"><a href="/events/unconfirmed-fights-3781">Unconfirmed Fights</a> Dec 31st 2025</td></tr><tr class="main-row"><th class="oppcell"><a href="/fighters/Ilia-Topuria-8322">Ilia Topuria</a></td><td class="moneyline" style="padding-right: 4px;"><span id="oID24">-770</span></td><td class="moneyline"><span id="oID25">-770</span></td><td class="dash-cell">...</td><td class="moneyline" style="text-align: left; padding-left: 0; padding-right: 7px;"><span id="oID26">-770</span></td><td class="chart-cell" rowspan="2"></td><td rowspan="2" class="change-cell"></td><td class="item-non-mobile" scope="row" style="padding-left: 20px"><a href="/events/unconfirmed-fights-3781" >Unconfirmed Fights</a></td></tr><tr><th class="oppcell"><a href="/fighters/Paddy-Pimblett-4242">Paddy Pimblett</a></td><td class="moneyline" style="padding-right: 4px;"><span id="oID27">+510</span></td><td class="moneyline"><span id="oID28">+510</span></td><td class="dash-cell">...</td><td class="moneyline" style="text-align: left; padding-left: 0"><span id="oID29">+510</span></td><td class="item-non-mobile" style="padding-left: 20px; color: #767676">Dec 31st 2025</td></tr><tr class="event-header item-mobile-only-row"><td colspan="8" scope="row"><a href="/events/unconfirmed-fights-3781">Unconfirmed Fights</a> Dec 31st 2025</td></tr><tr class="main-row"><th class="oppcell"><a href="/fighters/Ilia-Topuria-8322">Ilia Topuria</a></td><td class="moneyline" style="padding-right: 4px;"><span id="oID30">-560</span></td><td class="moneyline"><span id="oID31">-560</span></td><td class="dash-cell">...</td><td class="moneyline" style="text-align: left; padding-left: 0; padding-right: 7px;"><span id="oID32">-560</span></td><td class="chart-cell" rowspan="2"></td><td rowspan="2" class="change-cell"></td><td class="item-non-mobile" scope="row" style="padding-left: 20px"><a href="/events/unconfirmed-fights-3781" >Unconfirmed Fights</a></td></tr><tr><th class="oppcell"><a href="/fighters/Alexander-Volkanovski-9523">Alexander Volkanovski</a></td><td class="moneyline" style="padding-right: 4px;"><span id="oID33">+390</span></td><td class="moneyline"><span id="oID34">+390</span></td><td class="dash-cell">...</td><td class="moneyline" style="text-align: left; padding-left: 0"><span id="oID35">+390</span></td><td class="item-non-mobile" style="padding-left: 20px; color: #767676">Dec 31st 2025</td></tr><tr class="event-header item-mobile-only-row"><td colspan="8" scope="row"><a href="/events/ufc-3725">UFC</a> Jun 29th 2025</td></tr><tr class="main-row"><th class="oppcell"><a href="/fighters/Ilia-Topuria-8322">Ilia Topuria</a></td><td class="moneyline" style="padding-right: 4px;"><span id="oID36">-295</span></td><td class="moneyline"><span id="oID37">-425</span></td><td class="dash-cell">...</td><td class="moneyline" style="text-align: left; padding-left: 0; padding-right: 7px;"><span id="oID38">-400</span></td><td class="chart-cell" data-sparkline="1.33898, 1.263938, 1.261522, 1.258598, 1.255966, 1.250252, 1.228182, 1.229238, 1.228936, 1.24644" data-li="[38712,2]" rowspan="2"></td><td rowspan="2" class="change-cell"><span class="teamPercChange" data-li="[38712,2]">
                                                        -7.4%<span style="color: #E93524;position:relative; margin-left: 0">▼</span></span></td><td class="item-non-mobile" scope="row" style="padding-left: 20px"><a href="/events/ufc-3725" >UFC</a></td></tr><tr><th class="oppcell"><a href="/fighters/Charles-Oliveira-1893">Charles Oliveira</a></td><td class="moneyline" style="padding-right: 4px;"><span id="oID39">+220</span></td><td class="moneyline"><span id="oID40">+295</span></td><td class="dash-cell">...</td><td class="moneyline" style="text-align: left; padding-left: 0"><span id="oID41">+330</span></td><td class="item-non-mobile" style="padding-left: 20px; color: #767676">Jun 29th 2025</td></tr><tr class="event-header item-mobile-only-row"><td colspan="8" scope="row"><a href="/events/ufc-3412">UFC</a> Oct 26th 2024</td></tr><tr class="main-row"><th class="oppcell"><a href="/fighters/Ilia-Topuria-8322">Ilia Topuria</a></td><td class="moneyline" style="padding-right: 4px;"><span id="oID42">-188</span></td><td class="moneyline"><span id="oID43">-305</span></td><td class="dash-cell">...</td><td class="moneyline" style="text-align: left; padding-left: 0; padding-right: 7px;"><span id="oID44">-265</span></td><td class="chart-cell" data-sparkline="1.53191, 1.5027875, 1.4994125, 1.4931575, 1.481494, 1.479472, 1.4424866666667, 1.4306616666667, 1.37777, 1.35683" data-li="[35946,1]" rowspan="2"></td><td rowspan="2" class="change-cell"><span class="teamPercChange" data-li="[35946,1]">
                                                        -13%<span style="color: #E93524;position:relative; margin-left: 0">▼</span></span></td><td class="item-non-mobile" scope="row" style="padding-left: 20px"><a href="/events/ufc-3412" >UFC</a></td></tr><tr><th class="oppcell"><a href="/fighters/Max-Holloway-3090">Max Holloway</a></td><td class="moneyline" style="padding-right: 4px;"><span id="oID45">+146</span></td><td class="moneyline"><span id="oID46">+210</span></td><td class="dash-cell">...</td><td class="moneyline" style="text-align: left; padding-left: 0"><span id="oID47">+245</span></td><td class="item-non-mobile" style="padding-left: 20px; color: #767676">Oct 26th 2024</td></tr><tr class="event-header item-mobile-only-row"><td colspan="8" scope="row"><a href="/events/ufc-fight-night-228-2848">UFC Fight Night 228</a> Jun 24th 2023</td></tr><tr class="main-row"><th class="oppcell"><a href="/fighters/Ilia-Topuria-8322">Ilia Topuria</a></td><td class="moneyline" style="padding-right: 4px;"><span id="oID48">-200</span></td><td class="moneyline"><span id="oID49">-400</span></td><td class="dash-cell">...</td><td class="moneyline" style="text-align: left; padding-left: 0; padding-right: 7px;"><span id="oID50">-300</span></td><td class="chart-cell" data-sparkline="1.5, 1.38462, 1.33333, 1.313725, 1.32026, 1.31527, 1.312276, 1.306216, 1.30518875, 1.27587875" data-li="[30780,1]" rowspan="2"></td><td rowspan="2" class="change-cell"><span class="teamPercChange" data-li="[30780,1]">
                                                        -17.7%<span style="color: #E93524;position:relative; margin-left: 0">▼</span></span></td><td class="item-non-mobile" scope="row" style="padding-left: 20px"><a href="/events/ufc-fight-night-228-2848" >UFC Fight Night 228</a></td></tr><tr><th class="oppcell"><a href="/fighters/Josh-Emmett-6405">Josh Emmett</a></td><td class="moneyline" style="padding-right: 4px;"><span id="oID51">+170</span></td><td class="moneyline"><span id="oID52">+250</span></td><td class="dash-cell">...</td><td class="moneyline" style="text-align: left; padding-left: 0"><span id="oID53">+310</span></td><td class="item-non-mobile" style="padding-left: 20px; color: #767676">Jun 24th 2023</td></tr><tr class="event-header item-mobile-only-row"><td colspan="8" scope="row"><a href="/events/ufc-fight-night-205-2376">UFC Fight Night 205</a> Mar 19th 2022</td></tr><tr class="main-row"><th class="oppcell"><a href="/fighters/Ilia-Topuria-8322">Ilia Topuria</a></td><td class="moneyline" style="padding-right: 4px;"><span id="oID54">-500</span></td><td class="moneyline"><span id="oID55">-650</span></td><td class="dash-cell">...</td><td class="moneyline" style="text-align: left; padding-left: 0; padding-right: 7px;"><span id="oID56">-560</span></td><td class="chart-cell" data-sparkline="1.2, 1.2594733333333, 1.2615442857143, 1.2547933333333, 1.2565627272727, 1.2551481818182, 1.2494909090909, 1.23352, 1.1787054545455, 1.1630163636364" data-li="[26133,1]" rowspan="2"></td><td rowspan="2" class="change-cell"><span class="teamPercChange" data-li="[26133,1]">
                                                        -3.2%<span style="color: #E93524;position:relative; margin-left: 0">▼</span></span></td><td class="item-non-mobile" scope="row" style="padding-left: 20px"><a href="/events/ufc-fight-night-205-2376" >UFC Fight Night 205</a></td></tr><tr><th class="oppcell"><a href="/fighters/Jai-Herbert-6873">Jai Herbert</a></td><td class="moneyline" style="padding-right: 4px;"><span id="oID57">+375</span></td><td class="moneyline"><span id="oID58">+400</span></td><td class="dash-cell">...</td><td class="moneyline" style="text-align: left; padding-left: 0"><span id="oID59">+450</span></td><td class="item-non-mobile" style="padding-left: 20px; color: #767676">Mar 19th 2022</td></tr><tr class="event-header item-mobile-only-row"><td colspan="8" scope="row"><a href="/events/ufc-270-2322">UFC 270</a> Jan 22nd 2022</td></tr><tr class="main-row"><th class="oppcell"><a href="/fighters/Ilia-Topuria-8322">Ilia Topuria</a></td><td class="moneyline" style="padding-right: 4px;"><span id="oID60">-120</span></td><td class="moneyline"><span id="oID61">-135</span></td><td class="dash-cell">...</td><td class="moneyline" style="text-align: left; padding-left: 0; padding-right: 7px;"><span id="oID62">-135</span></td><td class="chart-cell" data-sparkline="1.83333, 1.74074, 1.71429, 1.76923, 1.83333, 1.76923, 1.74074" data-li="[24989,1]" rowspan="2"></td><td rowspan="2" class="change-cell"><span class="teamPercChange" data-li="[24989,1]">
                                                        -5.3%<span style="color: #E93524;position:relative; margin-left: 0">▼</span></span></td><td class="item-non-mobile" scope="row" style="padding-left: 20px"><a href="/events/ufc-270-2322" >UFC 270</a></td></tr><tr><th class="oppcell"><a href="/fighters/Movsar-Evloev-8457">Movsar Evloev</a></td><td class="moneyline" style="padding-right: 4px;"><span id="oID63">+100</span></td><td class="moneyline"><span id="oID64">+110</span></td><td class="dash-cell">...</td><td class="moneyline" style="text-align: left; padding-left: 0"><span id="oID65">+110</span></td><td class="item-non-mobile" style="padding-left: 20px; color: #767676">Jan 22nd 2022</td></tr><tr class="event-header item-mobile-only-row"><td colspan="8" scope="row"><a href="/events/ufc-264-poirier-vs-mcgregor-3-2127">UFC 264: Poirier vs. McGregor 3</a> Jul 10th 2021</td></tr><tr class="main-row"><th class="oppcell"><a href="/fighters/Ilia-Topuria-8322">Ilia Topuria</a></td><td class="moneyline" style="padding-right: 4px;"><span id="oID66">-220</span></td><td class="moneyline"><span id="oID67">-235</span></td><td class="dash-cell">...</td><td class="moneyline" style="text-align: left; padding-left: 0; padding-right: 7px;"><span id="oID68">-209</span></td><td class="chart-cell" data-sparkline="1.45455, 1.3917416666667, 1.3985371428571, 1.4171545454545, 1.4194754545455, 1.4179281818182, 1.4174172727273, 1.4198490909091, 1.40182, 1.44539" data-li="[22630,1]" rowspan="2"></td><td rowspan="2" class="change-cell"><span class="teamPercChange" data-li="[22630,1]">
                                                        -0.7%<span style="color: #E93524;position:relative; margin-left: 0">▼</span></span></td><td class="item-non-mobile" scope="row" style="padding-left: 20px"><a href="/events/ufc-264-poirier-vs-mcgregor-3-2127" >UFC 264: Poirier vs. McGregor 3</a></td></tr><tr><th class="oppcell"><a href="/fighters/Ryan-Hall-6089">Ryan Hall</a></td><td class="moneyline" style="padding-right: 4px;"><span id="oID69">+185</span></td><td class="moneyline"><span id="oID70">+155</span></td><td class="dash-cell">...</td><td class="moneyline" style="text-align: left; padding-left: 0"><span id="oID71">+185</span></td><td class="item-non-mobile" style="padding-left: 20px; color: #767676">Jul 10th 2021</td></tr><tr class="event-header item-mobile-only-row"><td colspan="8" scope="row"><a href="/events/ufc-on-espn-19-hermansson-vs-vettori-1982">UFC on ESPN 19: Hermansson vs. Vettori</a> Dec 5th 2020</td></tr><tr class="main-row"><th class="oppcell"><a href="/fighters/Ilia-Topuria-8322">Ilia Topuria</a></td><td class="moneyline" style="padding-right: 4px;"><span id="oID72">-170</span></td><td class="moneyline"><span id="oID73">-333</span></td><td class="dash-cell">...</td><td class="moneyline" style="text-align: left; padding-left: 0; padding-right: 7px;"><span id="oID74">-230</span></td><td class="chart-cell" data-sparkline="1.58824, 1.449495, 1.4498133333333, 1.4465933333333, 1.44582, 1.4713066666667, 1.46724, 1.4140666666667, 1.4055566666667, 1.38108" data-li="[21379,2]" rowspan="2"></td><td rowspan="2" class="change-cell"><span class="teamPercChange" data-li="[21379,2]">
                                                        -15.8%<span style="color: #E93524;position:relative; margin-left: 0">▼</span></span></td><td class="item-non-mobile" scope="row" style="padding-left: 20px"><a href="/events/ufc-on-espn-19-hermansson-vs-vettori-1982" >UFC on ESPN 19: Hermansson vs. Vettori</a></td></tr><tr><th class="oppcell"><a href="/fighters/Damon-Jackson-3828">Damon Jackson</a></td><td class="moneyline" style="padding-right: 4px;"><span id="oID75">+145</span></td><td class="moneyline"><span id="oID76">+195</span></td><td class="dash-cell">...</td><td class="moneyline" style="text-align: left; padding-left: 0"><span id="oID77">+250</span></td><td class="item-non-mobile" style="padding-left: 20px; color: #767676">Dec 5th 2020</td></tr><tr class="event-header item-mobile-only-row"><td colspan="8" scope="row"><a href="/events/ufc-on-espn-37-moraes-vs-sandhagen-1965">UFC on ESPN+ 37: Moraes vs. Sandhagen</a> Oct 10th 2020</td></tr><tr class="main-row"><th class="oppcell"><a href="/fighters/Ilia-Topuria-8322">Ilia Topuria</a></td><td class="moneyline" style="padding-right: 4px;"><span id="oID78">+190</span></td><td class="moneyline"><span id="oID79">+110</span></td><td class="dash-cell">...</td><td class="moneyline" style="text-align: left; padding-left: 0; padding-right: 7px;"><span id="oID80">+135</span></td><td class="chart-cell" data-sparkline="2.9, 2.45, 2.5266666666667, 2.5233333333333, 2.5666666666667, 2.59, 2.6, 2.4166666666667, 2.3733333333333, 2.25" data-li="[21153,1]" rowspan="2"></td><td rowspan="2" class="change-cell"><span class="teamPercChange" data-li="[21153,1]">
                                                        -28.9%<span style="color: #E93524;position:relative; margin-left: 0">▼</span></span></td><td class="item-non-mobile" scope="row" style="padding-left: 20px"><a href="/events/ufc-on-espn-37-moraes-vs-sandhagen-1965" >UFC on ESPN+ 37: Moraes vs. Sandhagen</a></td></tr><tr><th class="oppcell"><a href="/fighters/Youssef-Zalal-8823">Youssef Zalal</a></td><td class="moneyline" style="padding-right: 4px;"><span id="oID81">-270</span></td><td class="moneyline"><span id="oID82">-155</span></td><td class="dash-cell">...</td><td class="moneyline" style="text-align: left; padding-left: 0"><span id="oID83">-139</span></td><td class="item-non-mobile" style="padding-left: 20px; color: #767676">Oct 10th 2020</td></tr><tr class="event-header item-mobile-only-row"><td colspan="8" scope="row"><a href="/events/cage-warriors-94-bouland-vs-topuria-1510">Cage Warriors 94: Bouland vs. Topuria</a> Jun 16th 2018</td></tr><tr class="main-row"><th class="oppcell"><a href="/fighters/Ilia-Topuria-8322">Ilia Topuria</a></td><td class="moneyline" style="padding-right: 4px;"><span id="oID84">+100</span></td><td class="moneyline"><span id="oID85">+135</span></td><td class="dash-cell">...</td><td class="moneyline" style="text-align: left; padding-left: 0; padding-right: 7px;"><span id="oID86">+135</span></td><td class="chart-cell" data-sparkline="2, 2.2, 2.35, 2.65, 2.27, 2.75, 2.45, 2.7, 2.55, 2.35" data-li="[16180,2]" rowspan="2"></td><td rowspan="2" class="change-cell"><span class="teamPercChange" data-li="[16180,2]">
                                                        +14.9%<span style="color: #4BCA02;position:relative; margin-left: 0">▲</span></span></td><td class="item-non-mobile" scope="row" style="padding-left: 20px"><a href="/events/cage-warriors-94-bouland-vs-topuria-1510" >Cage Warriors 94: Bouland vs. Topuria</a></td></tr><tr><th class="oppcell"><a href="/fighters/Brian-Bouland-7838">Brian Bouland</a></td><td class="moneyline" style="padding-right: 4px;"><span id="oID87">-140</span></td><td class="moneyline"><span id="oID88">-175</span></td><td class="dash-cell">...</td><td class="moneyline" style="text-align: left; padding-left: 0"><span id="oID89">-175</span></td><td class="item-non-mobile" style="padding-left: 20px; color: #767676">Jun 16th 2018</td></tr></tbody></table></div></div></div></div></div><div id="page-bottom"></div>        </div>
        </div>
    </body>

    </html>
    """
    matchups = parse_matchups_from_fighter_html(html)
    for matchup in matchups:
        print(matchup)

    assert len(matchups) == 13
