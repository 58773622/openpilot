#!/usr/bin/env python3
import ssl
import subprocess
import urllib.error
import urllib.request
from email.utils import parsedate_to_datetime

URLS = [
  "http://worldtimeapi.org/api/timezone/Etc/UTC",
  "http://www.baidu.com",
  "http://www.qq.com",
  "https://www.google.com",
]


def get_time_from_http():
  ctx = ssl.create_default_context()
  ctx.check_hostname = False
  ctx.verify_mode = ssl.CERT_NONE

  for url in URLS:
    try:
      req = urllib.request.Request(url, method="GET")
      with urllib.request.urlopen(req, timeout=5, context=ctx) as resp:
        date_header = resp.headers.get("Date")
        if not date_header:
          continue
        dt = parsedate_to_datetime(date_header)
        return dt
    except (urllib.error.URLError, TimeoutError, ValueError):
      pass
    except Exception:
      pass

  return None


def set_system_time(dt):
  formatted = dt.strftime("%Y-%m-%d %H:%M:%S")
  try:
    subprocess.run(["sudo", "date", "-u", "-s", formatted], check=True)
    return True
  except Exception:
    return False


def main():
  dt = get_time_from_http()
  if dt is not None:
    set_system_time(dt)


if __name__ == "__main__":
  main()
