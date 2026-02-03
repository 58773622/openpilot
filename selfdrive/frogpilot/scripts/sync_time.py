#!/usr/bin/env python3
import datetime
import subprocess
import requests
import time

def sync_time():
    print("FrogPilot: Attempting to sync time...")

    # 1. Try NTP if available (usually requires root)
    ntp_servers = ["pool.ntp.org", "time.google.com", "time.apple.com"]
    for server in ntp_servers:
        try:
            print(f"Trying NTP sync with {server}...")
            subprocess.run(["sudo", "ntpdate", "-u", server], check=True, timeout=10, capture_output=True)
            print("NTP sync successful.")
            return True
        except Exception:
            continue

    # 2. Fallback to HTTP time (WorldTimeAPI)
    try:
        print("Trying HTTP time sync via worldtimeapi.org...")
        response = requests.get("http://worldtimeapi.org/api/timezone/Etc/UTC", timeout=10)
        if response.status_code == 200:
            data = response.json()
            utc_datetime = data['datetime']
            # Format: 2023-11-21T21:17:00.123456+00:00
            # date -s expects "YYYY-MM-DD HH:MM:SS"
            dt = datetime.datetime.fromisoformat(utc_datetime)
            formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S")
            subprocess.run(["sudo", "date", "-s", formatted_time], check=True)
            print(f"HTTP sync successful: {formatted_time}")
            return True
    except Exception as e:
        print(f"HTTP sync failed: {e}")

    # 3. Fallback to Google Headers
    try:
        print("Trying HTTP time sync via Google...")
        response = requests.head("https://www.google.com", timeout=10)
        if 'Date' in response.headers:
            http_date = response.headers['Date']
            # Date format: Tue, 21 Nov 2023 21:17:00 GMT
            subprocess.run(["sudo", "date", "-s", http_date], check=True)
            print(f"Google HTTP sync successful: {http_date}")
            return True
    except Exception as e:
        print(f"Google HTTP sync failed: {e}")

    print("FrogPilot: Time sync failed after all attempts.")
    return False

if __name__ == "__main__":
    # Wait up to 30 seconds for network if needed
    for _ in range(3):
        if sync_time():
            break
        print("Waiting for network...")
        time.sleep(10)
