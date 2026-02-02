#include "selfdrive/ui/qt/widgets/wifi.h"

#include <QHBoxLayout>
#include <QLabel>
#include <QPixmap>
#include <QPushButton>
#include <QVBoxLayout>

WiFiPromptWidget::WiFiPromptWidget(QWidget *parent) : QFrame(parent) {
  stack = new QStackedLayout(this);

  // Single Skyunlock device status card (no more upload prompt states)
  QWidget *card = new QWidget;
  QVBoxLayout *layout = new QVBoxLayout(card);
  layout->setContentsMargins(56, 40, 56, 40);
  layout->setSpacing(18);

  title_label = new QLabel(tr("Skyunlock 设备状态"));
  title_label->setStyleSheet("font-size: 64px; font-weight: 600;");
  layout->addWidget(title_label);

  status_label = new QLabel;
  status_label->setStyleSheet("font-size: 56px; font-weight: 600;");
  layout->addWidget(status_label);

  desc1_label = new QLabel;
  desc1_label->setStyleSheet("font-size: 44px; font-weight: 400;");
  desc1_label->setWordWrap(true);
  layout->addWidget(desc1_label);

  desc2_label = new QLabel;
  desc2_label->setStyleSheet("font-size: 44px; font-weight: 400;");
  desc2_label->setWordWrap(true);
  layout->addWidget(desc2_label);

  layout->addSpacing(10);

  mem_label = new QLabel;
  cpu_label = new QLabel;
  space_label = new QLabel;
  QString metrics_style = "font-size: 40px; font-weight: 400;";
  mem_label->setStyleSheet(metrics_style);
  cpu_label->setStyleSheet(metrics_style);
  space_label->setStyleSheet(metrics_style);

  layout->addWidget(mem_label);
  layout->addWidget(cpu_label);
  layout->addWidget(space_label);

  layout->addStretch();

  stack->addWidget(card);

  setStyleSheet(R"(
    WiFiPromptWidget {
      background-color: #333333;
      border-radius: 10px;
    }
  )");

  QObject::connect(uiState(), &UIState::uiUpdate, this, &WiFiPromptWidget::updateState);
}

void WiFiPromptWidget::updateState(const UIState &s) {
  if (!isVisible()) return;

  auto &sm = *(s.sm);
  auto device_state = sm["deviceState"].getDeviceState();

  QString dongle = QString::fromStdString(params.get("DongleId"));
  QString serial = QString::fromStdString(params.get("HardwareSerial"));
  bool unregistered = dongle.isEmpty() || dongle == "UnregisteredDevice";

  // Title is static but re-set in case of language changes at runtime
  title_label->setText(tr("Skyunlock 设备状态"));

  if (unregistered) {
    status_label->setText(tr("未注册"));
    status_label->setStyleSheet("font-size: 56px; font-weight: 600; color: #F87171;");
    desc1_label->setText(tr("当前设备未在 Skyunlock 注册。"));
    if (!serial.isEmpty()) {
      desc2_label->setText(tr("序列号: %1").arg(serial));
    } else {
      desc2_label->clear();
    }
  } else {
    status_label->setText(tr("已注册"));
    status_label->setStyleSheet("font-size: 56px; font-weight: 600; color: #34D399;");
    desc1_label->setText(tr("设备 ID: %1").arg(dongle));
    if (!serial.isEmpty()) {
      desc2_label->setText(tr("序列号: %1").arg(serial));
    } else {
      desc2_label->clear();
    }
  }

  // Metrics: memory / CPU / storage free percent
  int memory_usage = device_state.getMemoryUsagePercent();
  mem_label->setText(tr("内存占用 %1 %").arg(memory_usage));

  int cpu_usage = 0;
  auto cpu_loads = device_state.getCpuUsagePercent();
  if (cpu_loads.size() != 0) {
    int sum = 0;
    for (auto it = cpu_loads.begin(); it != cpu_loads.end(); ++it) {
      sum += *it;
    }
    cpu_usage = sum / cpu_loads.size();
  }
  cpu_label->setText(tr("处理器占用 %1 %").arg(cpu_usage));

  double free_space = device_state.getFreeSpacePercent();
  space_label->setText(tr("存储空间 %1 % 可用").arg(QString::number(free_space, 'f', 0)));
}
