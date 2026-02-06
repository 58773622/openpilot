#!/usr/bin/env python3
import time
import json
import jwt
import random
import string
from pathlib import Path

from datetime import datetime, timedelta
from openpilot.common.api import api_get
from openpilot.common.params import Params
from openpilot.common.spinner import Spinner
from openpilot.selfdrive.controls.lib.alertmanager import set_offroad_alert
from openpilot.system.hardware import HARDWARE, PC
from openpilot.system.hardware.hw import Paths
from openpilot.common.swaglog import cloudlog


UNREGISTERED_DONGLE_ID = "UnregisteredDevice"


def is_registered_device() -> bool:
  dongle = Params().get("DongleId", encoding='utf-8')
  return dongle not in (None, UNREGISTERED_DONGLE_ID)


def register(show_spinner=False) -> str | None:
  params = Params()

  IMEI = params.get("IMEI", encoding='utf8')
  HardwareSerial = params.get("HardwareSerial", encoding='utf8')
  dongle_id: str | None = params.get("DongleId", encoding='utf8')
  needs_registration = None in (IMEI, HardwareSerial, dongle_id)
  needs_registration |= dongle_id == UNREGISTERED_DONGLE_ID

  pubkey = Path(Paths.persist_root()+"/comma/id_rsa.pub")
  if not pubkey.is_file():
    dongle_id = UNREGISTERED_DONGLE_ID
    cloudlog.warning(f"missing public key: {pubkey}")
  elif needs_registration:
    if show_spinner:
      spinner = Spinner()
      spinner.update("skyunlock registering device")

    # Create registration token, in the future, this key will make JWTs directly
    with open(Paths.persist_root()+"/comma/id_rsa.pub") as f1, open(Paths.persist_root()+"/comma/id_rsa") as f2:
      public_key = f1.read()
      private_key = f2.read()

    # Block until we get the imei, but don't loop forever. On hardware without a
    # modem (e.g. C3 Lite) the IMEI may never be available, but the backend can
    # still register the device using other identifiers. After a timeout, stop
    # trying to read the IMEI and continue the online registration step without it.
    serial = HARDWARE.get_serial()
    if show_spinner:
      spinner.update(f"skyunlock registering device - serial: {serial}")
    start_time = time.monotonic()
    imei1: str | None = None
    imei2: str | None = None
    while imei1 is None and imei2 is None:
      try:
        imei1, imei2 = HARDWARE.get_imei(0), HARDWARE.get_imei(1)
      except Exception:
        cloudlog.exception("Error getting imei, trying again...")
        time.sleep(1)

      elapsed = time.monotonic() - start_time
      if elapsed > 60:
        cloudlog.warning("IMEI unavailable after 60s, continuing registration without IMEI")
        if show_spinner:
          spinner.update(f"skyunlock registering device - serial: {serial}, IMEI: (unavailable)")
        break

      if show_spinner:
        spinner.update(f"skyunlock registering device - serial: {serial}, IMEI: ({imei1}, {imei2})")

    if dongle_id != UNREGISTERED_DONGLE_ID:
      if imei1 is not None and imei1 != "":
        params.put("IMEI", imei1)
      params.put("HardwareSerial", serial)

      backoff = 0
      # overall timeout for online registration attempts (to avoid blocking forever when there's no internet)
      reg_start_time = time.monotonic()
      max_offline_time_s = 60
      while True:
        try:
          register_token = jwt.encode({'register': True, 'exp': datetime.utcnow() + timedelta(hours=1)}, private_key, algorithm='RS256')
          cloudlog.info("getting pilotauth")
          resp = api_get("v2/pilotauth/", method='POST', timeout=15,
                         imei=imei1, imei2=imei2, serial=serial, public_key=public_key, register_token=register_token)

          if resp.status_code == 200:
            dongleauth = json.loads(resp.text)
            dongle_id = dongleauth["dongle_id"]
            break

          if resp.status_code in (402, 403):
            error_msg = None
            try:
              error_msg = resp.json().get("error")
            except Exception:
              error_msg = None

            if isinstance(error_msg, str) and "not whitelisted" in error_msg:
              cloudlog.info(f"device not whitelisted on skyunlock server, waiting for approval: serial={serial}, imei={imei1}")
              if show_spinner:
                if imei1 is None and imei2 is None:
                  imei_text = "unavailable"
                else:
                  imei_text = f"({imei1}, {imei2})"
                spinner.update(f"skyunlock waiting approval - serial: {serial}, IMEI: {imei_text}, 请联系卖家开通注册权限")
              time.sleep(5)
              continue

            cloudlog.info(f"Unable to register device, got {resp.status_code}: {error_msg}")
            dongle_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=16))
            break

          cloudlog.info(f"Unexpected pilotauth status code: {resp.status_code}")
        except Exception:
          cloudlog.exception("failed to authenticate")
          backoff = min(backoff + 1, 15)
          # if we've been failing due to network issues for too long, fall back to an unregistered device ID
          elapsed = time.monotonic() - reg_start_time
          if elapsed > max_offline_time_s:
            cloudlog.warning(f"registration network timeout after {elapsed:.0f}s, using UNREGISTERED_DONGLE_ID and continuing offline")
            dongle_id = UNREGISTERED_DONGLE_ID
            break
          time.sleep(backoff)

    if show_spinner:
      spinner.close()

  if dongle_id:
    params.put("DongleId", dongle_id)
    set_offroad_alert("Offroad_UnofficialHardware", (dongle_id == UNREGISTERED_DONGLE_ID) and not PC)
  return dongle_id


if __name__ == "__main__":
  print(register())
