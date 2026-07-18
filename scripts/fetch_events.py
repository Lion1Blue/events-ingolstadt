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
MONTHS_AHEAD = 4


# Additional safety time after Retry-After
RETRY_BUFFER_SECONDS = 60


# Events containing these words will be removed
# Example:
#
# EXCLUDE_WORDS = [
#     "Ausstellung",
#     "Führung",
# ]
#
EXCLUDE_WORDS = [
]


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

    with open(
        CACHE_FILE,
        "wb"
    ) as f:

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


    with open(
        CACHE_FILE,
        "rb"
    ) as f:

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


        # --------------------------
        # Success
        # --------------------------

        if response.status_code == 200:

            logging.info(
                "API download successful"
            )


            save_cache(
                response.content
            )


            return response.content



        # --------------------------
        # Rate limit
        # --------------------------

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
                    "API rate limited. "
                    "Using cache instead. "
                    "API avaliable in approximately %s seconds",
                    retry_after
                )

                return cached



            wait_time = (
                retry_after
                + RETRY_BUFFER_SECONDS
            )


            logging.warning(
                "API rate limited and no cache exists"
            )


            logging.info(
                "Waiting %s seconds before retry",
                wait_time
            )


            time.sleep(
                wait_time
            )


            logging.info(
                "Retrying API request"
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



        # --------------------------
        # Other HTTP errors
        # --------------------------

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
# Duplicate detection
# ==================================================

def event_key(event):

    """
    Duplicate rule:

    same title
    same start date/time
    same location
    """

    title = str(
        event.get(
            "SUMMARY",
            ""
        )
    ).strip().lower()


    location = str(
        event.get(
            "LOCATION",
            ""
        )
    ).strip().lower()



    start = event.get(
        "DTSTART"
    )


    if start:

        date = start.dt.isoformat()

    else:

        date = ""


    return (
        title,
        date,
        location
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


    # Keep calendar metadata

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


    seen = set()


    stats = {

        "total": 0,
        "kept": 0,
        "duplicate": 0,
        "expired": 0,
        "excluded": 0,
    }



    for component in calendar.walk():


        if component.name != "VEVENT":

            continue



        stats["total"] += 1



        summary = str(
            component.get(
                "SUMMARY",
                ""
            )
        )



        # Exclusions

        if any(

            word.lower()
            in summary.lower()

            for word in EXCLUDE_WORDS

        ):

            stats["excluded"] += 1

            continue



        start = component.get(
            "DTSTART"
        )


        if not start:

            continue



        event_date = start.dt



        # all-day events

        if not isinstance(
            event_date,
            datetime
        ):

            event_date = datetime.combine(
                event_date,
                datetime.min.time(),
                tzinfo=timezone.utc
            )


        elif event_date.tzinfo is None:

            event_date = event_date.replace(
                tzinfo=timezone.utc
            )



        # Past events

        if event_date < now:

            stats["expired"] += 1

            continue



        # Outside range

        if event_date > limit:

            continue



        # Duplicate

        key = event_key(
            component
        )


        if key in seen:

            stats["duplicate"] += 1

            continue



        seen.add(
            key
        )


        output.add_component(
            component
        )


        stats["kept"] += 1



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
