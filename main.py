
from selenium import webdriver
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC

import os, json, sys, argparse, time, pathlib

getGecko_installed = True
try:
    from get_gecko_driver import GetGeckoDriver
except BaseException:
    getGecko_installed = False

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
            "Mai": 5,
            "Jun": 6,
            "Jul": 7,
            "Aug": 8,
            "Sep": 9,
            "Oct": 10,
            "Nov": 11,
            "Dec": 12
        }

    def fetch_data(self, USERNAME: str, PASSWORD: str) -> dict:

        # use the installed GeckoDriver with Selenium
        fireFoxOptions = webdriver.FirefoxOptions()
        fireFoxOptions.headless = not self.DEBUG
        driver = webdriver.Firefox(options=fireFoxOptions)

        driver.get(self.MB_URL)

        # login
        driver.find_element_by_id("loginDropdown").click()
        driver.find_element_by_id("Login_Username").send_keys(USERNAME)
        driver.find_element_by_id("Login_Password").send_keys(PASSWORD)
        driver.find_element_by_id("navlogin").click()

        WebDriverWait(
            driver, 10).until(
            EC.presence_of_element_located(
                (By.ID, "navlogin")))
        #WebDriverWait(browser, 10).until(EC.presence_of_element_located((By.ID, "element_id")))
        time.sleep(10)
        # navigate to logbook
        # driver.get("https://moonboard.com/Logbook/Index")
        driver.find_element_by_id("llogbook").click()
        driver.find_element_by_link_text("VIEW").click()

        time.sleep(10)  # TODO: await properly

        # select version
        select = Select(driver.find_element_by_id("Holdsetup"))
        select.select_by_index(3)  # 2019 version TODO : more stable

        time.sleep(5)  # TODO: await properly

        main_section = driver.find_element_by_id("main-section")

        # get headers for rows
        headers = main_section.find_elements_by_class_name(
            "logbook-grid-header")

        # get a tag expanders for the various days
        expanders = driver.find_elements_by_xpath(
            "//a[@class='k-icon k-i-expand']")
        # Lag
        time.sleep(3)

        # create list of elements
        res = []
        def any_nested(list, key): return any([k == key for k, _, _ in list])
        
        for a_tag, header in zip(expanders, headers):
            a_tag.click()  # expand information for that day
            # Lag
            time.sleep(1)

        entries = main_section.find_elements_by_class_name("entry")
        entry_text = [e.text.split('\n')[0] for e in entries]

        unique_entries = [(entries[i],entry_text[i]) for i in range(1, len(entries)) 
                            if i==1 or (entry_text[i] != entry_text[i-1])]
        

        print(f"#Entries: {len(unique_entries)} Problems:{' '.join([e[1] for e in unique_entries])}")
        for entry,entry_name in unique_entries:
            # Get screenshot
            entry.click()
            time.sleep(1)
            img_path = os.path.join(self.IMAGE_PATH,entry_name.replace(" ","_")+".png")
            if not os.path.isfile(img_path):
                driver.get_screenshot_as_file(img_path)       
            
            # get data
            if not any_nested(res, entry.text):
                res_entry = (entry.text, header.text, img_path)  # (route info, date)
                res.append(res_entry)

        # process data
        formatted_data = []
        for (data, date, img_name) in res:
            data_arr = data.split('\n')
            day, month, year = date.split('\n')[0].split(' ')
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
    args = parser.parse_args()

    scraper = Scraper(args.d, output_path=args.o)
    data = scraper.fetch_data(args.u, args.p)
    data_json = json.dumps(data, indent=4)

    with open(os.path.join(args.o,'data.json'), 'w') as f:
        f.write(data_json)
    print("done")

if __name__ == '__main__':
    sys.exit(main())
