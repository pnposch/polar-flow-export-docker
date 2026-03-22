import argparse
import os
import re
import requests
import sys
from datetime import date
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

FLOW_URL = "https://flow.polar.com"


def validate_env():
    required = ["POLAR_USER", "POLAR_PASS", "SELENIUM_HOST", "SELENIUM_PORT"]
    missing = [v for v in required if not os.environ.get(v)]
    if missing:
        sys.exit(f"Error: missing required environment variables: {', '.join(missing)}")


def build_driver(headless=True):
    chrome_options = Options()
    if headless:
        chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--no-sandbox")
    selenium_host = os.environ["SELENIUM_HOST"]
    selenium_port = os.environ["SELENIUM_PORT"]
    return webdriver.Remote(
        command_executor=f"http://{selenium_host}:{selenium_port}/wd/hub",
        options=chrome_options,
    )


def login(driver, username, password):
    driver.get(f"{FLOW_URL}/flowSso/login")
    driver.find_element(By.ID, "username").send_keys(username)
    driver.find_element(By.ID, "password").send_keys(password)
    driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
    # Wait until SSO redirect completes (URL leaves the flowSso domain)
    WebDriverWait(driver, 30).until(lambda d: "flowSso" not in d.current_url)
    print("Logged in")


def get_exercise_ids(driver, year, month):
    try:
        driver.get(f"{FLOW_URL}/diary/{year}/month/{month}")
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_all_elements_located(
            (By.XPATH, "//div[@class='event event-month exercise']/a")
        ))
        elements = driver.find_elements(By.XPATH, "//div[@class='event event-month exercise']/a")
        hrefs = [e.get_attribute("href") or "" for e in elements]
        # Log first few hrefs to help diagnose ID extraction issues
        if hrefs:
            print(f"  Sample hrefs: {hrefs[:3]}", file=sys.stderr)
        ids = []
        for href in hrefs:
            # Extract the last numeric segment from the URL path (robust vs prefix changes)
            m = re.search(r'/(\d+)(?:[/?#]|$)', href)
            if m:
                ids.append(m.group(1))
            else:
                print(f"  Warning: could not extract ID from href: {href!r}", file=sys.stderr)
        print(f"Found {len(ids)} exercise(s) for {year}/{month:02d}")
        return ids
    except Exception as e:
        print(f"No exercises found for {year}/{month:02d}: {e}")
        return []


def load_ids(output_dir):
    ids_file = os.path.join(output_dir, "ids.txt")
    try:
        with open(ids_file) as f:
            return set(f.read().splitlines())
    except FileNotFoundError:
        return set()
    except OSError as e:
        sys.exit(f"Error: cannot read {ids_file}: {e}\nEnsure the output directory exists and is writable.")


def save_ids(output_dir, ids):
    with open(os.path.join(output_dir, "ids.txt"), "w") as f:
        f.write("\n".join(sorted(ids)))


def load_completed_months(output_dir):
    path = os.path.join(output_dir, "completed_months.txt")
    try:
        with open(path) as f:
            return set(line.strip() for line in f if line.strip())
    except FileNotFoundError:
        return set()


def save_completed_month(output_dir, year_month, completed):
    completed.add(year_month)
    with open(os.path.join(output_dir, "completed_months.txt"), "w") as f:
        f.write("\n".join(sorted(completed)))


def download_exercises(session, exercise_ids, existing_ids, output_dir):
    new_ids = [eid for eid in exercise_ids if eid not in existing_ids]
    skipped = len(exercise_ids) - len(new_ids)
    if skipped:
        print(f"Skipping {skipped} already-downloaded exercise(s)")
    downloaded, failed = [], []
    for ex_id in new_ids:
        try:
            url = f"{FLOW_URL}/api/export/training/tcx/{ex_id}?compress=false"
            r = session.get(url)
            r.raise_for_status()
            match = re.search(r'filename="([\w._-]+)"', r.headers.get("Content-Disposition", ""))
            if not match:
                raise ValueError(f"missing Content-Disposition filename for exercise {ex_id}")
            filename = match.group(1)
            with open(os.path.join(output_dir, filename), "w") as f:
                f.write(r.text)
            print(f"Downloaded {filename}")
            downloaded.append(ex_id)
        except Exception as e:
            print(f"Error downloading exercise {ex_id}: {e}", file=sys.stderr)
            failed.append(ex_id)
    return downloaded, failed


def month_range(start: date, end: date):
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        yield y, m
        m += 1
        if m > 12:
            m, y = 1, y + 1


def parse_args():
    today = date.today()
    parser = argparse.ArgumentParser(
        description="Export Polar Flow training sessions as TCX files"
    )
    parser.add_argument(
        "--start", metavar="YYYY-MM",
        default=f"{today.year}-{today.month:02d}",
        help="First month to export (default: current month)",
    )
    parser.add_argument(
        "--end", metavar="YYYY-MM",
        default=f"{today.year}-{today.month:02d}",
        help="Last month to export (default: current month)",
    )
    parser.add_argument(
        "--output-dir", default="/data",
        help="Directory to write TCX files to (default: /data)",
    )
    parser.add_argument(
        "--no-headless", action="store_true",
        help="Disable headless mode (shows the browser — useful for debugging)",
    )
    # Legacy positional support: polar-export.py <month> <year>
    parser.add_argument("month_pos", nargs="?", help=argparse.SUPPRESS)
    parser.add_argument("year_pos", nargs="?", help=argparse.SUPPRESS)
    return parser.parse_args()


def main():
    validate_env()
    args = parse_args()
    output_dir = args.output_dir
    os.makedirs(output_dir, exist_ok=True)

    if args.month_pos and args.year_pos:
        m, y = int(args.month_pos), int(args.year_pos)
        start = end = date(y, m, 1)
    else:
        try:
            start = date.fromisoformat(args.start + "-01")
            end = date.fromisoformat(args.end + "-01")
        except ValueError as e:
            sys.exit(f"Error: invalid date format — {e}")
        if start > end:
            sys.exit("Error: --start must not be after --end")

    username = os.environ["POLAR_USER"]
    password = os.environ["POLAR_PASS"]
    print(f"Exporting {start.strftime('%Y-%m')} → {end.strftime('%Y-%m')} as {username}")

    driver = build_driver(headless=not args.no_headless)
    print("Chrome initialized")
    all_failed = []
    today_ym = date.today().strftime("%Y-%m")
    try:
        existing_ids = load_ids(output_dir)
        completed = load_completed_months(output_dir)
        login(driver, username, password)

        for year, month in month_range(start, end):
            ym = f"{year}-{month:02d}"
            # Skip months already fully downloaded, except the current month
            # (which may have new exercises added since last run)
            if ym in completed and ym != today_ym:
                print(f"Skipping {ym} (already completed)")
                continue

            exercise_ids = get_exercise_ids(driver, year, month)
            if not exercise_ids:
                # Empty month — mark as complete so we don't revisit
                save_completed_month(output_dir, ym, completed)
                continue
            # Refresh cookies from the driver before each batch of downloads
            session = requests.Session()
            for cookie in driver.get_cookies():
                session.cookies.set(cookie["name"], cookie["value"])
            # Mirror the browser's User-Agent and Referer so Polar doesn't reject the request
            user_agent = driver.execute_script("return navigator.userAgent")
            session.headers.update({
                "User-Agent": user_agent,
                "Referer": FLOW_URL + "/",
            })
            downloaded, failed = download_exercises(session, exercise_ids, existing_ids, output_dir)
            existing_ids.update(downloaded)
            save_ids(output_dir, existing_ids)
            all_failed.extend(failed)
            # Only mark the month complete when every exercise succeeded
            if not failed and ym != today_ym:
                save_completed_month(output_dir, ym, completed)
    finally:
        driver.quit()

    if all_failed:
        print(f"\n{len(all_failed)} exercise(s) failed:", file=sys.stderr)
        for fid in all_failed:
            print(f"  {fid}", file=sys.stderr)
        sys.exit(1)
    print("Done.")


if __name__ == "__main__":
    main()