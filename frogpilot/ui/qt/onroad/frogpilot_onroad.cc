#include "frogpilot/ui/qt/onroad/frogpilot_onroad.h"

FrogPilotOnroadWindow::FrogPilotOnroadWindow(QWidget *parent) : QWidget(parent) {
  signalTimer = new QTimer(this);

  QObject::connect(signalTimer, &QTimer::timeout, [this] {
    flickerActive = !flickerActive;
  });
}

void FrogPilotOnroadWindow::updateState(const UIState &s, const FrogPilotUIState &fs) {
  QJsonObject &frogpilot_toggles = fs.frogpilot_toggles;
  SubMaster &fpsm = *(fs.sm);

  const SubMaster &sm = *(s.sm);
  const UIScene &scene = s.scene;

  isMetricUnits = scene.is_metric || frogpilot_toggles.value("use_si_metrics").toBool();

  const cereal::CarState::Reader &carState = fpsm["carState"].getCarState();
  const cereal::CarControl::Reader &carControl = fpsm["carControl"].getCarControl();

  // Current gear label (P/R/N/D/S/L/ECO/M). Gear number (D1, D2, etc.) is not available from CarState.
  switch (carState.getGearShifter()) {
    case cereal::CarState::GearShifter::PARK:
      gearLabel = "P";
      break;
    case cereal::CarState::GearShifter::REVERSE:
      gearLabel = "R";
      break;
    case cereal::CarState::GearShifter::NEUTRAL:
      gearLabel = "N";
      break;
    case cereal::CarState::GearShifter::DRIVE:
      gearLabel = "D";
      break;
    case cereal::CarState::GearShifter::SPORT:
      gearLabel = "S";
      break;
    case cereal::CarState::GearShifter::LOW:
      gearLabel = "L";
      break;
    case cereal::CarState::GearShifter::ECO:
      gearLabel = "E";
      break;
    case cereal::CarState::GearShifter::MANUMATIC:
      gearLabel = "M";
      break;
    default:
      gearLabel.clear();
      break;
  }

  // Lead distance & headway (from RadarState lead one)
  hasLead = false;
  headwayS = 0.0;
  leadDistanceM = 0.0;
  leadSpeed = 0.0;
  if (sm.alive("radarState") && sm["radarState"].getValid()) {
    const auto &radarState = sm["radarState"].getRadarState();
    auto lead_one = radarState.getLeadOne();
    if (lead_one.getStatus()) {
      float d_rel = lead_one.getDRel();
      float v_lead = std::max(lead_one.getVLead(), 0.0f);
      float v_ego = std::max(carState.getVEgo(), 0.0f);

      leadDistanceM = d_rel;
      float denom = std::max(v_ego, 1.0f);
      headwayS = d_rel / denom;
      leadSpeed = v_lead;
      hasLead = true;
    }
  }

  blindSpotLeft = carState.getLeftBlindspot();
  blindSpotRight = carState.getRightBlindspot();
  steer = -carControl.getActuators().getSteer();
  turnSignalLeft = carState.getLeftBlinker();
  turnSignalRight = carState.getRightBlinker();

  // Device metrics: memory usage & CPU temperature
  const auto deviceState = sm["deviceState"].getDeviceState();
  memoryUsage = deviceState.getMemoryUsagePercent();
  cpuTempC = deviceState.getMaxTempC();

  showBlindspot = (blindSpotLeft || blindSpotRight) && frogpilot_toggles.value("blind_spot_metrics").toBool();
  showFPS = frogpilot_toggles.value("show_fps").toBool();
  showSignal = (turnSignalLeft || turnSignalRight) && frogpilot_toggles.value("signal_metrics").toBool();
  showSteering = frogpilot_toggles.value("steering_metrics").toBool();

  // Always repaint the overlay so the bottom status bar stays live.
  update();
}

void FrogPilotOnroadWindow::paintEvent(QPaintEvent *event) {
  QPainter p(this);
  p.setRenderHints(QPainter::Antialiasing | QPainter::TextAntialiasing);

  QRect rect = this->rect();

  QRegion marginRegion;
  marginRegion += QRegion(0, 0, rect.width(), UI_BORDER_SIZE);
  marginRegion += QRegion(0, rect.height() - UI_BORDER_SIZE, rect.width(), UI_BORDER_SIZE);
  marginRegion += QRegion(0, UI_BORDER_SIZE, UI_BORDER_SIZE, rect.height() - 2 * UI_BORDER_SIZE);
  marginRegion += QRegion(rect.width() - UI_BORDER_SIZE, UI_BORDER_SIZE, UI_BORDER_SIZE, rect.height() - 2 * UI_BORDER_SIZE);
  p.setClipRegion(marginRegion);

  if (showSteering) {
    paintSteeringTorqueBorder(p, rect);
  }

  if (showBlindspot || showSignal) {
    int interval = showBlindspot ? 250 : 500;

    if (!signalTimer->isActive()) {
      signalTimer->start(interval);
    } else if (signalTimer->interval() != interval) {
      signalTimer->stop();
      signalTimer->start(interval);
    }

    paintTurnSignalBorder(p, rect);
  } else if (signalTimer->isActive()) {
    signalTimer->stop();
  }

  if (showFPS) {
    paintFPS(p, rect);
  }

  // Persistent bottom status bar: lead distance/headway + memory/CPU temp
  paintBottomStatusBar(p, rect);
}

void FrogPilotOnroadWindow::paintFPS(QPainter &p, const QRect &rect) {
  p.save();

  qint64 now = QDateTime::currentMSecsSinceEpoch();

  static double maxFPS = 0.0;
  static double minFPS = 99.9;
  static double totalFPS = 0.0;

  static QList<QPair<qint64, double>> fpsHistory;

  fpsHistory.append({now, fps});
  totalFPS += fps;

  while (!fpsHistory.isEmpty() && now - fpsHistory.first().first > 60000) {
    totalFPS -= fpsHistory.first().second;
    fpsHistory.removeFirst();
  }

  double avgFPS = fpsHistory.isEmpty() ? 0.0 : totalFPS / fpsHistory.size();

  minFPS = std::min(minFPS, fps);
  maxFPS = std::max(maxFPS, fps);

  QString fpsDisplayString = QString("FPS: %1 | Min: %2 | Max: %3 | Avg: %4")
                                .arg(qRound(fps))
                                .arg(qRound(minFPS))
                                .arg(qRound(maxFPS))
                                .arg(qRound(avgFPS));

  p.setFont(InterFont(28, QFont::DemiBold));
  p.setPen(Qt::white);

  int xPos = (rect.width() - p.fontMetrics().horizontalAdvance(fpsDisplayString)) / 2;
  int yPos = rect.bottom() - 5;

  p.drawText(xPos, yPos, fpsDisplayString);

  p.restore();
}

void FrogPilotOnroadWindow::paintBottomStatusBar(QPainter &p, const QRect &rect) {
  p.save();

  const int barHeight = std::max(28, UI_BORDER_SIZE - 8);
  QRect barRect(rect.left() + UI_BORDER_SIZE,
                rect.bottom() - UI_BORDER_SIZE + (UI_BORDER_SIZE - barHeight) / 2,
                rect.width() - 2 * UI_BORDER_SIZE,
                barHeight);

  // Semi-transparent dark background
  p.setBrush(QColor(0, 0, 0, 140));
  p.setPen(Qt::NoPen);
  p.drawRoundedRect(barRect, 18, 18);

  p.setFont(InterFont(32, QFont::DemiBold));
  p.setPen(Qt::white);

  // Left side: lead distance + headway
  QString leadText;
  if (hasLead) {
    double dist_m = std::max(0.0, leadDistanceM);
    double headway = std::clamp(headwayS, 0.0, 9.9);
    double distanceConversion = isMetricUnits ? 1.0 : METER_TO_FOOT;
    QString distanceUnit = isMetricUnits ? tr("m") : tr("ft");

    double displayDist = dist_m * distanceConversion;

    double speedConversion = isMetricUnits ? MS_TO_KPH : MS_TO_MPH;
    QString speedUnit = isMetricUnits ? tr("km/h") : tr("mph");
    double displaySpeed = leadSpeed * speedConversion;

    leadText = QString("%1 %2  |  %3 s  |  %4 %5")
                 .arg(QString::number(displayDist, 'f', 1))
                 .arg(distanceUnit)
                 .arg(QString::number(headway, 'f', 1))
                 .arg(QString::number(displaySpeed, 'f', 0))
                 .arg(speedUnit);
  } else {
    leadText = tr("No lead");
  }

  // Prepend gear label if available (e.g., "D | 12.3 m | 1.0 s | 47 km/h").
  if (!gearLabel.isEmpty()) {
    if (!leadText.isEmpty()) {
      leadText = QString("%1  |  %2").arg(gearLabel, leadText);
    } else {
      leadText = gearLabel;
    }
  }

  // Right side: memory usage + CPU temp
  QString rightText = tr("内存 %1%   CPU %2°C")
                        .arg(memoryUsage)
                        .arg(cpuTempC);

  QFontMetrics fm(p.font());
  int padding = 24;

  int leftX = barRect.left() + padding;
  int baselineY = barRect.center().y() + fm.ascent() / 2 - 4;
  p.drawText(leftX, baselineY, leadText);

  int rightWidth = fm.horizontalAdvance(rightText);
  int rightX = barRect.right() - padding - rightWidth;
  p.drawText(rightX, baselineY, rightText);

  p.restore();
}

void FrogPilotOnroadWindow::paintSteeringTorqueBorder(QPainter &p, const QRect &rect) {
  p.save();

  static float smoothedSteer = 0.0;
  smoothedSteer = 0.25 * std::abs(steer) + 0.75 * smoothedSteer;
  if (std::abs(smoothedSteer - steer) < 0.01) {
    smoothedSteer = steer;
  }

  QLinearGradient gradient(rect.topLeft(), rect.bottomLeft());
  gradient.setColorAt(0.0, bg_colors[STATUS_TRAFFIC_MODE_ENABLED]);
  gradient.setColorAt(0.25, bg_colors[STATUS_EXPERIMENTAL_MODE_ENABLED]);
  gradient.setColorAt(0.5, bg_colors[STATUS_CONDITIONAL_OVERRIDDEN]);
  gradient.setColorAt(0.75, bg_colors[STATUS_ENGAGED]);
  gradient.setColorAt(1.0, bg_colors[STATUS_ENGAGED]);

  int visibleHeight = rect.height() * smoothedSteer;

  QRect rectToFill, rectToHide;
  if (steer < 0) {
    rectToFill = QRect(rect.x(), rect.y() + rect.height() - visibleHeight, UI_BORDER_SIZE, visibleHeight);
    rectToHide = QRect(rect.x(), rect.y(), UI_BORDER_SIZE, rect.height() - visibleHeight);
  } else {
    rectToFill = QRect(rect.x() + rect.width() - UI_BORDER_SIZE, rect.y() + rect.height() - visibleHeight, UI_BORDER_SIZE, visibleHeight);
    rectToHide = QRect(rect.x() + rect.width() - UI_BORDER_SIZE, rect.y(), UI_BORDER_SIZE, rect.height() - visibleHeight);
  }
  p.fillRect(rectToFill, QBrush(gradient));
  p.fillRect(rectToHide, Qt::transparent);

  p.restore();
}

void FrogPilotOnroadWindow::paintTurnSignalBorder(QPainter &p, const QRect &rect) {
  p.save();

  std::function<QColor(bool, bool)> getBorderColor = [&](bool blindSpot, bool turnSignal) {
    if (turnSignal && showSignal) {
      if (blindSpot) {
        return flickerActive ? bg_colors[STATUS_TRAFFIC_MODE_ENABLED] : bg_colors[STATUS_CONDITIONAL_OVERRIDDEN];
      } else {
        return flickerActive ? bg_colors[STATUS_CONDITIONAL_OVERRIDDEN] : bg;
      }
    } else if (blindSpot && showBlindspot) {
      return bg_colors[STATUS_TRAFFIC_MODE_ENABLED];
    } else {
      return bg;
    }
  };

  QColor borderColorLeft = getBorderColor(blindSpotLeft, turnSignalLeft);
  QColor borderColorRight = getBorderColor(blindSpotRight, turnSignalRight);

  p.fillRect(rect.x(), rect.y(), rect.width() / 2, rect.height(), borderColorLeft);
  p.fillRect(rect.x() + rect.width() / 2, rect.y(), rect.width() / 2, rect.height(), borderColorRight);

  p.restore();
}
