#include <QRegularExpression>
#include <QTextStream>
#include <QStackedLayout>

#include "selfdrive/frogpilot/ui/qt/offroad/vehicle_settings.h"

QStringList getCarNames(const QString &carMake, QMap<QString, QString> &carModels) {
  static const QMap<QString, QString> makeMap = {
    {"acura", "honda"},
    {"audi", "volkswagen"},
    {"buick", "gm"},
    {"cadillac", "gm"},
    {"chevrolet", "gm"},
    {"chrysler", "chrysler"},
    {"cupra", "volkswagen"},
    {"dodge", "chrysler"},
    {"ford", "ford"},
    {"genesis", "hyundai"},
    {"gmc", "gm"},
    {"holden", "gm"},
    {"honda", "honda"},
    {"hyundai", "hyundai"},
    {"jeep", "chrysler"},
    {"kia", "hyundai"},
    {"lexus", "toyota"},
    {"lincoln", "ford"},
    {"man", "volkswagen"},
    {"mazda", "mazda"},
    {"nissan", "nissan"},
    {"ram", "chrysler"},
    {"seat", "volkswagen"},
    {"škoda", "volkswagen"},
    {"subaru", "subaru"},
    {"tesla", "tesla"},
    {"toyota", "toyota"},
    {"volkswagen", "volkswagen"}
  };

  QStringList carNameList;

  QFile valuesFile(QString("../car/%1/values.py").arg(makeMap.value(carMake, carMake)));
  if (!valuesFile.open(QIODevice::ReadOnly | QIODevice::Text)) {
    return carNameList;
  }

  QTextStream in(&valuesFile);
  QString fileContent = in.readAll();
  valuesFile.close();

  fileContent.remove(QRegularExpression("#[^\n]*"));
  fileContent.remove(QRegularExpression("footnotes=\\[[^\\]]*\\],\\s*"));

  static const QRegularExpression carNameRegex("CarDocs\\(\\s*\"([^\"]+)\"[^)]*\\)");
  static const QRegularExpression platformRegex("((\\w+)\\s*=\\s*\\w+\\s*\\(\\s*\\[([\\s\\S]*?)\\]\\s*,)");
  static const QRegularExpression validNameRegex("^[A-Za-z0-9 \u0160.()-]+$");

  QRegularExpressionMatchIterator platformMatches = platformRegex.globalMatch(fileContent);
  while (platformMatches.hasNext()) {
    QRegularExpressionMatch platformMatch = platformMatches.next();
    QString platformName = platformMatch.captured(2);
    QString platformSection = platformMatch.captured(3);

    QRegularExpressionMatchIterator carNameMatches = carNameRegex.globalMatch(platformSection);
    while (carNameMatches.hasNext()) {
      QString carName = carNameMatches.next().captured(1);
      if (carName.contains(validNameRegex) && carName.count(" ") >= 1) {
        QStringList carNameParts = carName.split(" ");
        for (const QString &part : carNameParts) {
          if (part.compare(carMake, Qt::CaseInsensitive) == 0) {
            carNameList.append(carName);
            carModels[carName] = platformName;
          }
          break;
        }
      }
    }
  }

  carNameList.sort();
  return carNameList;
}

FrogPilotVehiclesPanel::FrogPilotVehiclesPanel(FrogPilotSettingsWindow *parent) : FrogPilotListWidget(parent), parent(parent) {
  vehiclesLayout = new QStackedLayout();
  addItem(vehiclesLayout);

  FrogPilotListWidget *settingsList = new FrogPilotListWidget(this);

  ScrollView *vehiclesPanel = new ScrollView(settingsList, this);

  vehiclesLayout->addWidget(vehiclesPanel);

  QStringList makes = {
    "Acura", "Audi", "Buick", "Cadillac", "Chevrolet", "Chrysler",
    "CUPRA", "Dodge", "Ford", "Genesis", "GMC", "Holden", "Honda",
    "Hyundai", "Jeep", "Kia", "Lexus", "Lincoln", "MAN", "Mazda",
    "Nissan", "Ram", "SEAT", "Škoda", "Subaru", "Tesla", "Toyota",
    "Volkswagen"
  };

  ButtonControl *selectMakeButton = new ButtonControl(tr("Select Make"), tr("SELECT"));
  QObject::connect(selectMakeButton, &ButtonControl::clicked, [this, makes, selectMakeButton]() {
    QString makeSelection = MultiOptionDialog::getSelection(tr("Select a Make"), makes, "", this);
    if (!makeSelection.isEmpty()) {
      params.put("CarMake", makeSelection.toStdString());
      selectMakeButton->setValue(makeSelection);
    }
  });
  settingsList->addItem(selectMakeButton);

  ButtonControl *selectModelButton = new ButtonControl(tr("Select Model"), tr("SELECT"));
  QObject::connect(selectModelButton, &ButtonControl::clicked, [this, selectModelButton]() {
    QString modelSelection = MultiOptionDialog::getSelection(tr("Select a Model"), getCarNames(QString::fromStdString(params.get("CarMake")).toLower(), carModels), "", this);
    if (!modelSelection.isEmpty()) {
      params.put("CarModel", carModels.value(modelSelection).toStdString());
      params.put("CarModelName", modelSelection.toStdString());
      selectModelButton->setValue(modelSelection);
    }
  });
  settingsList->addItem(selectModelButton);

  ParamControl *forceFingerprint = new ParamControl("ForceFingerprint", tr("Disable Automatic Fingerprint Detection"), tr("Forces the selected fingerprint and prevents it from ever changing."), "");
  settingsList->addItem(forceFingerprint);

  disableOpenpilotLong = new ParamControl("DisableOpenpilotLongitudinal", tr("Disable openpilot Longitudinal Control"), tr("Disables openpilot longitudinal control and uses the car's stock ACC instead."), "");
  QObject::connect(disableOpenpilotLong, &ToggleControl::toggleFlipped, [this, parent](bool state) {
    if (state) {
      if (FrogPilotConfirmationDialog::yesorno(tr("Are you sure you want to completely disable openpilot longitudinal control?"), this)) {
        if (started) {
          if (FrogPilotConfirmationDialog::toggleReboot(this)) {
            Hardware::reboot();
          }
        }
      } else {
        params.putBool("DisableOpenpilotLongitudinal", false);
        disableOpenpilotLong->refresh();
      }
    }

    parent->updateVariables();
    updateToggles();
  });
  settingsList->addItem(disableOpenpilotLong);

  FrogPilotListWidget *gmList = new FrogPilotListWidget(this);
  FrogPilotListWidget *hkgList = new FrogPilotListWidget(this);
  FrogPilotListWidget *toyotaList = new FrogPilotListWidget(this);

  gmPanel = new ScrollView(gmList, this);
  ScrollView *hkgPanel = new ScrollView(hkgList, this);
  ScrollView *toyotaPanel = new ScrollView(toyotaList, this);

  vehiclesLayout->addWidget(gmPanel);
  vehiclesLayout->addWidget(hkgPanel);
  vehiclesLayout->addWidget(toyotaPanel);

  std::vector<std::tuple<QString, QString, QString, QString>> vehicleToggles {
    {"GMToggles", tr("General Motors Settings"), tr("Settings specific to <b>General Motors</b> vehicles."), ""},
    {"ExperimentalGMTune", tr("FrogsGoMoo's Experimental Tune"), tr("<b>FrogsGoMoo's</b> experimental <b>General Motors</b> tune that aims to smoothen out stopping and takeoff control based on nothing but guesswork. Use at your own risk!"), ""},
    {"LongPitch", tr("Smooth Pedal Response on Hills"), tr("Smoothen the acceleration and braking when driving uphill or downhill."), ""},
    {"GMDisableGps", tr("\u5c4f\u853d GPS / \u4f4e\u901f\u8f6c\u5411\u544a\u8b66"), tr("\u5173\u95ed\u4e0e GPS \u76f8\u5173\u7684\u6a21\u5757\uff0c\u5e76\u5c4f\u853d \"GPS \u4fe1\u53f7\u4e0d\u4f73\" \u4ee5\u53ca \"\u4f4e\u901f\u8f6c\u5411\u4e0d\u53ef\u7528\" \u7684\u63d0\u793a\u3002\u4ec5\u5728\u5b8c\u5168\u4e0d\u9700\u8981\u5bfc\u822a / \u901f\u5ea6\u9650\u5236\u7b49 GPS \u529f\u80fd\u65f6\u542f\u7528\u3002"), ""},
    {"GMDisableLowSpeedRes", tr("25 km/h \u4ee5\u4e0b\u7981\u6b62\u4f7f\u7528 RES- \u8bbe\u7f6e\u5e76\u7ebf"), tr("\u5f53\u8f66\u901f\u4f4e\u4e8e 25 km/h \u65f6\uff0c\u7981\u6b62\u901a\u8fc7 RES- \u6309\u94ae\u542f\u7528\u6216\u8bbe\u7f6e/\u6062\u590d\u5e76\u7ebf\uff0c\u4ee5\u51cf\u5c11\u4f4e\u901f\u4e0b ACC / SASCM \u76f8\u5173\u6545\u969c\u3002"), ""},
    {"GMStopAndGo", tr("\u961f\u5217\u8ddf\u8f66\u8d77\u6b65"), tr("\u5728\u62e5\u5835\u961f\u5217\u4e2d\uff0c\u5f53\u8f66\u8f86\u5b8c\u5168\u505c\u6ede\u4e14\u524d\u8f66\u8d77\u6b65\u65f6\uff0c\u5141\u8bb8 openpilot \u5728 0 km/h \u81ea\u52a8\u8d77\u6b65\u5e76\u8ddf\u8f66\u3002"), ""},
    {"DisableDriverMonitoring", tr("\u5c4f\u853d\u9a7e\u9a76\u5458\u76d1\u63a7"), tr("\u5173\u95ed\u9a7e\u9a76\u5458\u6ce8\u610f\u529b\u76d1\u63a7\u548c\u76f8\u5e94\u8b66\u544a\u3002\u4ec5\u5728\u5145\u5206\u4e86\u89e3\u98ce\u9669\u5e76\u63a5\u53d7\u5b89\u5168\u9690\u60a3\u7684\u524d\u63d0\u4e0b\u542f\u7528\u3002"), ""},
    {"GMExternalPanda", tr("\u5916\u7f6e\u7ea2\u718a\u5b89\u5168\u6a21\u5757"), tr("\u4f7f\u7528\u5916\u7f6e\u7ea2\u718a\u8fdb\u884c CAN \u603b\u7ebf\u6620\u5c04\u548c\u5b89\u5168\u6a21\u5757\u63a7\u5236\u3002\u4ec5\u5728\u5df2\u7ecf\u6b63\u786e\u5b89\u88c5\u5916\u7f6e\u5b89\u5168\u6a21\u5757\u65f6\u542f\u7528\uff0c\u5426\u5219\u53ef\u80fd\u5bfc\u81f4\u8f6c\u5411/\u5236\u52a8\u5931\u6548\u3002"), ""},
    {"NewLongAPI", tr("comma's New Longitudinal API"), tr("comma's new longitudinal control system that has shown great improvement with acceleration and braking, but has issues on some <b>Hyundai</b>/<b>Kia</b>/<b>Genesis</b> vehicles."), ""},

    {"ToyotaToggles", tr("Toyota/Lexus Settings"), tr("Settings specific to <b>Toyota</b> and <b>Lexus</b> vehicles."), ""},
    {"ToyotaDoors", tr("Automatically Lock/Unlock Doors"), tr("Automatically lock the doors when shifting into drive and unlock them when shifting into park."), ""},
    {"ClusterOffset", tr("Cluster Speed Offset"), tr("The cluster speed offset used by openpilot to match the speed displayed on the dash."), ""},
    {"FrogsGoMoosTweak", tr("FrogsGoMoo's Personal Tweaks"), tr("<b>FrogsGoMoo's</b> personal tweaks for quicker acceleration and smoother braking."), ""},
    {"LockDoorsTimer", tr("Lock Doors On Ignition Off After"), tr("Automatically lock the doors after the car's ignition has been turned off and no one is detected in either of the front seats."), ""},
    {"SNGHack", tr("Stop and Go Hack"), tr("Force stop and go on <b>Toyota</b>/<b>Lexus</b> vehicles without stock stop and go functionality."), ""}
  };

  for (const auto &[param, title, desc, icon] : vehicleToggles) {
    AbstractControl *vehicleToggle;

    if (param == "GMToggles") {
      ButtonControl *gmToggle = new ButtonControl(title, tr("MANAGE"), desc);
      QObject::connect(gmToggle, &ButtonControl::clicked, [this]() {
        vehiclesLayout->setCurrentWidget(gmPanel);
      });
      vehicleToggle = gmToggle;

    } else if (param == "HKGToggles") {
      ButtonControl *hkgToggle = new ButtonControl(title, tr("MANAGE"), desc);
      QObject::connect(hkgToggle, &ButtonControl::clicked, [this, hkgPanel]() {
        vehiclesLayout->setCurrentWidget(hkgPanel);
      });
      vehicleToggle = hkgToggle;

    } else if (param == "ToyotaToggles") {
      ButtonControl *toyotaToggle = new ButtonControl(title, tr("MANAGE"), desc);
      QObject::connect(toyotaToggle, &ButtonControl::clicked, [this, toyotaPanel]() {
        vehiclesLayout->setCurrentWidget(toyotaPanel);
      });
      vehicleToggle = toyotaToggle;
    } else if (param == "ToyotaDoors") {
      std::vector<QString> lockToggles{"LockDoors", "UnlockDoors"};
      std::vector<QString> lockToggleNames{tr("Lock"), tr("Unlock")};
      vehicleToggle = new FrogPilotButtonToggleControl(param, title, desc, icon, lockToggles, lockToggleNames);
    } else if (param == "LockDoorsTimer") {
      std::map<float, QString> autoLockLabels;
      for (int i = 0; i <= 300; ++i) {
        autoLockLabels[i] = i == 0 ? tr("Never") : QString::number(i) + tr(" seconds");
      }
      vehicleToggle = new FrogPilotParamValueControl(param, title, desc, icon, 0, 300, QString(), autoLockLabels, 5);
    } else if (param == "ClusterOffset") {
      std::vector<QString> clusterOffsetButton{"Reset"};
      FrogPilotParamValueButtonControl *clusterOffsetToggle = new FrogPilotParamValueButtonControl(param, title, desc, icon, 1.000, 1.050, "x", std::map<float, QString>(), 0.001, false, {}, clusterOffsetButton, false, false);
      QObject::connect(clusterOffsetToggle, &FrogPilotParamValueButtonControl::buttonClicked, [this, clusterOffsetToggle]() {
        params.putFloat("ClusterOffset", params_default.getFloat("ClusterOffset"));
        clusterOffsetToggle->refresh();
      });
      vehicleToggle = clusterOffsetToggle;

    } else {
      vehicleToggle = new ParamControl(param, title, desc, icon);
    }

    toggles[param] = vehicleToggle;

    if (gmKeys.find(param) != gmKeys.end()) {
      gmList->addItem(vehicleToggle);
    } else if (hkgKeys.find(param) != hkgKeys.end()) {
      hkgList->addItem(vehicleToggle);
    } else if (toyotaKeys.find(param) != toyotaKeys.end()) {
      toyotaList->addItem(vehicleToggle);
    } else {
      settingsList->addItem(vehicleToggle);

      parentKeys.insert(param);
    }

    if (ButtonControl *buttonControl = qobject_cast<ButtonControl*>(vehicleToggle)) {
      QObject::connect(buttonControl, &ButtonControl::clicked, this, &FrogPilotVehiclesPanel::openParentToggle);
    }

    QObject::connect(vehicleToggle, &AbstractControl::showDescriptionEvent, [this]() {
      update();
    });
  }

  auto lock_timer_it = toggles.find("LockDoorsTimer");
  if (lock_timer_it != toggles.end()) {
    if (auto *lock_timer = qobject_cast<FrogPilotParamValueControl*>(lock_timer_it->second)) {
      lock_timer->setWarning("<b>Warning:</b> openpilot can't detect if keys are still inside the car, so ensure you have a spare key to prevent accidental lockouts!");
    }
  }

  std::set<QString> rebootKeys = {"NewLongAPI", "GMExternalPanda"};
  for (const QString &key : rebootKeys) {
    auto it = toggles.find(key);
    if (it == toggles.end()) continue;

    if (auto *reboot_toggle = qobject_cast<ToggleControl*>(it->second)) {
      QObject::connect(reboot_toggle, &ToggleControl::toggleFlipped, [this]() {
        if (started) {
          if (FrogPilotConfirmationDialog::toggleReboot(this)) {
            Hardware::reboot();
          }
        }
      });
    }
  }

  QObject::connect(uiState(), &UIState::offroadTransition, [this, selectMakeButton, selectModelButton]() {
    std::thread([this, selectMakeButton, selectModelButton]() {
      selectMakeButton->setValue(QString::fromStdString(params.get("CarMake", true)));
      selectModelButton->setValue(QString::fromStdString(params.get(params.get("CarModelName").empty() ? "CarModel" : "CarModelName")));
    }).detach();
  });

  QObject::connect(parent, &FrogPilotSettingsWindow::closeParentToggle, [this, vehiclesPanel]() {
    vehiclesLayout->setCurrentWidget(vehiclesPanel);
  });
  QObject::connect(uiState(), &UIState::uiUpdate, this, &FrogPilotVehiclesPanel::updateState);
}

void FrogPilotVehiclesPanel::showEvent(QShowEvent *event) {
  frogpilotToggleLevels = parent->frogpilotToggleLevels;
  hasExperimentalOpenpilotLongitudinal = parent->hasExperimentalOpenpilotLongitudinal;
  hasOpenpilotLongitudinal = parent->hasOpenpilotLongitudinal;
  hasSNG = parent->hasSNG;
  isC3 = parent->isC3;
  isGM = parent->isGM;
  isHKG = parent->isHKG;
  isHKGCanFd = parent->isHKGCanFd;
  isToyota = parent->isToyota;
  isVolt = parent->isVolt;
  tuningLevel = parent->tuningLevel;

  updateToggles();
}

void FrogPilotVehiclesPanel::updateState(const UIState &s) {
  if (!isVisible()) {
    return;
  }

  started = s.scene.started;
}

void FrogPilotVehiclesPanel::openGMSection() {
  if (vehiclesLayout && gmPanel) {
    vehiclesLayout->setCurrentWidget(gmPanel);
    emit openParentToggle();
  }
}

void FrogPilotVehiclesPanel::updateToggles() {
  for (auto &[key, toggle] : toggles) {
    if (parentKeys.find(key) != parentKeys.end()) {
      toggle->setVisible(false);
    }
  }

  for (auto &[key, toggle] : toggles) {
    if (parentKeys.find(key) != parentKeys.end()) {
      continue;
    }

    // GM-specific toggles are always visible regardless of Tuning Level.
    double requiredLevel = frogpilotToggleLevels.value(key).toDouble(0);
    bool setVisible = gmKeys.find(key) != gmKeys.end() ? true : tuningLevel >= requiredLevel;

    if (hkgKeys.find(key) != hkgKeys.end()) {
      setVisible &= isHKG;
    } else if (toyotaKeys.find(key) != toyotaKeys.end()) {
      setVisible &= isToyota;
    }

    if (longitudinalKeys.find(key) != longitudinalKeys.end()) {
      setVisible &= hasOpenpilotLongitudinal;
    }

    if (key == "LockDoorsTimer") {
      setVisible &= !isC3;
    }

    if (key == "SNGHack") {
      setVisible &= !hasSNG;
    }

    if (key == "VoltSNG") {
      setVisible &= isVolt && !hasSNG;
    }

    toggle->setVisible(setVisible);

    if (setVisible) {
      if (gmKeys.find(key) != gmKeys.end()) {
        toggles["GMToggles"]->setVisible(true);
      } else if (hkgKeys.find(key) != hkgKeys.end()) {
        toggles["HKGToggles"]->setVisible(true);
      } else if (toyotaKeys.find(key) != toyotaKeys.end()) {
        toggles["ToyotaToggles"]->setVisible(true);
      }
    }
  }

  disableOpenpilotLong->setVisible((hasOpenpilotLongitudinal || params.getBool("DisableOpenpilotLongitudinal")) && !hasExperimentalOpenpilotLongitudinal);

  update();
}
