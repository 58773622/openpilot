#!/usr/bin/env python3
import ssl
import subprocess
import urllib.error
import urllib.request
from email.utils import parsedate_to_datetime


# 优先使用 HTTP，避免因为本地时间错误导致 HTTPS 证书校验失败；
# 仅将 HTTPS 作为最后的补充，并关闭证书校验（只用于校时）。
URLS = [
  "http://worldtimeapi.org/api/timezone/Etc/UTC",
  "http://www.baidu.com",
  "http://www.qq.com",
  "https://www.google.com",
]


def get_time_from_http():
  # 为 HTTPS 创建一个不校验证书的 SSL 上下文，仅用于时间同步
  ctx = ssl.create_default_context()
  ctx.check_hostname = False
  ctx.verify_mode = ssl.CERT_NONE

  for url in URLS:
    try:
      print(f"Trying HTTP time sync via {url} ...")
      req = urllib.request.Request(url, method="GET")
      with urllib.request.urlopen(req, timeout=5, context=ctx) as resp:
        date_header = resp.headers.get("Date")
        if not date_header:
          continue

        dt = parsedate_to_datetime(date_header)
        return dt
    except (urllib.error.URLError, TimeoutError, ValueError) as e:
      print(f"HTTP time sync failed for {url}: {e}")
    except Exception as e:
      print(f"Unexpected error during HTTP time sync for {url}: {e}")

  return None


def set_system_time(dt):
  # 使用 UTC，避免时区干扰；证书校验只关心绝对时间是否合理
  formatted = dt.strftime("%Y-%m-%d %H:%M:%S")
  try:
    subprocess.run(["sudo", "date", "-u", "-s", formatted], check=True)
    print(f"System time updated to {formatted} (UTC)")
    return True
  except Exception as e:
    print(f"Failed to set system time: {e}")
    return False


def main():
  print("FrogPilot: starting one-shot HTTP time sync at boot...")
  dt = get_time_from_http()
  if dt is not None and set_system_time(dt):
    return

  print("FrogPilot: time sync failed, continuing boot without correction.")


if __name__ == "__main__":
  main()
