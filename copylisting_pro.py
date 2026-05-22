import subprocess
import sys
import os
import json
import time
import random
import psutil
import shutil
import logging
from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
import undetected_chromedriver as uc

# --- Configuration ---
SEARCH_TERM = ""  # Set this to a model number if you only want to copy ONE specific product
TARGET_COUNT = 5   # Number of products from the list to copy
COPIES_PER_PRODUCT = 2

# --- Setup Logging ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "automation_pro.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8"), logging.StreamHandler(sys.stdout)]
)

def log_step(msg, delay=0):
    logging.info(msg)
    if delay > 0: time.sleep(delay)

# --- Helper Functions ---
def wait_el(driver, selectors, timeout=20):
    start = time.time()
    while time.time() - start < timeout:
        for selector in selectors:
            try:
                el = driver.find_element(*selector)
                if el.is_displayed(): return el
            except: pass
        time.sleep(1)
    return None

def safe_click(driver, el):
    try:
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
        time.sleep(0.5)
        el.click()
    except:
        driver.execute_script("arguments[0].click();", el)

def start_browser():
    options = uc.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    # Kill any existing chrome processes to prevent locking
    for proc in psutil.process_iter(['name']):
        if proc.info['name'] == 'chrome.exe' or proc.info['name'] == 'chromedriver.exe':
            try: proc.terminate()
            except: pass
    time.sleep(2)
    driver = uc.Chrome(options=options)
    return driver

def login(driver):
    COOKIES_FILE = os.path.join(BASE_DIR, "cookies.json")
    driver.get("https://i.alibaba.com/products/list-manage#/product/all")
    time.sleep(5)
    if os.path.exists(COOKIES_FILE):
        with open(COOKIES_FILE) as f:
            cookies = json.load(f)
        for c in cookies:
            try: driver.add_cookie(c)
            except: pass
        logging.info("Cookies loaded.")
    driver.get("https://i.alibaba.com/products/list-manage#/product/all")
    time.sleep(10)

def set_model_number(driver, model_number):
    if not model_number: return
    log_step(f"[MODEL] Forcing model number: {model_number}")
    inp = wait_el(driver, [
        (By.CSS_SELECTOR, 'input[name="modelNumber"]'),
        (By.XPATH, '//div[contains(text(),"Model Number")]/following-sibling::div//input'),
        (By.CSS_SELECTOR, 'input[placeholder*="Model Number"]'),
    ], timeout=15)
    if inp:
        try:
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", inp)
            inp.click()
            inp.send_keys(Keys.CONTROL + "a")
            inp.send_keys(Keys.BACKSPACE)
            time.sleep(0.5)
            inp.send_keys(model_number)
            inp.send_keys(Keys.TAB)
            driver.execute_script("arguments[0].value = arguments[1];", inp, model_number)
            driver.execute_script("arguments[0].dispatchEvent(new Event('input', {bubbles:true}));", inp)
            return True
        except Exception as e:
            logging.warning(f"Failed to set model number: {e}")
    return False

def process_video(driver, model_number):
    try:
        btn = wait_el(driver, [(By.CSS_SELECTOR, '.uploader-video-not-select-buttons button'), (By.XPATH, '//div[text()="Under 10 minutes (up to 500 MB)"]')], 10)
        if not btn: return
        safe_click(driver, btn)
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        if iframes:
            driver.switch_to.frame(iframes[-1])
            inp = wait_el(driver, [(By.CSS_SELECTOR, 'input[placeholder*="Video"], input[placeholder*="name"]')], 10)
            if inp:
                inp.clear()
                inp.send_keys(model_number)
                inp.send_keys(Keys.ENTER)
                time.sleep(8)
                select_btns = driver.find_elements(By.XPATH, '//span[contains(text(),"Select")]')
                if select_btns: safe_click(driver, select_btns[0])
            driver.switch_to.default_content()
    except: driver.switch_to.default_content()

def copy_products(driver):
    if SEARCH_TERM:
        log_step(f"Searching for specific model: {SEARCH_TERM}")
        search_inp = wait_el(driver, [(By.CSS_SELECTOR, 'input[placeholder*="Enter product model"]') or (By.CSS_SELECTOR, 'input[placeholder*="model"]')], 15)
        if search_inp:
            search_inp.clear()
            search_inp.send_keys(SEARCH_TERM)
            search_inp.send_keys(Keys.ENTER)
            time.sleep(5)

    log_step("Scanning list for products...", 10)
    rows = driver.find_elements(By.CSS_SELECTOR, '[data-component="component-market-list-item"], tr.next-table-row')
    target_data = []
    
    today_str = datetime.now().strftime("%d/%m/%Y")
    logging.info(f"Today is {today_str}. Will skip products updated today to avoid copying copies.")

    for row in rows:
        try:
            # Skip if updated today (prevents infinite loop of copying copies)
            try:
                date_text = row.find_element(By.CSS_SELECTOR, "td:nth-child(3), .product-update-time").text
                if today_str in date_text:
                    logging.info(f"Skipping product updated today: {date_text}")
                    continue
            except: pass

            id_text = row.find_element(By.CSS_SELECTOR, ".product-id, div[class*='id']").text
            pid = id_text.split(":")[-1].strip()
            model_text = row.find_element(By.CSS_SELECTOR, ".product-model, span[class*='model']").text
            # Clean up the model text (remove 'undefined', 'model:', etc.)
            model = model_text.lower().replace("undefined", "").replace("model:", "").replace("model", "").replace(":", "").strip().upper()
            
            if model and pid:
                target_data.append({"id": pid, "model": model})
                if len(target_data) >= TARGET_COUNT: break
        except: pass

    if not target_data:
        logging.error("No valid products found to copy. Check if they were all updated today.")
        return

    logging.info(f"Targets locked: {[t['model'] for t in target_data]}")
    main_handle = driver.current_window_handle

    for item in target_data:
        pid, model = item['id'], item['model']
        for copy_num in range(1, COPIES_PER_PRODUCT + 1):
            try:
                logging.info(f"--- Duplicating {model} (Copy {copy_num}/{COPIES_PER_PRODUCT}) ---")
                driver.switch_to.window(main_handle)
                url = f"https://post.alibaba.com/product/publish.htm?pubType=similarPost&itemId={pid}&behavior=copyNew/"
                driver.execute_script(f"window.open('{url}','_blank');")
                time.sleep(5)
                
                # Robust tab switching
                found_tab = False
                for handle in driver.window_handles:
                    if handle != main_handle:
                        driver.switch_to.window(handle)
                        if "post.alibaba.com" in driver.current_url:
                            found_tab = True
                            break
                if not found_tab:
                    logging.error("Failed to find duplication tab.")
                    continue

                log_step("Waiting for publish page...", 20)
                
                # AI Optimization
                title_opt = wait_el(driver, [(By.XPATH, '//button[contains(.,"Title optimization")]')], 15)
                if title_opt:
                    safe_click(driver, title_opt)
                    time.sleep(15)
                    apply = wait_el(driver, [(By.XPATH, '//button[contains(.,"Apply")]')], 10)
                    if apply: safe_click(driver, apply)

                # Image Bank
                img_bank = wait_el(driver, [(By.XPATH, "//button[contains(.,'Use image bank')]")], 10)
                if img_bank:
                    safe_click(driver, img_bank)
                    time.sleep(5)
                    iframes = driver.find_elements(By.TAG_NAME, "iframe")
                    if iframes:
                        driver.switch_to.frame(iframes[-1])
                        search = wait_el(driver, [(By.CSS_SELECTOR, 'input[placeholder*="Search"], input[placeholder*="搜索"]')], 10)
                        if search:
                            search.clear()
                            search.send_keys(model)
                            search.send_keys(Keys.ENTER)
                            time.sleep(10)
                            imgs = driver.find_elements(By.CSS_SELECTOR, 'img[src*="kf/"], .image-item img')
                            for img in imgs[:5]: safe_click(driver, img)
                            confirm = wait_el(driver, [(By.ID, "confirm")], 5)
                            if confirm: safe_click(driver, confirm)
                    driver.switch_to.default_content()

                process_video(driver, model)
                set_model_number(driver, model)

                submit = wait_el(driver, [(By.XPATH, '//button[contains(@class, "header-submit-button")]'), (By.XPATH, '//button[contains(text(),"Submit")]')], 15)
                if submit:
                    safe_click(driver, submit)
                    log_step("Submitted. Closing tab...", 10)
                
                driver.close()
                driver.switch_to.window(main_handle)
            except Exception as e:
                logging.error(f"Error processing {model}: {e}")
                try:
                    if len(driver.window_handles) > 1:
                        driver.close()
                        driver.switch_to.window(main_handle)
                except: pass

def main():
    driver = None
    try:
        driver = start_browser()
        login(driver)
        copy_products(driver)
        logging.info("PROCESS COMPLETE.")
    except Exception as e:
        logging.critical(f"FATAL CRASH: {e}")
    finally:
        if driver: driver.quit()

if __name__ == "__main__":
    main()
