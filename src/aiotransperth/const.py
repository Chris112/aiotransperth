"""Endpoints and static header sets for Transperth's website APIs."""

BASE_URL = "https://www.transperth.wa.gov.au"

_SILVERRAIL = f"{BASE_URL}/API/SilverRailRestService/SilverRailService"
STOP_TIMETABLE_URL = f"{_SILVERRAIL}/GetStopTimetableAsync"
OPTIONS_URL = f"{_SILVERRAIL}/GetTimetableOptionsAsync"
TRIP_URL = f"{_SILVERRAIL}/GetTimetableTripAsync"

TRAIN_STATUS_URL_TEMPLATE = (
    f"{BASE_URL}/API/TrainLiveTimes/LiveStatus/GetStationLiveStatusAsync"
    "/{line}/{station}/false"
)
LIVE_TRAIN_TIMES_PAGE = f"{BASE_URL}/Timetables/Live-Train-Times"

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

TRAIN_HEADERS = {
    "ModuleId": "5111",
    "TabId": "248",
    "User-Agent": USER_AGENT,
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
}

# Service-note codes the Transperth website sends; responses index into them.
NOTE_CODES = "DV,LM,CM,TC,BG,FG,LK"

DEFAULT_TIMEOUT = 15.0
