#!/usr/bin/env python3
"""
错误上报守护进程
独立运行，不影响主系统
"""

import time
from openpilot.common.swaglog import cloudlog

def main():
    """启动错误上报守护进程"""
    try:
        cloudlog.info("启动错误上报守护进程...")
        
        # 延迟导入，避免启动时的依赖问题
        from openpilot.selfdrive.error_reporter import install_error_reporter
        
        reporter = install_error_reporter()
        cloudlog.info("✓ 错误自动上报已启用")
        
        # 保持运行，定期检查
        while True:
            time.sleep(60)
            
    except KeyboardInterrupt:
        cloudlog.info("错误上报守护进程已停止")
    except Exception as e:
        cloudlog.error(f"错误上报守护进程异常: {e}")
        import traceback
        traceback.print_exc()
        # 出错后等待一段时间再退出，避免频繁重启
        time.sleep(30)

if __name__ == "__main__":
    main()
