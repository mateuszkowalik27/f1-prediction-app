"""Lista wszystkich czynników modelu (kolejność nie ma znaczenia)."""
from factors.car_pace import CarPace
from factors.car_track_fit import CarTrackFit
from factors.driver_form import DriverForm
from factors.practice_pace import PracticePace, WeekendShift
from factors.quali_gap import QualiGap
from factors.reliability import Reliability
from factors.track_history import TrackHistory
from factors.wet_skill import WetSkill

ALL_FACTORS = [CarPace(), DriverForm(), TrackHistory(), PracticePace(), WeekendShift(), CarTrackFit(), WetSkill(),
               Reliability(), QualiGap()]
