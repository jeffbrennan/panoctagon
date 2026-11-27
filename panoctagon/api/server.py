from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Request
from starlette.responses import JSONResponse

from panoctagon.api.database import _active, dispose_cached_engines, resolve_revision, warm_runtime
from fastapi.middleware.gzip import GZipMiddleware

from panoctagon.api.analytics import router as analytics_router

from panoctagon.api.models import (
    EventDetail,
    EventFight,
    EventSummary,
    FightDetail,
    FighterBio,
    FighterDetail,
    FighterFightSummary,
    FighterRecord,
    FighterSearchResult,
    FighterStats,
    FightFighterStats,
    FightRoundStats,
    FightSummary,
    RankedFighter,
    RosterFighter,
    UpcomingEvent,
    UpcomingMatchup,
)
from panoctagon.api.queries import (
    get_divisions,
    get_event_by_uid,
    get_event_fights,
    get_events,
    get_fight_detail,
    get_fighter_detail,
    get_fighter_fights,
    get_fighter_stats,
    get_rankings,
    get_roster,
    get_upcoming_rows,
    search_events,
    search_fighters,
)


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    warm_runtime()
    try:
        yield
    finally:
        dispose_cached_engines()


app = FastAPI(
    title="Panoctagon API",
    description="UFC fight data API",
    version="0.1.0",
    lifespan=_lifespan,
)
app.add_middleware(GZipMiddleware, minimum_size=1000)


@app.middleware("http")
async def pin_database_revision(request: Request, call_next):
    try:
        revision = resolve_revision()
    except (OSError, ValueError, KeyError):
        return JSONResponse({"detail": "Database snapshot unavailable"}, status_code=503)
    token = _active.set(revision)
    try:
        return await call_next(request)
    finally:
        _active.reset(token)


app.include_router(analytics_router)


@app.get("/fighter", response_model=list[FighterSearchResult])
def list_fighters(
    name: Optional[str] = Query(None, description="Search fighters by name (substring match)"),
    division: Optional[str] = Query(None, description="Filter by weight class"),
    limit: int = Query(50, ge=1, le=200, description="Maximum results to return"),
) -> list[FighterSearchResult]:
    rows = search_fighters(name=name, division=division, limit=limit)
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
        for row in rows
    ]


@app.get("/fighter/{fighter_uid}", response_model=FighterDetail)
def get_fighter(fighter_uid: str) -> FighterDetail:
    bio_row, record_row, fight_rows = get_fighter_detail(fighter_uid)

    if bio_row is None or record_row is None:
        raise HTTPException(status_code=404, detail=f"Fighter {fighter_uid} not found")

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
        for row in fight_rows
    ]

    return FighterDetail(bio=bio, record=record, recent_fights=recent_fights)


@app.get("/fighter/{fighter_uid}/stats", response_model=FighterStats)
def get_fighter_stats_endpoint(fighter_uid: str) -> FighterStats:
    row = get_fighter_stats(fighter_uid)

    if row is None:
        raise HTTPException(status_code=404, detail=f"Fighter {fighter_uid} not found")

    return FighterStats(
        avg_sig_strikes=row["avg_sig_strikes"],
        strike_accuracy=row["strike_accuracy"],
        avg_takedowns=row["avg_takedowns"],
        total_knockdowns=row["total_knockdowns"],
        ko_wins=row["ko_wins"],
        sub_wins=row["sub_wins"],
        dec_wins=row["dec_wins"],
        avg_opp_win_rate=row["avg_opp_win_rate"],
    )


@app.get("/upcoming", response_model=list[UpcomingEvent])
def list_upcoming() -> list[UpcomingEvent]:
    upcoming_rows = get_upcoming_rows()

    if not upcoming_rows:
        return []

    events: dict[str, UpcomingEvent] = {}

    for row in upcoming_rows:
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
            fighter1_closing_odds=row["fighter1_closing_odds"],
            fighter2_closing_odds=row["fighter2_closing_odds"],
            fighter1_total_fights=row["fighter1_total_fights"],
            fighter2_total_fights=row["fighter2_total_fights"],
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
    sort_by: str = Query(
        "win_rate",
        description="Sort by: win_rate, sig_strikes, strike_accuracy, takedowns, knockdowns, ko_wins, sub_wins, opp_win_rate",
    ),
) -> list[RankedFighter]:
    rows = get_rankings(division=division, min_fights=min_fights, limit=limit, sort_by=sort_by)
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
            avg_sig_strikes=row["avg_sig_strikes"],
            strike_accuracy=row["strike_accuracy"],
            avg_takedowns=row["avg_takedowns"],
            total_knockdowns=row["total_knockdowns"],
            opp_win_rate=row["opp_win_rate"],
        )
        for row in rows
    ]


@app.get("/roster", response_model=list[RosterFighter])
def list_roster(
    division: Optional[str] = Query(None, description="Filter by weight class"),
    min_fights: int = Query(5, ge=1, description="Minimum UFC fights required"),
    min_win_rate: Optional[float] = Query(
        None, ge=0, le=100, description="Minimum win rate percentage"
    ),
    max_win_rate: Optional[float] = Query(
        None, ge=0, le=100, description="Maximum win rate percentage"
    ),
    limit: int = Query(100, ge=1, le=500, description="Maximum results to return"),
    sort_by: str = Query(
        "win_rate",
        description="Sort by: win_rate, sig_strikes, strike_accuracy, takedowns, knockdowns, ko_wins, sub_wins, opp_win_rate",
    ),
) -> list[RosterFighter]:
    rows = get_roster(
        division=division,
        min_fights=min_fights,
        min_win_rate=min_win_rate,
        max_win_rate=max_win_rate,
        limit=limit,
        sort_by=sort_by,
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
            ko_wins=row["ko_wins"],
            sub_wins=row["sub_wins"],
            dec_wins=row["dec_wins"],
            avg_sig_strikes=row["avg_sig_strikes"],
            strike_accuracy=row["strike_accuracy"],
            avg_takedowns=row["avg_takedowns"],
            total_knockdowns=row["total_knockdowns"],
            opp_win_rate=row["opp_win_rate"],
        )
        for row in rows
    ]


@app.get("/events", response_model=list[EventSummary])
def list_events(
    upcoming_only: bool = Query(False, description="Only show events with upcoming fights"),
    limit: int = Query(20, ge=1, le=100, description="Maximum events to return"),
) -> list[EventSummary]:
    rows = get_events(upcoming_only=upcoming_only, limit=limit)
    return [
        EventSummary(
            event_uid=row["event_uid"],
            title=row["title"],
            event_date=row["event_date"],
            event_location=row["event_location"],
            num_fights=row["num_fights"],
        )
        for row in rows
    ]


@app.get("/fight/{fight_uid}", response_model=FightDetail)
def get_fight(fight_uid: str) -> FightDetail:
    fight_row, stats_rows = get_fight_detail(fight_uid)

    if fight_row is None:
        raise HTTPException(status_code=404, detail=f"Fight {fight_uid} not found")

    def build_fighter_stats(
        fighter_uid: str, fighter_name: str, result: Optional[str]
    ) -> FightFighterStats:
        rounds = [
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
            for row in stats_rows
            if row["fighter_uid"] == fighter_uid
        ]
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


@app.get("/event/search", response_model=list[EventSummary])
def search_events_endpoint(
    name: Optional[str] = Query(None, description="Search events by name"),
    limit: int = Query(20, ge=1, le=100, description="Maximum events to return"),
) -> list[EventSummary]:
    rows = search_events(name=name, limit=limit)
    return [
        EventSummary(
            event_uid=row["event_uid"],
            title=row["title"],
            event_date=row["event_date"],
            event_location=row["event_location"],
            num_fights=row["num_fights"],
        )
        for row in rows
    ]


@app.get("/event/{event_uid}", response_model=EventDetail)
def get_event_detail(event_uid: str) -> EventDetail:
    event_row = get_event_by_uid(event_uid)

    if event_row is None:
        raise HTTPException(status_code=404, detail=f"Event {event_uid} not found")

    fight_rows = get_event_fights(event_uid)
    fights = [
        EventFight(
            fight_uid=row["fight_uid"],
            fight_division=row["fight_division"],
            fight_type=row["fight_type"],
            fight_order=row["fight_order"],
            fighter1_name=row["fighter1_name"],
            fighter1_result=row["fighter1_result"],
            fighter2_name=row["fighter2_name"],
            fighter2_result=row["fighter2_result"],
            decision=row["decision"],
            decision_round=row["decision_round"],
        )
        for row in fight_rows
    ]

    return EventDetail(
        event_uid=event_row["event_uid"],
        title=event_row["title"],
        event_date=event_row["event_date"],
        event_location=event_row["event_location"],
        fights=fights,
    )


@app.get("/fighter/{fighter_uid}/fights", response_model=list[FighterFightSummary])
def get_fighter_fights_endpoint(
    fighter_uid: str,
    limit: int = Query(10, ge=1, le=50, description="Maximum fights to return"),
) -> list[FighterFightSummary]:
    rows = get_fighter_fights(fighter_uid, limit=limit)
    return [
        FighterFightSummary(
            fight_uid=row["fight_uid"],
            event_title=row["event_title"],
            event_date=row["event_date"],
            fight_division=row["fight_division"],
            opponent_name=row["opponent_name"],
            result=row["result"],
            decision=row["decision"],
            decision_round=row["decision_round"],
        )
        for row in rows
    ]


@app.get("/divisions", response_model=list[str])
def list_divisions() -> list[str]:
    return get_divisions()


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
