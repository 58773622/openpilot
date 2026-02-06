#pragma once

#include <set>

#include "selfdrive/frogpilot/ui/qt/offroad/frogpilot_settings.h"

class QStackedLayout;
class ScrollView;

class FrogPilotVehiclesPanel : public FrogPilotListWidget {
  Q_OBJECT

public:
  explicit FrogPilotVehiclesPanel(FrogPilotSettingsWindow *parent);

  // Allow external callers (e.g. SettingsWindow) to jump directly into the
  // GM-specific vehicle settings section without going through the parent
  // "General Motors Settings" manage button.
  void openGMSection();

signals:
  void openParentToggle();

protected:
  void showEvent(QShowEvent *event) override;

private:
  void updateState(const UIState &s);
  void updateToggles();

  bool hasExperimentalOpenpilotLongitudinal;
  bool hasOpenpilotLongitudinal;
  bool hasSNG;
  bool isC3;
  bool isGM;
  bool isHKG;
  bool isHKGCanFd;
  bool isToyota;
  bool isVolt;
  bool started;

  int tuningLevel;

  std::map<QString, AbstractControl*> toggles;

  QStackedLayout *vehiclesLayout;
  ScrollView *gmPanel;

  std::set<QString> gmKeys = {"ExperimentalGMTune", "LongPitch", "GMDisableGps", "GMDisableLowSpeedRes", "GMStopAndGo", "GMExternalPanda", "DisableDriverMonitoring", "QuietFan"};
  std::set<QString> hkgKeys = {"NewLongAPI"};
  std::set<QString> longitudinalKeys = {"ExperimentalGMTune", "FrogsGoMoosTweak", "LongPitch", "NewLongAPI", "SNGHack", "GMDisableLowSpeedRes", "GMStopAndGo"};
  std::set<QString> toyotaKeys = {"ClusterOffset", "FrogsGoMoosTweak", "LockDoorsTimer", "SNGHack", "ToyotaDoors"};

  std::set<QString> parentKeys;

  FrogPilotSettingsWindow *parent;

  QJsonObject frogpilotToggleLevels;

  QMap<QString, QString> carModels;

  ParamControl *disableOpenpilotLong;

  Params params;
  Params params_default{"/dev/shm/params_default"};
};
