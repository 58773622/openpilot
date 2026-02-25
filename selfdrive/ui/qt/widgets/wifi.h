#pragma once

#include <QFrame>
#include <QLabel>
#include <QStackedLayout>
#include <QWidget>

#include "selfdrive/ui/ui.h"

class WiFiPromptWidget : public QFrame {
  Q_OBJECT

public:
  explicit WiFiPromptWidget(QWidget* parent = 0);

signals:
  void openSettings(int index = 0, const QString &param = "");

public slots:
  void updateState(const UIState &s);

private:
  Params params;

protected:
  QStackedLayout *stack;
  QLabel *title_label;
  QLabel *status_label;
  QLabel *desc1_label;
  QLabel *desc2_label;
  QLabel *mem_label;
  QLabel *cpu_label;
  QLabel *space_label;
};
