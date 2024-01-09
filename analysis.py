# Mainly scripts for processing the scraped csv data

import pandas as pd
import numpy as np

import re
import os
import sys
from collections import namedtuple
import datetime

Problem = namedtuple("Problem", "date name grade setter mygrade attempts ticked comment")

FONT_TO_HUECO = {
    "6B" : 3,
    "6B+": 4,
    "6C" : 5,
    "6C+": 5.5,
    "7A" : 6,
    "7A+": 7,
    "7B" : 8,
    "7B+": 8.5
}


def load_df(fp: str) -> pd.DataFrame:
    # Redundant wrapper
    df = pd.read_csv(fp)
    assert [col in df.columns for col in ['date', 'text', 'img_path']], f"Error in columns: found {df.columns}"

    return df

def _convert_attempt_to_numeric(s: str) -> int:
    # Used by split text
    simple_map = {
        "Flashed": 1,
        "2nd try": 2,
        "3rd try": 3,
    }

    if "Project" in s or "more" in s.lower():
        matches = re.findall(r'\d+', s)
        return matches[-1]

    return simple_map[s]

def _date_text_to_dt(d: str) -> datetime.datetime:
    return datetime.datetime.strptime(d, "%d %b %y")


def split_text(df: pd.DataFrame) -> pd.DataFrame:
    # Does some basic preprocessing of the text column of the csv
    # Assumes some conventions: 
    # If marked as project, comment may contain a single integer representing attempts
    # - If Project, then it wasn't sent.
    # All other attempt types are ticks.

    problem_list = []

    for i,r in df.iterrows():
        data = r.text.split("\n")
        # num_entries = r.lentlist
        dt = r.date


        # Text either is 6, 7, or 8 rows. 
        # Name
        # Setter
        # Grade
        # "Feet follow hands"
        # (OPTIONAL) "You rated"
        # Attempts
        # "40deg moonboard"
        # (OPTIONAL) comment

        if len(data) == 6:
            # No comment, no rating
            data.insert(4, "No rating")
            data.append("")
        
        if len(data) == 7:
            if data[4] == "You rated this problem":
                # No comment
                data.append("")
            else:
                # No rating
                data.insert(4, "No rating")


        name = data[0]
        setter = data[1]
        # Grade and mygrade if available
        grade = data[2].split(".")
        
        if len(grade) > 1:
            grade, mygrade, _ = grade
            mygrade = mygrade.split(" ")[-1]
        else:
            grade = grade[0]
            mygrade = grade 
        
        comment = data[-1]


        # Attempt type
        attempt = data[5]
        try:
            attempt = attempt + f" ({int(data[-1])})"
            comment = ""
        except:
            comment = data[-1]
        
        # Only one problem has this currently, but in case
        if attempt == "Project":
            attempt = attempt + " (1)"

        ticked = True if "project" not in attempt.lower() else False

        problem_list.append(Problem(dt, name, grade, setter, mygrade, attempt, ticked, comment))

    df = pd.DataFrame(problem_list, columns=Problem._fields)
    df["date"] = df.date.apply(_date_text_to_dt)
    df.set_index("date")

    df.loc[:, "attempts"] = df.attempts.apply(_convert_attempt_to_numeric)
    df.loc[:, "grade_v"] = df.grade.apply(lambda g: FONT_TO_HUECO[g])
    df.loc[:, "mygrade_v"] = df.mygrade.apply(lambda g: FONT_TO_HUECO[g])

    return df

if __name__ == "__main__":
    # Supply inpath and outpath
    df = load_df(sys.argv[1])
    df = split_text(df)
    df.to_csv(sys.argv[2], index=False)


