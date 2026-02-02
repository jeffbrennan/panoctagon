from __future__ import annotations

from typing import Optional

from fastapi import FastAPI, HTTPException, Query

from panoctagon.api.models import (
    EventSummary,
    FightDetail,
    FightFighterStats,
    FightRoundStats,
    FighterBio,
    FighterDetail,
    FighterRecord,
    FighterSearchResult,
    FightSummary,
    RankedFighter,
    RosterFighter,
    UpcomingEvent,
    UpcomingMatchup,
)
from panoctagon.api.queries import (
    get_events,
    get_fight_detail,
    get_fighter_detail,
    get_rankings,
    get_roster,
    get_upcoming_fights,
    search_fighters,
)

app = FastAPI(
    title="Panoctagon API",
    description="UFC fight data API",
    version="0.1.0",
)


@app.get("/fighter", response_model=list[FighterSearchResult])
def list_fighters(
    name: Optional[str] = Query(None, description="Search fighters by name (substring match)"),
    division: Optional[str] = Query(None, description="Filter by weight class"),
    limit: int = Query(50, ge=1, le=200, description="Maximum results to return"),
) -> list[FighterSearchResult]:
    df = search_fighters(name=name, division=division, limit=limit)
    return [
        FighterSearchResult(
            fighter_uid=row["fighter_uid"],
            full_name=row["full_name"],
            nickname=row["nickname"],
            stance=row["stance"],
            division=row["division"],
            wins=row["wins"],
            losses=row["losses"],
            draws=row["draws"],
        )
        for row in df.iter_rows(named=True)
    ]


@app.get("/fighter/{fighter_uid}", response_model=FighterDetail)
def get_fighter(fighter_uid: str) -> FighterDetail:
    bio_df, record_df, fights_df = get_fighter_detail(fighter_uid)

    if bio_df is None:
        raise HTTPException(status_code=404, detail=f"Fighter {fighter_uid} not found")

    bio_row = bio_df.row(0, named=True)
    record_row = record_df.row(0, named=True)

    bio = FighterBio(
        fighter_uid=bio_row["fighter_uid"],
        first_name=bio_row["first_name"],
        last_name=bio_row["last_name"],
        full_name=bio_row["full_name"],
        nickname=bio_row["nickname"],
        dob=bio_row["dob"],
        place_of_birth=bio_row["place_of_birth"],
        stance=bio_row["stance"],
        style=bio_row["style"],
        height_inches=bio_row["height_inches"],
        reach_inches=bio_row["reach_inches"],
        leg_reach_inches=bio_row["leg_reach_inches"],
    )

    record = FighterRecord(
        wins=record_row["wins"],
        losses=record_row["losses"],
        draws=record_row["draws"],
        no_contests=record_row["no_contests"],
        total_fights=record_row["total_fights"],
    )

    recent_fights = [
        FightSummary(
            fight_uid=row["fight_uid"],
            event_title=row["event_title"],
            event_date=row["event_date"],
            fight_division=row["fight_division"],
            fight_type=row["fight_type"],
            opponent_name=row["opponent_name"],
            result=row["result"],
            decision=row["decision"],
            decision_round=row["decision_round"],
        )
        for row in fights_df.iter_rows(named=True)
    ]

    return FighterDetail(bio=bio, record=record, recent_fights=recent_fights)


@app.get("/upcoming", response_model=list[UpcomingEvent])
def list_upcoming() -> list[UpcomingEvent]:
    df = get_upcoming_fights()

    if df.height == 0:
        return []

    events: dict[str, UpcomingEvent] = {}

    for row in df.iter_rows(named=True):
        event_uid = row["event_uid"]

        matchup = UpcomingMatchup(
            fight_uid=row["fight_uid"],
            event_uid=row["event_uid"],
            event_title=row["event_title"],
            event_date=row["event_date"],
            event_location=row["event_location"],
            fight_division=row["fight_division"],
            fight_type=row["fight_type"],
            fight_order=row["fight_order"],
            fighter1_uid=row["fighter1_uid"],
            fighter1_name=row["fighter1_name"],
            fighter1_record=row["fighter1_record"],
            fighter1_reach=row["fighter1_reach"],
            fighter1_height=row["fighter1_height"],
            fighter1_stance=row["fighter1_stance"],
            fighter2_uid=row["fighter2_uid"],
            fighter2_name=row["fighter2_name"],
            fighter2_record=row["fighter2_record"],
            fighter2_reach=row["fighter2_reach"],
            fighter2_height=row["fighter2_height"],
            fighter2_stance=row["fighter2_stance"],
        )

        if event_uid not in events:
            events[event_uid] = UpcomingEvent(
                event_uid=event_uid,
                event_title=row["event_title"],
                event_date=row["event_date"],
                event_location=row["event_location"],
                fights=[],
            )

        events[event_uid].fights.append(matchup)

    return list(events.values())


@app.get("/rankings", response_model=list[RankedFighter])
def list_rankings(
    division: Optional[str] = Query(None, description="Filter by weight class"),
    min_fights: int = Query(5, ge=1, description="Minimum UFC fights required"),
    limit: int = Query(15, ge=1, le=50, description="Top N fighters per division"),
) -> list[RankedFighter]:
    df = get_rankings(division=division, min_fights=min_fights, limit=limit)
    return [
        RankedFighter(
            rank=row["rank"],
            fighter_uid=row["fighter_uid"],
            full_name=row["full_name"],
            division=row["division"],
            wins=row["wins"],
            losses=row["losses"],
            draws=row["draws"],
            win_rate=row["win_rate"],
            total_fights=row["total_fights"],
            ko_wins=row["ko_wins"],
            sub_wins=row["sub_wins"],
            dec_wins=row["dec_wins"],
        )
        for row in df.iter_rows(named=True)
    ]


@app.get("/roster", response_model=list[RosterFighter])
def list_roster(
    stance: Optional[str] = Query(None, description="Filter by stance (Orthodox, Southpaw, Switch)"),
    division: Optional[str] = Query(None, description="Filter by weight class"),
    min_fights: int = Query(5, ge=1, description="Minimum UFC fights required"),
    min_win_rate: Optional[float] = Query(None, ge=0, le=100, description="Minimum win rate percentage"),
    max_win_rate: Optional[float] = Query(None, ge=0, le=100, description="Maximum win rate percentage"),
    limit: int = Query(100, ge=1, le=500, description="Maximum results to return"),
) -> list[RosterFighter]:
    df = get_roster(
        stance=stance,
        division=division,
        min_fights=min_fights,
        min_win_rate=min_win_rate,
        max_win_rate=max_win_rate,
        limit=limit,
    )
    return [
        RosterFighter(
            fighter_uid=row["fighter_uid"],
            full_name=row["full_name"],
            stance=row["stance"],
            division=row["division"],
            wins=row["wins"],
            losses=row["losses"],
            draws=row["draws"],
            win_rate=row["win_rate"],
            total_fights=row["total_fights"],
            avg_strikes_landed=row["avg_strikes_landed"],
            avg_strikes_absorbed=row["avg_strikes_absorbed"],
            head_strike_pct=row["head_strike_pct"],
            body_strike_pct=row["body_strike_pct"],
            leg_strike_pct=row["leg_strike_pct"],
        )
        for row in df.iter_rows(named=True)
    ]


@app.get("/events", response_model=list[EventSummary])
def list_events(
    upcoming_only: bool = Query(False, description="Only show events with upcoming fights"),
    limit: int = Query(20, ge=1, le=100, description="Maximum events to return"),
) -> list[EventSummary]:
    df = get_events(upcoming_only=upcoming_only, limit=limit)
    return [
        EventSummary(
            event_uid=row["event_uid"],
            title=row["title"],
            event_date=row["event_date"],
            event_location=row["event_location"],
            num_fights=row["num_fights"],
        )
        for row in df.iter_rows(named=True)
    ]


@app.get("/fight/{fight_uid}", response_model=FightDetail)
def get_fight(fight_uid: str) -> FightDetail:
    fight_df, stats_df = get_fight_detail(fight_uid)

    if fight_df is None:
        raise HTTPException(status_code=404, detail=f"Fight {fight_uid} not found")

    fight_row = fight_df.row(0, named=True)

    def build_fighter_stats(fighter_uid: str, fighter_name: str, result: Optional[str]) -> FightFighterStats:
        rounds = []
        if stats_df is not None:
            fighter_stats = stats_df.filter(stats_df["fighter_uid"] == fighter_uid)
            for row in fighter_stats.iter_rows(named=True):
                rounds.append(
                    FightRoundStats(
                        round_num=row["round_num"],
                        knockdowns=row["knockdowns"],
                        total_strikes_landed=row["total_strikes_landed"],
                        total_strikes_attempted=row["total_strikes_attempted"],
                        sig_strikes_landed=row["sig_strikes_landed"],
                        sig_strikes_attempted=row["sig_strikes_attempted"],
                        takedowns_landed=row["takedowns_landed"],
                        takedowns_attempted=row["takedowns_attempted"],
                        submissions_attempted=row["submissions_attempted"],
                        reversals=row["reversals"],
                        control_time_seconds=row["control_time_seconds"],
                    )
                )
        return FightFighterStats(
            fighter_uid=fighter_uid,
            fighter_name=fighter_name,
            result=result,
            rounds=rounds,
        )

    fighter1 = build_fighter_stats(
        fight_row["fighter1_uid"],
        fight_row["fighter1_name"],
        fight_row["fighter1_result"],
    )
    fighter2 = build_fighter_stats(
        fight_row["fighter2_uid"],
        fight_row["fighter2_name"],
        fight_row["fighter2_result"],
    )

    return FightDetail(
        fight_uid=fight_row["fight_uid"],
        event_uid=fight_row["event_uid"],
        event_title=fight_row["event_title"],
        event_date=fight_row["event_date"],
        fight_division=fight_row["fight_division"],
        fight_type=fight_row["fight_type"],
        decision=fight_row["decision"],
        decision_round=fight_row["decision_round"],
        decision_time_seconds=fight_row["decision_time_seconds"],
        referee=fight_row["referee"],
        fighter1=fighter1,
        fighter2=fighter2,
    )


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
