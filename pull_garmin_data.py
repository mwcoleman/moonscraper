import garminconnect
import pandas as pd
import sys, os
from getpass import getpass
from datetime import datetime
from collections import defaultdict, namedtuple

GARTH_HOME = os.getenv("GARTH_HOME", "~/.garth")


ACTIVITIES = {
    "Deadlift",
    "BP + HB max hang",
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


def pull_workout_data_from_date(dt: str = '1999-01-01', as_dataframe=True):
    
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

    activities = garmin.get_activities(0,30) # from most recent, so should always be ok
    filtered_activities = [
        a for a in activities 
        if a['activityName'] in ACTIVITIES
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
        # Same format as reflex
        try:
            dt = datetime.strftime(
                datetime.strptime(wset['startTime'][:10], "%Y-%m-%d"),
                "%d %b %y"
            )
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

if __name__=="__main__":
    sys.exit(pull_workout_data_from_date('2012-12-02'))