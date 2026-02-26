#!/usr/bin/env python3
import math
from cereal import car
from openpilot.common.conversions import Conversions as CV
from opendbc.can.parser import CANParser
from openpilot.selfdrive.car.gm.values import DBC, CanBus
from openpilot.selfdrive.car.interfaces import RadarInterfaceBase

RADAR_HEADER_MSG = 1120
SLOT_1_MSG = RADAR_HEADER_MSG + 1
NUM_SLOTS = 20

# Actually it's 0x47f, but can parser only reports
# messages that are present in DBC
LAST_RADAR_MSG = RADAR_HEADER_MSG + NUM_SLOTS


def create_radar_can_parser(car_fingerprint):
  # C1A-ARS3-A by Continental
  radar_targets = list(range(SLOT_1_MSG, SLOT_1_MSG + NUM_SLOTS))
  signals = list(zip(['FLRRNumValidTargets',
                      'FLRRSnsrBlckd', 'FLRRYawRtPlsblityFlt',
                      'FLRRHWFltPrsntInt', 'FLRRAntTngFltPrsnt',
                      'FLRRAlgnFltPrsnt', 'FLRRSnstvFltPrsntInt'] +
                     ['TrkRange'] * NUM_SLOTS + ['TrkRangeRate'] * NUM_SLOTS +
                     ['TrkRangeAccel'] * NUM_SLOTS + ['TrkAzimuth'] * NUM_SLOTS +
                     ['TrkWidth'] * NUM_SLOTS + ['TrkObjectID'] * NUM_SLOTS,
                     [RADAR_HEADER_MSG] * 7 + radar_targets * 6, strict=True))

  # OEM vision signals from F_Vision object and environment messages
  # Object header
  signals += [
    ('ClstInPathVehObjID', 1056),
    ('FVisionNumValidTrgts', 1056),
    ('FrtVsnUnvlbl', 1056),
  ]

  # Object tracks (positions, types, widths, lanes, confidence)
  vision_track_msgs = [
    (1057, '1'),
    (1058, '2'),
    (1059, '3'),
    (1060, '4'),
    (1061, '5'),
    (1062, '6'),
    (1089, '7'),
    (1090, '8'),
    (1091, '9'),
    (1092, '10'),
  ]

  for msg, suffix in vision_track_msgs:
    signals += [
      (f'FVisionObjectIDTrk{suffix}', msg),
      (f'FwdVsnRngTrk{suffix}Rev', msg),
      (f'FwdVsnAzmthTrk{suffix}Rev', msg),
      (f'FVisionWidthTrk{suffix}', msg),
      (f'FVisionRelLaneTrk{suffix}', msg),
      (f'FVisionConfTrk{suffix}', msg),
      (f'FwdVsnObjTypTr{suffix}Rev', msg),
    ]

  # Lane and environment information
  signals += [
    # F_Vision_Environment (848)
    ('FwdVsnEnvIllum', 848),
    ('LaneSnsLLnPosValid', 848),
    ('LnSenseDistToLLnEdge', 848),
    ('LnSnsRLnPosValid', 848),
    ('LnSnsDistToRLnEdge', 848),
    ('LnSnsLnChngStatus', 848),
    # F_Vision_Environment_7 (854)
    ('FwdVsnCnstrctZnDet', 854),
    ('FwdVsnEgoVehLnPos', 854),
    ('FwdVsnRdTypDet', 854),
    ('FwdVsnTunnlDetd', 854),
  ]

  messages = list({(s[1], 14) for s in signals})

  return CANParser(DBC[car_fingerprint]['radar'], messages, CanBus.OBSTACLE)


class RadarInterface(RadarInterfaceBase):
  def __init__(self, CP):
    super().__init__(CP)

    self.rcp = None if CP.radarUnavailable else create_radar_can_parser(CP.carFingerprint)

    self.trigger_msg = LAST_RADAR_MSG
    self.updated_messages = set()
    self.radar_ts = CP.radarTimeStep

  def update(self, can_strings):
    if self.rcp is None:
      return super().update(None)

    vls = self.rcp.update_strings(can_strings)
    self.updated_messages.update(vls)

    if self.trigger_msg not in self.updated_messages:
      return None

    ret = car.RadarData.new_message()
    header = self.rcp.vl[RADAR_HEADER_MSG]
    fault = header['FLRRSnsrBlckd'] or header['FLRRSnstvFltPrsntInt'] or \
      header['FLRRYawRtPlsblityFlt'] or header['FLRRHWFltPrsntInt'] or \
      header['FLRRAntTngFltPrsnt'] or header['FLRRAlgnFltPrsnt']
    errors = []
    if not self.rcp.can_valid:
      errors.append("canError")
    if fault:
      errors.append("fault")
    ret.errors = errors

    currentTargets = set()
    num_targets = header['FLRRNumValidTargets']

    # Not all radar messages describe targets,
    # no need to monitor all of the self.rcp.msgs_upd
    for ii in self.updated_messages:
      if ii == RADAR_HEADER_MSG:
        continue

      if num_targets == 0:
        break

      # Only radar target slot messages contain tracking fields like TrkRange.
      # Skip any other updated messages (e.g. OEM vision / environment frames).
      if ii < SLOT_1_MSG or ii > LAST_RADAR_MSG:
        continue

      cpt = self.rcp.vl[ii]
      # Ensure required tracking fields are present before accessing them.
      if not all(k in cpt for k in ('TrkRange', 'TrkObjectID', 'TrkAzimuth', 'TrkRangeRate')):
        continue

      distance = cpt['TrkRange']
      # Zero distance means it's an empty target slot
      if distance > 0.0:
        targetId = cpt['TrkObjectID']
        currentTargets.add(targetId)
        if targetId not in self.pts:
          self.pts[targetId] = car.RadarData.RadarPoint.new_message()
          self.pts[targetId].trackId = targetId
        self.pts[targetId].dRel = distance  # from front of car
        # From driver's pov, left is positive
        self.pts[targetId].yRel = math.sin(cpt['TrkAzimuth'] * CV.DEG_TO_RAD) * distance
        self.pts[targetId].vRel = cpt['TrkRangeRate']
        self.pts[targetId].aRel = float('nan')
        self.pts[targetId].yvRel = float('nan')

    for oldTarget in list(self.pts.keys()):
      if oldTarget not in currentTargets:
        del self.pts[oldTarget]

    ret.points = list(self.pts.values())

    # OEM vision objects and lane data (if available)
    vision_points = []

    # Object header for in-path flag
    vision_header = self.rcp.vl.get(1056, {})
    in_path_id = vision_header.get('ClstInPathVehObjID', 0)
    num_vision_targets = int(vision_header.get('FVisionNumValidTrgts', 0))

    if num_vision_targets > 0:
      vision_track_msgs = [
        (1057, '1'),
        (1058, '2'),
        (1059, '3'),
        (1060, '4'),
        (1061, '5'),
        (1062, '6'),
        (1089, '7'),
        (1090, '8'),
        (1091, '9'),
        (1092, '10'),
      ]

      for msg, suffix in vision_track_msgs:
        if msg not in self.rcp.vl:
          continue
        vp = self.rcp.vl[msg]

        rng = float(vp.get(f'FwdVsnRngTrk{suffix}Rev', 0.0))
        if rng <= 0.0:
          continue

        az_deg = float(vp.get(f'FwdVsnAzmthTrk{suffix}Rev', 0.0))
        obj_id = int(vp.get(f'FVisionObjectIDTrk{suffix}', 0))
        width = float(vp.get(f'FVisionWidthTrk{suffix}', 0.0))
        rel_lane = int(vp.get(f'FVisionRelLaneTrk{suffix}', 0))
        conf_raw = float(vp.get(f'FVisionConfTrk{suffix}', 0.0))
        obj_type = int(vp.get(f'FwdVsnObjTypTr{suffix}Rev', 0))

        vision_pt = car.RadarData.VisionPoint.new_message()
        vision_pt.id = obj_id
        vision_pt.dRel = rng
        vision_pt.yRel = math.sin(az_deg * CV.DEG_TO_RAD) * rng
        vision_pt.vRel = 0.0  # longitudinal velocity not currently parsed
        vision_pt.width = width
        vision_pt.objectType = obj_type
        vision_pt.relLane = rel_lane
        vision_pt.brakeLight = 0
        vision_pt.turnSignal = 0
        vision_pt.confidence = conf_raw
        vision_pt.inPath = obj_id == in_path_id

        vision_points.append(vision_pt)

    ret.visionPoints = vision_points

    # Lane and environment state
    env = self.rcp.vl.get(848, {})
    env7 = self.rcp.vl.get(854, {})
    lane = ret.visionLane

    lane.leftValid = bool(env.get('LaneSnsLLnPosValid', 0))
    lane.rightValid = bool(env.get('LnSnsRLnPosValid', 0))
    lane.distToLeft = float(env.get('LnSenseDistToLLnEdge', 0.0))
    lane.distToRight = float(env.get('LnSnsDistToRLnEdge', 0.0))
    lane.egoLanePos = int(env7.get('FwdVsnEgoVehLnPos', 0))
    lane.roadType = int(env7.get('FwdVsnRdTypDet', 0))
    lane.laneChangeStatus = int(env.get('LnSnsLnChngStatus', 0))
    lane.tunnelDetected = int(env7.get('FwdVsnTunnlDetd', 0))
    lane.constrAreaDetected = int(env7.get('FwdVsnCnstrctZnDet', 0))
    lane.envIllum = int(env.get('FwdVsnEnvIllum', 0))
    self.updated_messages.clear()
    return ret
