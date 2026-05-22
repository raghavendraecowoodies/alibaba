import os
import time
import json
import psutil
import undetected_chromedriver as uc

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COOKIES_FILE = os.path.join(BASE_DIR, "cookies.json")

def clean_chrome_processes():
    for proc in psutil.process_iter(['name']):
        try:
            if proc.info['name'] in ('chrome.exe', 'chromedriver.exe'):
                proc.terminate()
        except:
            pass
    time.sleep(2)

def main():
    clean_chrome_processes()
    options = uc.ChromeOptions()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")
    driver = uc.Chrome(options=options)
    
    try:
        driver.get("https://www.alibaba.com/")
        time.sleep(4)
        if os.path.exists(COOKIES_FILE):
            with open(COOKIES_FILE, "r") as f:
                cookies = json.load(f)
            for c in cookies:
                try:
                    driver.add_cookie(c)
                except:
                    pass
            print("Cookies loaded!")
            driver.get("https://www.alibaba.com/")
            time.sleep(5)
            
        driver.save_screenshot(os.path.join(BASE_DIR, "alibaba_homepage.png"))
        print("Screenshot saved to alibaba_homepage.png")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
