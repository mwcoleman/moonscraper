import garminconnect
import pandas as pd
import sys, os
from getpass import getpass
from datetime import datetime, timedelta
from collections import defaultdict, namedtuple
import logging
import argparse
from typing import Tuple, Set, List, Dict

GARTH_HOME = os.getenv("GARTH_HOME", "~/.garth")


ACTIVITIES = {
    "Deadlift",
    "BP + HB max hang",
    "HB + (PUP & BP)",
    "HB + Pull Up",
    "DL + HB max hangs",
    "BP 80%",
    "No Hangs",
    "pull up weighted"
}

NAME_MAPPINGS = {
    "CURL": "HB: SC 20mm",
    "OLYMPIC_LIFT": "HB: IMR 20mm",
    "BENCH_PRESS": "benchpress",
    "DEADLIFT": "deadlift",
    "PULL_UP" : "weighted pull up"
}

def config_logger(logger: logging.Logger) -> logging.Logger:
    """
    Standardise logging output
    """

    logger.setLevel(logging.INFO)
    logger.propogate = False

    formatter = logging.Formatter('%(asctime)s: %(levelname)s [%(filename)s:%(lineno)s]: %(message)s')

    stdout_handler = logging.StreamHandler(stream=sys.stdout)
    stdout_handler.setFormatter(formatter)

    logger.addHandler(stdout_handler)
    return logger

_logger = config_logger(logging.getLogger(__name__))



def pull_workout_data_from_date(
        dt: str = '1999-01-01', 
        as_dataframe=True, 
        n_most_recent_activities=30,
        interactive_exclusion=False):
    
    def compare_date(dt_less, dt_greater):
        
        dt_less, dt_greater = [datetime.strptime(dt, "%Y-%m-%d") 
                               for dt in (dt_less, dt_greater)]

        return dt_less <= dt_greater

    email = input("Enter email:")
    password = getpass("Enter password:")

    garmin = garminconnect.Garmin(email, password)
    garmin.login()
    garmin.garth.dump(GARTH_HOME)



    print(f'Connected with id: {garmin.display_name}')

    activities = garmin.get_activities(0,n_most_recent_activities) # from most recent, so should always be ok
    
    found_activity_types = list(set([a['activityName'] for a in activities]))
    
    if interactive_exclusion:
        indexed_activity_types = [
            (i,name) 
            for i,name 
            in enumerate(found_activity_types)
        ]
        print(f'Interactive mode. Found Activites:')
        print(pd.DataFrame(found_activity_types, columns=["Name"]).to_string())

        excluded = input(
            f'Enter indices (listed above) of activities to exclude (e.g. "0,5,6"): ')
            
        excluded = [int(e) for e in excluded.split(",")]
        excluded = [found_activity_types[i] for i in excluded]
        
    else:
        excluded = [a for a in found_activity_types if a not in ACTIVITIES]

    filtered_activities = [
        a for a in activities 
        if a['activityName'] not in excluded
        and compare_date(dt, a['startTimeLocal'][:10])
        ]
    # This is a list list of individual sets. 
    exercise_sets = [
        garmin.get_activity_exercise_sets(a['activityId'])['exerciseSets']
          for a in filtered_activities
        ]
    print(f'Found {len(exercise_sets)} logged exercises across {len(filtered_activities)} days since {dt}')
    # so flatten for ease of iterating
    working_sets = [wset for workout in exercise_sets for wset in workout]

    refactored_working_sets = []#defaultdict(list)

    LoggedGarminExercise = namedtuple('LoggedGarminExercise', 'date ename ereps duration kg')

    for wset in working_sets:

        if wset['setType'] == 'REST':
            continue
        # Name is system name in garmin for that exercise, e.g. hangboard = bicep curl = CURL in category
        ename = wset['exercises'][0]['category']
        try:
            ename = NAME_MAPPINGS[ename] # cat is name, and repeated heaps..
        except:
            print(f'{ename} not found in mappings, adding as is..')
            ename = wset['exercises'][0]['category']
        ereps = 1 if (wset['repetitionCount'] is None) \
                    or (wset['repetitionCount'] == 0) \
                        else wset['repetitionCount']
        # ereps = max(1, wset['repetitionCount']) # default to 1 if garmin didnt log correctly
        weight = wset['weight']
        try:
               dt = datetime.strptime(wset['startTime'][:10], "%Y-%m-%d")

        except:
            # TODO: Some exercises don't log the starttime weirdly. In this case take the last exercise date as log.
            pass
        if weight is None or ename == 'UNKNOWN':
            # print(f"Errors of nonetype for {wset}")
            continue
        duration = wset['duration']

        refactored_working_sets.append(LoggedGarminExercise(dt, ename, ereps, duration, weight/1000))
    if as_dataframe:
        refactored_working_sets = pd.DataFrame(refactored_working_sets, columns=LoggedGarminExercise._fields)
    return refactored_working_sets

def find_existing_date(
        existing_csv_path: str, 
        date_format: str = "%d %b %y"
        ) -> Tuple[pd.DataFrame, datetime]:
    # Return datetime obj
    existing_data = pd.read_csv(existing_csv_path)
    dates = pd.to_datetime(existing_data.date, format=date_format)
    last_date = sorted(dates, reverse=True)[0]
    # last_date = datetime.strptime(existing_data['date'][0], date_format)
    _logger.info(f"Existing csv loaded, date found {last_date}")
    return existing_data, last_date


def main():
    parser = argparse.ArgumentParser(description="CLI Args")
    parser.add_argument("-o", "--output-to", default="./data/garmin_log.csv", help="output file path for logbook entries")
    parser.add_argument("--append-to-existing", default=None, type=str,
                        help="path to existing csv to append from latest date, overrides from_date")
    parser.add_argument("--from-date", default="2012-01-01",
                        help="earliest date to extract logs from, %Y-%m-%d")
    parser.add_argument("--interactive-exclude", action='store_true')

    

    args = parser.parse_args()


    outfile = args.output_to

    if os.path.exists(args.output_to):
        newfile = input(f"{args.output_to} exists. New path and filename (blank to overwrite): ")
        outfile = newfile if newfile != '' else args.output_to
        # os.path.join(args.o, f"{newfile if newfile != '' else 'data.csv'}")


    try:
        existing_data, from_date = find_existing_date(args.append_to_existing, date_format="%Y-%m-%d")
        args.from_date = (from_date + timedelta(days=1)).strftime("%Y-%m-%d")
    except:
        pass

    data = pull_workout_data_from_date(args.from_date, n_most_recent_activities=9999, interactive_exclusion=args.interactive_exclude)
    data['date'] = data.date.dt.strftime("%Y-%m-%d")
    try:
        data = pd.concat([data, existing_data], axis=0)
    except:
        pass

    data.to_csv(outfile, index=False)

if __name__=="__main__":
    # sys.exit(pull_workout_data_from_date('2012-12-02', n_most_recent_activities=9999))
    sys.exit(main())