"""
Run this script ONCE to log in manually to Alibaba.
After you log in, press ENTER in the console and it will save fresh cookies.
"""
import os
import sys
import json
import time
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
        time.sleep(3)

        print("\n" + "="*70)
        print("  MANUAL LOGIN REQUIRED")
        print("  1. Click 'Sign in' on the Alibaba page that just opened.")
        print("  2. Log in with your email/password or any method.")
        print("  3. Once you are fully logged in (you see your account name),")
        print("     come back here and press ENTER.")
        print("="*70 + "\n")

        input("Press ENTER once you are logged in...")

        # Save cookies
        cookies = driver.get_cookies()
        with open(COOKIES_FILE, "w") as f:
            json.dump(cookies, f, indent=4)
        print(f"\n✅ Cookies saved to: {COOKIES_FILE}")
        print(f"   Total cookies saved: {len(cookies)}")
        print("\nYou can now run: python sheet_alibaba_inquiry.py")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
