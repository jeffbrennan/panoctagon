from pathlib import Path

import duckdb


def seed_dashboard(path: Path, outlier: bool = False) -> None:
    with duckdb.connect(str(path)) as db:
        db.execute("""
            create table ufc_fighters (
                fighter_uid varchar, first_name varchar, last_name varchar, nickname varchar,
                dob varchar, place_of_birth varchar, stance varchar, style varchar,
                height_inches int, reach_inches int, leg_reach_inches int
            );
            insert into ufc_fighters values
                ('alpha', 'Alex', 'Alpha', 'A', '1990-01-01', null, 'Orthodox', null, 72, 74, null),
                ('bravo', 'Blair', 'Bravo', null, '1995-01-01', null, 'Southpaw', null, 70, 70, null),
                ('charlie', 'Casey', 'Charlie', null, null, null, null, null, null, null, null);
            create table ufc_events (event_uid varchar, title varchar, event_date varchar,
                event_location varchar, downloaded_ts varchar);
            insert into ufc_events values
                ('past', 'UFC Test', '2024-01-01', 'Test City', '2024-01-02T00:00:00'),
                ('future', 'UFC Future', '2099-01-01', 'Test City', '2024-01-03T00:00:00');
            create table ufc_fights (fight_uid varchar, event_uid varchar,
                fighter1_uid varchar, fighter2_uid varchar, fighter1_result varchar,
                fighter2_result varchar, fight_division varchar, fight_type varchar,
                decision varchar, decision_round int, fight_order int);
            insert into ufc_fights
                select 'fight' || cast(i as varchar), 'past', 'alpha', 'bravo',
                    case when i < 5 then 'WIN' else 'LOSS' end,
                    case when i < 5 then 'LOSS' else 'WIN' end,
                    'MIDDLEWEIGHT', 'REGULAR', 'TKO', 1, i from range(1, 6) t(i);
            insert into ufc_fights values
                ('upcoming', 'future', 'alpha', 'charlie', null, null, 'MIDDLEWEIGHT', 'REGULAR', null, null, 1),
                ('missingstats', 'past', 'alpha', 'charlie', 'NO_CONTEST', 'NO_CONTEST', 'HEAVYWEIGHT', 'REGULAR', 'DQ', 1, 6);
            create table ufc_fight_stats (fight_uid varchar, fighter_uid varchar, round_num int,
                total_strikes_landed int, total_strikes_attempted int,
                sig_strikes_landed int, sig_strikes_attempted int,
                sig_strikes_head_landed int, sig_strikes_body_landed int, sig_strikes_leg_landed int,
                takedowns_landed int, control_time_seconds int);
            insert into ufc_fight_stats
                select 'fight' || cast(i as varchar), 'alpha', 1, 30, 60, 20, 40, 10, 6, 4, 1, 50 from range(1, 6) t(i);
            insert into ufc_fight_stats
                select 'fight' || cast(i as varchar), 'bravo', 1, 10, 40, 10, 25, 5, 3, 2, 0, 0 from range(1, 6) t(i);
            create table bfo_ufc_link (fight_uid varchar, fighter_uid varchar, match_id int, fighter varchar);
            create table bfo_parsed_odds (match_id int, fighter varchar, closing_odds int, event_date varchar, slug varchar);
            insert into bfo_ufc_link values ('fight1', 'alpha', 1, 'alpha'), ('upcoming', 'alpha', 2, 'alpha');
            insert into bfo_parsed_odds values
                (1, 'alpha', -110, '2023-12-30', 'old'), (1, 'alpha', -150, '2024-01-01', 'new'),
                (2, 'alpha', -200, '2098-12-30', 'future');
        """)
        if outlier:
            db.execute(
                "update ufc_fight_stats set sig_strikes_head_landed = 0, sig_strikes_body_landed = 16 where fight_uid = 'fight1' and fighter_uid = 'alpha'"
            )
