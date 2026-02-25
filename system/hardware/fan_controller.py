#!/usr/bin/env python3
from abc import ABC, abstractmethod

from openpilot.common.realtime import DT_HW
from openpilot.common.numpy_fast import interp
from openpilot.common.swaglog import cloudlog
from openpilot.selfdrive.controls.lib.pid import PIDController
from openpilot.common.params import Params

params = Params()


class BaseFanController(ABC):
  @abstractmethod
  def update(self, cur_temp: float, ignition: bool) -> int:
    pass


class TiciFanController(BaseFanController):
  def __init__(self) -> None:
    super().__init__()
    cloudlog.info("Setting up TICI fan handler")

    self.last_ignition = False
    self.controller = PIDController(k_p=0, k_i=4e-3, k_f=1, rate=(1 / DT_HW))

  def update(self, cur_temp: float, ignition: bool) -> int:
    # Configure PID limits based on ignition state
    self.controller.neg_limit = -(100 if ignition else 30)
    self.controller.pos_limit = -(30 if ignition else 0)

    if ignition != self.last_ignition:
      self.controller.reset()

    # Read quiet fan toggle from params so UI changes take effect quickly
    quiet_fan = params.get_bool("QuietFan")

    if quiet_fan:
      # Quiet mode: simple linear mapping with capped max power to reduce noise
      fan_pwr_out = int(interp(cur_temp, [60.0, 80.0], [0.0, 65.0]))
      fan_pwr_out = max(0, min(65, fan_pwr_out))
    else:
      # Default: PID-based control with full fan speed available
      error = 70 - cur_temp
      fan_pwr_out = -int(self.controller.update(
                        error=error,
                        feedforward=interp(cur_temp, [60.0, 100.0], [0, -100])
                      ))

    self.last_ignition = ignition
    return fan_pwr_out
