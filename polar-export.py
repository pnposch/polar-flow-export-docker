from selenium import webdriver
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import requests
import re
import time
import sys
import os
import json
from datetime import datetime

FLOW_URL = "https://flow.polar.com"
SELENIUM_HOST = os.environ["SELENIUM_HOST"]
SELENIUM_PORT = os.environ["SELENIUM_PORT"]
username = os.environ["POLAR_USER"]
password = os.environ["POLAR_PASS"]
month = datetime.now().month
year = datetime.now().year
output_dir = "/data"

chrome_options = Options()
chrome_options.add_argument("--headless") # disable to show whats happening
chrome_options.add_argument("--disable-extensions")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--disable-dev-shm-usage")
#chrome_options.add_argument("--remote-debugging-port=9222")  # this
chrome_options.add_argument("--no-sandbox") # needed in docker

print("Initialized using username %s" % (username))

def login(driver, username, password):
    driver.get("%s/flowSso/login" % FLOW_URL)
    driver.find_element(By.ID,"username").send_keys(username)
    driver.find_element(By.ID,"password").send_keys(password)
    driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
    print("Logged in")

def get_exercise_ids(driver, year, month):
    try:
        driver.get(f"{FLOW_URL}/diary/{year}/month/{month}")
        
        # Use WebDriverWait instead of time.sleep

        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_all_elements_located(
            (By.XPATH, "//div[@class='event event-month exercise']/a")
        ))
        
        # Get elements and extract IDs
        elements = driver.find_elements(By.XPATH, "//div[@class='event event-month exercise']/a")
        prefix = "https://flow.polar.com/training/analysis2/"
        ids = [e.get_attribute("href")[len(prefix):] for e in elements]
        
        print(f"Exercise List downloaded with {len(ids)} id's")
        
        # Write new IDs to file
        write_new_ids(ids)
        return ids
        
    except Exception as e:
        print(f"Error fetching exercise IDs: {e}")
        return []


def _load_cookies(session, cookies):
    for cookie in cookies:
        session.cookies.set(cookie['name'], cookie['value'])

def initialize_local_tcxs():
    try:
        with open(os.path.join(output_dir, "ids.txt"), 'r') as infile:
            existing_ids = infile.read().splitlines()
    except IOError as e:
        print(f"Error reading file: {e}")
        existing_ids = []
    return existing_ids

def write_new_ids(newids):
    oldids = initialize_local_tcxs()
    ids = list ( set(newids+oldids) )
    with open(os.path.join(output_dir, "ids.txt"), 'w') as outfile:
        outfile.write("\n".join(ids))

if __name__ == "__main__":
    try:
        (month, year) = sys.argv[1:]
    except ValueError:
        sys.stderr.write(("You can provide: %s <month> <year> here or in ENV \n") % sys.argv[0])
    print("Fetching %s / %s" % (month, year))


    #driver = webdriver.Chrome(options=chrome_options)
    driver = webdriver.Remote(
        command_executor='http://%s:%s/wd/hub' % (SELENIUM_HOST, SELENIUM_PORT),
        #desired_capabilities=DesiredCapabilities.CHROME,
        options=chrome_options
    )
    print("Chrome initialized")
    try:
        existing_ids = initialize_local_tcxs() #do this first
        login(driver, username, password)
        time.sleep(5)
        exercise_ids = get_exercise_ids(driver, year, month) #list gets updated by this process
        print(f"We got  {len(exercise_ids)} total online and {len(existing_ids)} locally")
        s = requests.Session()
        _load_cookies(s, driver.get_cookies())

        for ex_id in exercise_ids:
            r = s.get("%s/api/export/training/tcx/%s" % (FLOW_URL, ex_id))
            filename = re.search(r"filename=\"([\w._-]+)\"", r.headers['Content-Disposition']).group(1)
            with open(os.path.join(output_dir, filename), 'w') as outfile:
                outfile.write(r.text)
            print("Wrote file %s" % filename)

    finally:
        driver.quit()
        print("Finished with %s / %s" % (month, year) )