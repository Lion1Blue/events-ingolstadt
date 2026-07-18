#!/usr/bin/env python3

import logging
import os
import time
from datetime import datetime, timedelta, timezone

import requests
from icalendar import Calendar


# ==================================================
# Configuration
# ==================================================

ICS_SOURCE = (
    "https://ingolstadt.live/api/v1/getAllEvents/?type=ics"
)

OUTPUT_FILE = "../events/all-events.ics"

CACHE_FILE = "../cache/original.ics"


# How many months into the future should be included?
MONTHS_AHEAD = 3


# Additional safety time after Retry-After
RETRY_BUFFER_SECONDS = 10


# Minimum score required to keep an event
MIN_SCORE = 10


# ==================================================
# Hard exclusions only
# ==================================================

EXCLUDE_WORDS = [
    "hinterlassenschaften",
    "stadtführung",
    "pfeifturmführung",
    "kinder",
    "ü40",
    "ü50",
    "ü60",
    "ü70",

    # Religious / lectures / low interest
    "english mass",
    "holy mass",
    "gottesdienst",
    "messe",
    "kirch",
    "pfarr",
    "kolloquiumskapelle",
    "mittagsvisite",
    "gartenvisite",
    "gott",
    "samstagorgel",
    "orgel",

    # Tours / educational
    "adfc",
    "führung:",
    "themenführung",
    "seminar",
    "colloquium",
    "CSU",
    "CDU",
]


# ==================================================
# Interest scoring
# ==================================================

INTEREST_WORDS = {

    # -------------------------
    # Culture / Entertainment
    # -------------------------
    "konzert": 5,
    "live": 4,
    "livemusik": 5,
    "musik": 4,
    "jazz": 5,
    "rock": 5,
    "blasmusik": 4,
    "volksmusik": 4,
    "theater": 5,
    "kino": 3,
    "ballett": 4,
    "kabarett": 5,
    "comedy": 5,
    "comedian": 5,
    "show": 5,
    "performance": 4,
    "dj": 4,
    "party": 5,
    "tango": 4,
    "jodel": 4,
    "chor": 5,
    "orchester": 5,
    "festival": 10,
    "fest": 8,
    "open air": 6,

    # -------------------------
    # Museums / Arts / History
    # -------------------------
    "museum": 5,
    "ausstellung": 4,
    "vernissage": 5,
    "kunst": 4,
    "galerie": 4,
    "geschichte": 4,
    "historisch": 3,
    "kultur": 5,
    "kulturen": 4,
    "skulpturen": 3,

    # -------------------------
    # Food / Drinks / Social
    # -------------------------
    "bier": 4,
    "biergarten": 5,
    "brauerei": 4,
    "biertour": 3,
    "cocktail": 4,
    "wine": 3,
    "food": 4,
    "street food": 5,
    "markt": 4,
    "bauernmarkt": 4,
    "picknick": 5,

    # -------------------------
    # Comedy / Stage extras
    # -------------------------
    "humor": 4,
    "lachen": 3,
    "pointen": 3,
    "kabarettprogramm": 5,

    # -------------------------
    # Workshops / Creative
    # -------------------------
    "workshop": 4,
    "siebdruck": 3,
    "handwerk": 3,

    # -------------------------
    # Outdoor / nature
    # -------------------------
    "wander": 5,
    "natur": 3,
    "garten": 2,
    "sommer": 3,
    "radtour": 100,
    "fahrrad": 100,

    # -------------------------
    # Technology / Audi
    # -------------------------
    "technik": 10,
    "audi": 10,
    "programmieren": 100,
    "robotik": 100,

    # -------------------------
    # Places / venues
    # -------------------------
    "eventhalle": 5,
    "kulturzentrum": 5,
    "turm baur": 3,
    "audi forum": 5,
}


# ==================================================
# Negative scoring
# ==================================================

BAD_WORDS = {

    # Family / children
    "kinder": -10,
    "baby": -10,
    "babykonzert": -10,

    # Age groups
    "senioren": -10,
    "ü40": -10,
    "ü50": -10,
    "ü60": -10,
    "ü70": -10,

    # Religion
    "gottesdienst": -10,
    "kirche": -10,
    "messe": -8,

    # Tours / talks
    "stadtführung": -9,
    "pfeifturmführung": -10,
    "vortrag": -8,
    "seminar": -8,
    "kolloquium": -8,

    # Sports / cycling (personal preference)
    "adfc": -100,
}


# ==================================================
# Location scoring
# ==================================================

GOOD_LOCATIONS = {

    "eventhalle": 5,
    "kulturzentrum neun": 5,
    "theater": 5,
    "museum": 4,
    "turm baur": 3,
    "audi sportpark": 3,
    "audi forum": 5,
    "kap94": 4,
    "festsaal": 4,
    "congress centrum": 4,
    "bauerngerätemuseum": 3,
}


BAD_LOCATIONS = {

    "kindergarten": -10,
    "schule": -10,
    "senior": -10,
    "kolloquiumskapelle": -10,
}


# ==================================================
# Logging
# ==================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)


# ==================================================
# Cache handling
# ==================================================

def save_cache(data):

    os.makedirs(
        os.path.dirname(CACHE_FILE),
        exist_ok=True
    )

    with open(CACHE_FILE, "wb") as f:
        f.write(data)

    logging.info(
        "Saved API response to cache"
    )


def load_cache():

    if not os.path.exists(CACHE_FILE):
        return None

    logging.warning(
        "Using cached ICS file"
    )

    with open(CACHE_FILE, "rb") as f:
        return f.read()


# ==================================================
# API Download
# ==================================================

def download_calendar():

    logging.info(
        "Downloading original ICS"
    )

    try:

        response = requests.get(
            ICS_SOURCE,
            timeout=60
        )


        if response.status_code == 200:

            logging.info(
                "API download successful"
            )

            save_cache(
                response.content
            )

            return response.content


        if response.status_code == 429:

            retry_after = int(
                response.headers.get(
                    "Retry-After",
                    3600
                )
            )

            cached = load_cache()


            if cached:

                logging.warning(
                    "API rate limited. Using cached ICS instead."
                )

                logging.warning(
                    "API retry available in approximately %s seconds",
                    retry_after
                )

                return cached


            wait_time = (
                retry_after
                + RETRY_BUFFER_SECONDS
            )


            logging.warning(
                "Rate limited and no cache exists"
            )

            logging.info(
                "Waiting %s seconds before retry",
                wait_time
            )


            time.sleep(
                wait_time
            )


            retry = requests.get(
                ICS_SOURCE,
                timeout=60
            )

            retry.raise_for_status()

            save_cache(
                retry.content
            )

            return retry.content


        response.raise_for_status()


    except requests.RequestException:

        cached = load_cache()

        if cached:

            logging.warning(
                "API error. Using cache"
            )

            return cached

        raise
    
# ==================================================
# Event helpers
# ==================================================

def get_datetime(component, field):

    value = component.get(field)

    if not value:
        return None

    dt = value.dt


    if isinstance(dt, datetime):

        if dt.tzinfo is None:
            dt = dt.replace(
                tzinfo=timezone.utc
            )

        return dt


    return datetime.combine(
        dt,
        datetime.min.time(),
        tzinfo=timezone.utc
    )



def normalize_text(value):

    return (
        str(value or "")
        .strip()
        .lower()
    )



def event_text(event):

    fields = [
        event.get("SUMMARY"),
        event.get("DESCRIPTION"),
        event.get("LOCATION"),
    ]

    return " ".join(
        normalize_text(x)
        for x in fields
    )



def event_score(event):

    text = event_text(event)

    location = normalize_text(
        event.get("LOCATION")
    )

    score = 0


    for word, value in INTEREST_WORDS.items():

        if word in text:
            score += value


    for word, value in BAD_WORDS.items():

        if word in text:
            score += value


    for word, value in GOOD_LOCATIONS.items():

        if word in location:
            score += value


    for word, value in BAD_LOCATIONS.items():

        if word in location:
            score += value


    return score



def event_key(event):

    title = normalize_text(
        event.get("SUMMARY")
    )

    location = normalize_text(
        event.get("LOCATION")
    )

    start = get_datetime(
        event,
        "DTSTART"
    )

    end = get_datetime(
        event,
        "DTEND"
    )


    if not start:
        return None


    if not end:
        end = start + timedelta(
            hours=24
        )


    return (
        title,
        location,
        start,
        end
    )



def is_duplicate(event, existing):

    key = event_key(event)

    if not key:
        return False


    title, location, start, end = key


    for old in existing:

        old_title, old_location, old_start, old_end = old


        if (
            title == old_title
            and location == old_location
        ):

            if (
                start <= old_end
                and end >= old_start
            ):

                return True


    return False



def event_sort_key(event):

    start = get_datetime(
        event,
        "DTSTART"
    )

    return start or datetime.max.replace(
        tzinfo=timezone.utc
    )



# ==================================================
# Filter ICS
# ==================================================

def filter_events(data):

    logging.info(
        "Parsing ICS"
    )


    calendar = Calendar.from_ical(
        data
    )


    output = Calendar()


    for key in [
        "VERSION",
        "PRODID"
    ]:

        if key in calendar:

            output.add(
                key,
                calendar[key]
            )


    now = datetime.now(
        timezone.utc
    )


    limit = (
        now
        + timedelta(
            days=30 * MONTHS_AHEAD
        )
    )


    seen_events = []

    scored_events = []


    stats = {

        "total": 0,
        "kept": 0,
        "duplicate": 0,
        "expired": 0,
        "excluded": 0,
        "low_score": 0,
    }



    for component in calendar.walk():

        if component.name != "VEVENT":
            continue


        stats["total"] += 1


        summary = normalize_text(
            component.get(
                "SUMMARY"
            )
        )


        if any(
            word in summary
            for word in EXCLUDE_WORDS
        ):

            stats["excluded"] += 1
            continue



        start = get_datetime(
            component,
            "DTSTART"
        )


        if not start:
            continue



        if start < now:

            stats["expired"] += 1
            continue



        if start > limit:

            continue



        if is_duplicate(
            component,
            seen_events
        ):

            stats["duplicate"] += 1
            continue



        seen_events.append(
            event_key(component)
        )


        score = event_score(
            component
        )


        if score < MIN_SCORE:

            stats["low_score"] += 1
            continue


        component.add(
            "X-SCORE",
            str(score)
        )


        scored_events.append(
            component
        )


        stats["kept"] += 1



    scored_events.sort(
        key=event_sort_key
    )


    for event in scored_events:

        output.add_component(
            event
        )


    logging.info(
        "Total events: %s",
        stats["total"]
    )

    logging.info(
        "Kept events: %s",
        stats["kept"]
    )

    logging.info(
        "Duplicates removed: %s",
        stats["duplicate"]
    )

    logging.info(
        "Expired removed: %s",
        stats["expired"]
    )

    logging.info(
        "Excluded: %s",
        stats["excluded"]
    )

    logging.info(
        "Low score removed: %s",
        stats["low_score"]
    )


    return output



# ==================================================
# Save output
# ==================================================

def save_calendar(calendar):

    os.makedirs(
        os.path.dirname(OUTPUT_FILE),
        exist_ok=True
    )


    with open(
        OUTPUT_FILE,
        "wb"
    ) as f:

        f.write(
            calendar.to_ical()
        )


    logging.info(
        "Written %s",
        OUTPUT_FILE
    )



# ==================================================
# Main
# ==================================================

def main():

    logging.info(
        "========== START =========="
    )


    try:

        data = download_calendar()


        calendar = filter_events(
            data
        )


        save_calendar(
            calendar
        )


    except Exception:

        logging.exception(
            "Fatal error"
        )

        raise


    finally:

        logging.info(
            "=========== END ==========="
        )


if __name__ == "__main__":

    main()