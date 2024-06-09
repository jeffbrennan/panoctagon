from dataclasses import dataclass
@dataclass(frozen=True)
class Fighter:
    fighter_uid: str
    name_first: str
    name_last: str
    dob: str
    stance: str
    reach_inches: int
    leg_reach_inches: int
    height_inches: int
    division: str
