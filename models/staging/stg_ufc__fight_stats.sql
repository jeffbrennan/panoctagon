select
    fight_uid,
    fighter_uid,
    round_num,
    sig_strikes_body_attempted,
    sig_strikes_body_landed,
    sig_strikes_head_attempted,
    sig_strikes_head_landed,
    sig_strikes_leg_attempted,
    sig_strikes_leg_landed
from {{ source("main", "ufc_fight_stats") }}
