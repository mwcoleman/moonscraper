
from selenium import webdriver
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
import logging
import itertools
import bisect
import pandas as pd
import os, json, sys, argparse, time, pathlib
import getpass
import logging
from collections import namedtuple


from datetime import datetime, timedelta


getGecko_installed = True

try:
    from get_gecko_driver import GetGeckoDriver


except BaseException:
    getGecko_installed = False

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


ScrapedEntry = namedtuple('Entry', 'date text imagepath')

class Scraper:

    def __init__(self, debug: bool, output_image_path):
        self.MB_URL = "https://www.moonboard.com"
        self.debug = debug

        self.image_path = output_image_path

        pathlib.Path(self.image_path).mkdir(parents=True, exist_ok=True)

        # # use getGecko to get the driver
        # if getGecko_installed:
        #     _logger.info("Getting GeckoDriver")
        #     get_driver = GetGeckoDriver()
        #     get_driver.install()

        # self.MONTH_MAP = {
        #     "Jan": 1,
        #     "Feb": 2,
        #     "Mar": 3,
        #     "Apr": 4,
        #     "May": 5,
        #     "Jun": 6,
        #     "Jul": 7,
        #     "Aug": 8,
        #     "Sep": 9,
        #     "Oct": 10,
        #     "Nov": 11,
        #     "Dec": 12
        # }

    def fetch_data(
            self, 
            USERNAME: str, 
            PASSWORD: str, 
            board_number: int, 
            from_date: str, 
            ):

        # use the installed GeckoDriver with Selenium
        fireFoxOptions = webdriver.FirefoxOptions()
        # fireFoxOptions.headless = not self.debug
        if not self.debug:
            _logger.info("Running in headless mode.")
            fireFoxOptions.add_argument("-headless")

        _logger.info(f"Fetching web data. Allow some minutes.")

        driver = webdriver.Firefox(options=fireFoxOptions)

        driver.get(self.MB_URL)



        # login
        driver.find_element(By.ID, "loginDropdown").click()
        driver.find_element(By.ID, "Login_Username").send_keys(USERNAME)
        driver.find_element(By.ID, "Login_Password").send_keys(PASSWORD)
        driver.find_element(By.ID, "navlogin").click()

        # WebDriverWait(
        #     driver, 10).until(
        #     EC.presence_of_element_located(
        #         (By.ID, "navlogin")))
        #WebDriverWait(browser, 10).until(EC.presence_of_element_located((By.ID, "element_id")))
        time.sleep(5)
        # navigate to logbook
        # driver.get("https://moonboard.com/Logbook/Index")
        driver.find_element(By.ID,"llogbook").click()
        time.sleep(0.5)
        driver.find_element(By.LINK_TEXT, "VIEW").click()

        time.sleep(5)  # TODO: await properly

        # select version
        select = Select(driver.find_element(By.ID,"Holdsetup"))
        select.select_by_index(board_number)  

        time.sleep(5)  # TODO: await properly


        
        # Lag
        time.sleep(3)

        # create list of elements
        scraped_entries = []

        # # TODO: What even..
        # def any_nested(entry_list, entry_text): 
        #     return any([k == entry_text for k, _, _ in entry_list])
        
        
        # Each element is a page that contains up to 40 dates 
        # does not include the first page, currently, selected, element XPATh 'k-state-selected'
        page_elements = driver.find_elements(By.XPATH,"//a[@class='k-link']")

        _logger.info(f"{len(page_elements) + 1} pages found in logbook..")

        # found_date = False
        # Iterate through pages, and then dates
        for i in range(len(page_elements) + 1):
            # Can't directly work with page elements as they go stale
            _logger.info(f"Processing page {i+1}")
            # Used to find individual entries
            main_section = driver.find_element(By.ID,"main-section")

            # get headers for each clickable date - can be used to find the date text. 
            headers = main_section.find_elements(
                By.CLASS_NAME, "logbook-grid-header")

            # Generate a list of dates repeated based on number of problems for that day (for iterating over later)
            # This will be used later
            date_texts = [h.text.split('\n')[0] for h in headers]
            num_problems_per_date = [int(h.text.split('\n')[1][:2]) for h in headers]
            repeated_date_list = itertools.chain.from_iterable(
                itertools.repeat(value, count) 
                for value, count in zip(date_texts, num_problems_per_date)
            )
            
            # Count to from_date (if present)
            from_date_as_dt = datetime.strptime(from_date, "%d-%m-%y")
            dates_as_dts = [datetime.strptime(d, "%d %b %y") for d in date_texts]

            last_page = False

            if from_date_as_dt > min(dates_as_dts):
                last_page = True
                # Must be in ascending order for bisect
                earliest_entry = len(dates_as_dts) - bisect.bisect_right(dates_as_dts[::-1], from_date_as_dt)
                _logger.info(f"Earliest date ({from_date}) reached on page {i+1} after {earliest_entry} entries.")
            
            else:
                earliest_entry = len(date_texts)

            

            # get a tag expanders for the various days
            date_expanders = main_section.find_elements(
                By.XPATH, "//a[@class='k-icon k-i-expand']")

            # Click to expand all dates
            # for date_expander, header in zip(date_expanders[:earliest_entry], headers[:earliest_entry]):
            for date_expander in date_expanders[:earliest_entry]:
                date_expander.click()
                time.sleep(1)

            # Should contain all entries for the entire page
            entries = main_section.find_elements(By.CLASS_NAME, "entry")

            # TODO: Entries are _always_ (?) duplicated, unknown reason. Quick fix. 
            entries = entries[::2]

            _logger.info(f"{len(entries)} entries found (page {i + 1}). Scraping..")

            # Entries has been sliced to the from_date
            for (entry, entry_date) in zip(entries, repeated_date_list):
                entry_name = entry.text.split('\n')[0]
                img_path = os.path.join(self.image_path, entry_name.replace(" ","_")+".png")
                if not os.path.isfile(img_path):
                    # Get screenshot only if the file doesn't exist
                    entry.click()
                    time.sleep(1)
                    driver.get_screenshot_as_file(img_path)       
                
                # get data
                scraped_entry = ScrapedEntry(entry_date, entry.text, img_path)  
                scraped_entries.append(scraped_entry)
            
            if last_page:
                break
            
            else:
                # Navigate to the next page by clicking on the number
                # Clicker id is always the last in the list (for progressing to next page.)
                next_page_clicker = driver.find_elements(By.XPATH,"//a[@class='k-link k-pager-nav']")[-1]
                next_page_clicker.click()
                time.sleep(5)
                
        _logger.info(f"Completed scraping {len(scraped_entries)} entries.")
        # process data
        # if return_format == 'json':
        #     formatted_data = []
        #     for (data, date, img_name) in res:
        #         data_arr = data.split('\n')
        #         day, month, year = date.split('\n')[0].split(' ')
        #         day, month, year = int(day), self.MONTH_MAP[month], int(year)

        #         formatted = {
        #             'Name': data_arr[0],
        #             'Setter': data_arr[1],
        #             'Grade': data_arr[2].split('.')[0],
        #             'Date': (day, month, year),
        #             'png': img_name,
        #             'raw_text': data
        #         }

        #         formatted_data.append(formatted)
        # else:
        df = pd.DataFrame(([e.date, e.text, e.imagepath] for e in scraped_entries), 
                          columns=['date', 'text', 'img_path'])
        driver.quit()
        return df


def main():
    parser = argparse.ArgumentParser(description="CLI args")
    parser.add_argument("-b", type=int, choices=[0,1,2,3,4], default=4,
                        help='Board: 0-2024, 1-2020Mini, 2-2019, 3-2017, 4-2016')
    parser.add_argument("-d", "--debug", action="store_true")
    parser.add_argument("-o", "--output-to", default="./data.csv", help="output path for json and images")
    parser.add_argument("--output-images-to", default="./images", help="path to save images.")
    parser.add_argument("--from-date", type=str, default="30-01-99", help="Earliest date to extract logs from. %d %b %y")
    parser.add_argument("--append-to-existing", default=None, type=str, 
                        help="path to existing csv to append from lastest date, overrides file_format and from_date.")

    args = parser.parse_args()


    outfile = args.output_to

    if os.path.exists(args.output_to):
        newfile = input(f"{args.output_to} exists. New path and filename (blank to overwrite): ")
        outfile = newfile if newfile != '' else args.output_to
        # os.path.join(args.o, f"{newfile if newfile != '' else 'data.csv'}")

    uname = input("Username:")
    password = getpass.getpass("Password:")

    try:
        existing_data = pd.read_csv(args.append_to_existing)
        last_date = datetime.strptime(existing_data['date'][0], "%d %b %y") 
        args.from_date = (last_date + timedelta(days=1)).strftime("%d-%m-%y")

        print(f"Existing csv loaded, date found {args.from_date}")

    except:
        pass

    scraper = Scraper(debug=args.debug, output_image_path=args.output_images_to)

    data = scraper.fetch_data(
        uname, 
        password, 
        args.b, 
        args.from_date, 
        )

    try:
        data = pd.concat([data, existing_data], axis=0)
    except:
        pass

    _logger.info(f"Writing to {outfile}")

    data.to_csv(outfile, index=False)

    _logger.info(f"Done.")

if __name__ == '__main__':
    sys.exit(main())
