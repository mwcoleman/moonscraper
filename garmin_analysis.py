import datetime
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import sys, os, logging


# Collection of scripts to assist in presenting summary info on garmin logs.
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

def calc_load(df, tut_to_rep_mapping={'HB: SC 20mm': 2.5, 'HB: IMR 20mm': 2.5}):
    # Maps a time-duration exercise to a rep count
    df.loc[:, 'rep_load'] = df.ereps * df.kg
    tut_only = df.ename.isin(tut_to_rep_mapping.keys())
    df.loc[tut_only, "rep_load"] = df.loc[tut_only].apply(
        lambda row: (row.duration / tut_to_rep_mapping[row.ename]) * row.kg,
        axis=1
    )
    return df

def filter_df(
        df: pd.DataFrame, 
        exclude_names=[],
        exclude_weeks=[],
        week_col_name="dt_cut",
        min_kg=0, 
        max_duration=30,
        rename_nohangs=True
        ):
    # Filter out by name, kg, etc. To filter out 'no hangs'
    df.loc[df.duration > max_duration, "duration"] = 30
    if rename_nohangs:
        df.loc[((df.ename == "HB: IMR 20mm") | (df.ename == "HB: SC 20mm")) 
               & (df.kg == 62), "ename"] = "no hangs"
    
    if exclude_weeks != [] and week_col_name in df.columns:
        df = df[df[week_col_name].isin(exclude_weeks)]

    return df[(~df.ename.isin(exclude_names)) & (df.kg>min_kg)].dropna()


def weekly_bins(
        block_start=None, 
        block_end=None,
        previous_n_weeks=None ,
        dataframe=None,
        date_format="%Y-%m-%d"
        ):
    # Generate a DatetimeIndex of weeks between start and end
    # if end not specified, uses the monday after (or on) today
    # Returns a 4-tup of bin indexes, the bin labels, bin labels as text,
    # and the ordered series to match input df (None if no dataframe provided)
    if block_end is not None:
        end_dt = datetime.datetime.strptime(block_end, date_format)
    else:   
        end_dt = datetime.date.today()
    
    end_dt += datetime.timedelta(days=(7-datetime.date.today().weekday())) # Round to monday
    
    if block_start is not None:
        start_dt = datetime.datetime.strptime(block_start, date_format)

    elif previous_n_weeks is not None:
        start_dt = end_dt - datetime.timedelta(weeks=previous_n_weeks)
    
    else:
        _logger.error(f"One of block_start of previous_n_weeks must be supplied")
        return None
    
    bins_dt = pd.date_range(start=start_dt, end=end_dt, freq="7D")
    
    bin_labels = [i+1 for i,dt in enumerate(bins_dt[:-1])]
    bin_labels_text = [f"Week {i+1} ({dt.strftime('%d %b')})" for i,dt in enumerate(bins_dt[:-1])]
    
    
    if dataframe is not None:
        dt_cut_series = pd.cut(
            dataframe['date'],
            bins=bins_dt,
            labels=bin_labels,
            right=False,
            include_lowest=True 
            )
        # dt_cut_series_text = dt_cut_series.apply(lambda x: bin_labels_text[x-1])
    else:
        dt_cut_series = None
        # dt_cut_series_text = None
    _logger.info(f"{len(bin_labels)} weeks: ")
    print(pd.DataFrame(bin_labels_text).to_string())
    return bins_dt, bin_labels_text, dt_cut_series#, dt_cut_series_text

# def report_block_summary(df):
