#!/usr/bin/env python3
"""
设备统计信息上报模块
定期上报设备类型、版本、内存、运行时间等信息到服务器
"""

import time
import requests
import psutil
import os
from datetime import datetime
from openpilot.common.params import Params
from openpilot.common.api import API_HOST
from openpilot.common.swaglog import cloudlog
from openpilot.system.hardware import HARDWARE

class DeviceStatsReporter:
    def __init__(self):
        self.params = Params()
        self.dongle_id = self.params.get("DongleId", encoding='utf-8')
        self.api_host = API_HOST.replace('https://', 'http://').replace('http://', 'http://')
        
        # 记录启动时间
        self.boot_time = datetime.now()
        
    def get_device_info(self):
        """获取完整的设备信息"""
        try:
            # 基本信息
            device_type = "Comma 3"
            if hasattr(HARDWARE, 'get_device_type'):
                device_type = HARDWARE.get_device_type()
            
            # 版本信息
            version = self.params.get("Version", encoding='utf-8') or "Unknown"
            git_commit = self.params.get("GitCommit", encoding='utf-8') or ""
            git_branch = self.params.get("GitBranch", encoding='utf-8') or ""
            
            # 序列号和 IMEI
            serial = self.params.get("HardwareSerial", encoding='utf-8') or ""
            imei = ""
            if hasattr(HARDWARE, 'get_imei'):
                imei = HARDWARE.get_imei(0) or ""
            
            # 内存信息（MB）
            memory = psutil.virtual_memory()
            total_memory = round(memory.total / 1024 / 1024)  # MB
            used_memory = round(memory.used / 1024 / 1024)    # MB
            memory_percent = memory.percent
            
            # CPU 信息
            cpu_percent = psutil.cpu_percent(interval=1)
            cpu_count = psutil.cpu_count()
            
            # 磁盘信息
            disk = psutil.disk_usage('/')
            total_disk = round(disk.total / 1024 / 1024 / 1024, 2)  # GB
            used_disk = round(disk.used / 1024 / 1024 / 1024, 2)    # GB
            disk_percent = disk.percent
            
            # 运行时间
            uptime_seconds = (datetime.now() - self.boot_time).total_seconds()
            uptime_hours = round(uptime_seconds / 3600, 2)
            
            # 系统启动时间
            boot_timestamp = psutil.boot_time()
            system_boot_time = datetime.fromtimestamp(boot_timestamp).isoformat()
            
            # 网络信息
            net_io = psutil.net_io_counters()
            bytes_sent = round(net_io.bytes_sent / 1024 / 1024, 2)  # MB
            bytes_recv = round(net_io.bytes_recv / 1024 / 1024, 2)  # MB
            
            # 温度信息（如果可用）
            temperature = None
            try:
                if hasattr(HARDWARE, 'get_current_power_draw'):
                    temps = psutil.sensors_temperatures()
                    if temps:
                        # 获取第一个温度传感器
                        for name, entries in temps.items():
                            if entries:
                                temperature = round(entries[0].current, 1)
                                break
            except:
                pass
            
            # 行驶统计（从 FrogPilot params 获取真实数据）
            distance = 0.0
            time_driven = 0.0
            drives = 0
            
            try:
                # 从 FrogPilotStats JSON 中获取统计数据
                frogpilot_stats_json = self.params.get("FrogPilotStats", encoding='utf-8')
                if frogpilot_stats_json:
                    import json
                    frogpilot_stats = json.loads(frogpilot_stats_json)
                    
                    # 累计里程（米）-> 转换为公里
                    distance = frogpilot_stats.get("FrogPilotMeters", 0) / 1000.0
                    
                    # 累计驾驶时间（秒）-> 转换为小时
                    time_driven = frogpilot_stats.get("FrogPilotSeconds", 0) / 3600.0
                    
                    # 累计行程数
                    drives = frogpilot_stats.get("FrogPilotDrives", 0)
            except Exception as e:
                cloudlog.warning(f"获取行驶统计失败: {e}")
                # 尝试从 tracking params 获取
                try:
                    params_tracking = Params("/cache/tracking")
                    distance = params_tracking.get_float("FrogPilotKilometers")
                    time_driven = params_tracking.get_float("FrogPilotMinutes") / 60.0  # 分钟转小时
                    drives = params_tracking.get_int("FrogPilotDrives")
                except:
                    pass
            
            return {
                # 基本信息
                'device_type': device_type,
                'version': version,
                'git_commit': git_commit[:8] if git_commit else "",
                'git_branch': git_branch,
                'serial': serial,
                'imei': imei,
                
                # 系统资源
                'total_memory_mb': total_memory,
                'used_memory_mb': used_memory,
                'memory_percent': memory_percent,
                'cpu_percent': cpu_percent,
                'cpu_count': cpu_count,
                'total_disk_gb': total_disk,
                'used_disk_gb': used_disk,
                'disk_percent': disk_percent,
                
                # 运行时间
                'uptime_hours': uptime_hours,
                'system_boot_time': system_boot_time,
                
                # 网络
                'network_sent_mb': bytes_sent,
                'network_recv_mb': bytes_recv,
                
                # 温度
                'temperature': temperature,
                
                # 行驶统计
                'distance': distance,
                'time': time_driven,
                'drives': drives
            }
        except Exception as e:
            cloudlog.error(f"获取设备信息失败: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def report_stats(self):
        """上报统计信息到服务器"""
        if not self.dongle_id:
            cloudlog.warning("无法获取 Dongle ID，跳过统计上报")
            return False
        
        device_info = self.get_device_info()
        if not device_info:
            return False
        
        try:
            url = f"{self.api_host}/v1/devices/{self.dongle_id}/stats"
            response = requests.post(url, json=device_info, timeout=10)
            
            if response.status_code == 200:
                cloudlog.info(f"✓ 设备统计已上报: {device_info['device_type']} v{device_info['version']}")
                return True
            else:
                cloudlog.warning(f"统计上报失败: {response.status_code}")
                return False
        except Exception as e:
            cloudlog.error(f"统计上报异常: {e}")
            return False
    
    def start_periodic_reporting(self, interval=300):
        """启动定期上报（默认5分钟一次）"""
        cloudlog.info("启动设备统计定期上报...")
        
        while True:
            try:
                self.report_stats()
            except Exception as e:
                cloudlog.error(f"定期上报异常: {e}")
            
            time.sleep(interval)


def main():
    """主函数"""
    reporter = DeviceStatsReporter()
    reporter.start_periodic_reporting(interval=300)  # 5分钟上报一次


if __name__ == '__main__':
    main()
