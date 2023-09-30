
from selenium import webdriver
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
import logging
import itertools
import datetime

import os, json, sys, argparse, time, pathlib

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

class Scraper:

    def __init__(self, DEBUG: bool, output_path='./'):
        self.MB_URL = "https://www.moonboard.com"
        self.DEBUG = DEBUG

        self.IMAGE_PATH = os.path.join(output_path,"images")
        pathlib.Path(self.IMAGE_PATH).mkdir(parents=True, exist_ok=True)

        # use getGecko to get the driver
        if getGecko_installed:
            print("Getting GeckoDriver")
            get_driver = GetGeckoDriver()
            get_driver.install()

        self.MONTH_MAP = {
            "Jan": 1,
            "Feb": 2,
            "Mar": 3,
            "Apr": 4,
            "May": 5,
            "Jun": 6,
            "Jul": 7,
            "Aug": 8,
            "Sep": 9,
            "Oct": 10,
            "Nov": 11,
            "Dec": 12
        }

    def fetch_data(self, USERNAME: str, PASSWORD: str, newer_than: str) -> dict:
        
        newer_than = "01-01-01" if newer_than is None else newer_than
        newer_than = datetime.datetime.strptime(newer_than, "%d-%m-%y")
        
        # use the installed GeckoDriver with Selenium
        fireFoxOptions = webdriver.FirefoxOptions()
        fireFoxOptions.headless = not self.DEBUG
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
        select.select_by_index(3)  # 2019 version TODO : more stable

        time.sleep(5)  # TODO: await properly


        
        # Lag
        time.sleep(3)

        # create list of elements
        res = []
        # TODO: What even..
        def any_nested(entry_list, entry_text): return any([k == entry_text for k, _, _ in entry_list])
        
        # 
        
        # Each element is a page that contains up to 40 dates 
        # does not include the first page, currently, selected, element XPATh 'k-state-selected'
        page_elements = driver.find_elements(By.XPATH,"//a[@class='k-link']")

        _logger.info(f"{len(page_elements) + 1} pages of dates found in logbook..")

        found_date = False
        # Iterate through pages, and then dates
        for i, _ in enumerate(page_elements):
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


            

            # get a tag expanders for the various days
            date_expanders = main_section.find_elements(
                By.XPATH, "//a[@class='k-icon k-i-expand']")

            # Click to expand all dates
            for date_expander, header in zip(date_expanders, headers):
                datetext = header.text.split('\n')[0]
                # Text if clickable date is older than oldest wanted date
                if datetime.datetime.strptime(datetext, "%d %b %y") < newer_than:
                    found_date = True
                    break
                date_expander.click()
                time.sleep(1)

            # SHould contain all entries for the entire page
            entries = main_section.find_elements(By.CLASS_NAME, "entry")
            entry_names = [e.text.split('\n')[0] for e in entries]

            # Logbook error has dupes (doubles) of entries in consecutive slots

            # TODO: Better way to do this.. But the ids arent duped.. just text
            # unique_entries = [(entries[i],entry_text[i]) for i in range(1, len(entries)) 
            #                     if i==1 or (entry_text[i] != entry_text[i-1])]
            entries = entries[::2]

            print(f"Page {i + 1} - #Entries: {len(entries)} ")
            for i, (entry, entry_date) in enumerate(zip(entries, repeated_date_list)):
                
                # # Test if we've hit date criteria
                # if datetime.strptime(entry_date, "%d %b %y") < newer_than:
                #     # Break inner and outer loop
                #     found_date = True
                #     break
                
                entry_name = entry.text.split('\n')[0]
                img_path = os.path.join(self.IMAGE_PATH, entry_name.replace(" ","_")+".png")
                if not os.path.isfile(img_path):
                    # Get screenshot only if the file doesn't exist
                    # TODO: Update when using rdbms
                    entry.click()
                    time.sleep(1)
                    driver.get_screenshot_as_file(img_path)       
                
                # get data
                # if not any_nested(res, entry.text):
                res_entry = (entry.text, entry_date, img_path)  # (route info, date)
                res.append(res_entry)
                # else:
                    # pass
            
            # Break early if we found date's older than the oldest wanted
            if found_date:
                break
            
            # Navigate to the next page by clicking on the number
            next_page_clicker = driver.find_elements(By.XPATH,"//a[@class='k-link k-pager-nav']")[0]
            next_page_clicker.click()
            time.sleep(5)
                
        _logger.info(f"Completed scraping {len(res)} entries. Formatting and storing..")
        # process data
        formatted_data = []
        for (data, log_date, img_name) in res:
            data_arr = data.split('\n')
            day, month, year = log_date.split('\n')[0].split(' ')
            day, month, year = int(day), self.MONTH_MAP[month], int(year)

            formatted = {
                'Name': data_arr[0],
                'Setter': data_arr[1],
                'Grade': data_arr[2].split('.')[0],
                'Date': (day, month, year),
                'png': img_name
            }

            formatted_data.append(formatted)

        # cleanup
        driver.quit()

        return formatted_data


def main():
    parser = argparse.ArgumentParser(description='CLI args')
    parser.add_argument("-u", required=True, help='Username')
    parser.add_argument("-p", required=True, help='Password')
    parser.add_argument("-b", type=int, choices=[0,1,2,3], default=3,
                        help='Board: 0-2020Mini, 1-2019, 2-2017, 3-2016')
    parser.add_argument("-d", action='store_false')
    parser.add_argument("-o", default="./", help="output path for json and images")
    parser.add_argument("--newer-than", default=None, help='dd-mm-yy to set as the oldest date to scrape')
    args = parser.parse_args()

    scraper = Scraper(args.d, output_path=args.o)
    data = scraper.fetch_data(args.u, args.p, args.newer_than)
    data_json = json.dumps(data, indent=4)

    with open(os.path.join(args.o,'data.json'), 'w') as f:
        f.write(data_json)
    print("done")

if __name__ == '__main__':
    sys.exit(main())
