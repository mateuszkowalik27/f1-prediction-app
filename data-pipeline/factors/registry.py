"""Lista wszystkich czynników modelu (kolejność nie ma znaczenia)."""
from factors.car_pace import CarPace
from factors.car_track_fit import CarTrackFit
from factors.driver_form import DriverForm
from factors.pit_stop import PitStopSpeed
from factors.practice_pace import PracticePace, WeekendShift
from factors.quali_gap import QualiGap
from factors.race_vs_quali import RaceVsQuali
from factors.rating_race import RatingRace
from factors.reliability import Reliability
from factors.temp_fit import TempFit
from factors.track_history import TrackHistory
from factors.tyre_deg_fit import TyreDegFit
from factors.wet_skill import WetSkill

ALL_FACTORS = [CarPace(), DriverForm(), TrackHistory(), PracticePace(), WeekendShift(), CarTrackFit(), WetSkill(),
               Reliability(), QualiGap(), PitStopSpeed(), RaceVsQuali(), TyreDegFit(), TempFit(), RatingRace()]
