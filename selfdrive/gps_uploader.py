#!/usr/bin/env python3
"""
GPS 数据上传模块
在上传 qlog 文件后，自动提取 GPS 数据并上传 JSON
"""

import os
import json
import requests
from pathlib import Path
from openpilot.common.params import Params
from openpilot.common.api import API_HOST
from openpilot.common.swaglog import cloudlog

# 导入 GPS 解析器
try:
    from openpilot.selfdrive.gps_parser import parse_qlog
    GPS_PARSER_AVAILABLE = True
except ImportError:
    GPS_PARSER_AVAILABLE = False
    cloudlog.warning("GPS 解析器不可用")


def extract_and_upload_gps(qlog_path: str, dongle_id: str, route_name: str, api_host: str):
    """
    提取 qlog 中的 GPS 数据并上传到服务器
    
    Args:
        qlog_path: qlog 文件路径
        dongle_id: 设备 ID
        route_name: 行程名称
        api_host: API 服务器地址
    """
    if not GPS_PARSER_AVAILABLE:
        cloudlog.warning("GPS 解析器不可用，跳过 GPS 数据上传")
        return False
    
    try:
        cloudlog.info(f"开始提取 GPS 数据: {qlog_path}")
        
        # 解析 qlog 文件
        track = parse_qlog(qlog_path)
        
        if not track or len(track.points) == 0:
            cloudlog.warning(f"未找到 GPS 数据: {qlog_path}")
            return False
        
        # 转换为 JSON 格式
        gps_data = {
            'route': route_name,
            'dongle_id': dongle_id,
            'points': track.points,
            'start_time': track.start_time,
            'end_time': track.end_time,
            'duration': track.end_time - track.start_time if track.end_time and track.start_time else 0,
            'distance': track.total_distance,
            'max_speed': track.max_speed,
            'point_count': len(track.points)
        }
        
        # 上传到服务器
        url = f"{api_host}/v1/gps/{dongle_id}/{route_name}"
        response = requests.post(url, json=gps_data, timeout=30)
        
        if response.status_code == 200:
            cloudlog.info(f"✓ GPS 数据已上传: {len(track.points)} 个点, {track.total_distance/1000:.2f} km")
            return True
        else:
            cloudlog.error(f"GPS 数据上传失败: {response.status_code}")
            return False
            
    except Exception as e:
        cloudlog.error(f"GPS 数据提取/上传失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def process_route_gps(route_path: str):
    """
    处理一个行程目录下的所有 qlog 文件
    
    Args:
        route_path: 行程目录路径，格式如 /data/media/0/realdata/2024-01-01--12-00-00
    """
    route_path = Path(route_path)
    if not route_path.exists():
        return
    
    # 获取配置
    params = Params()
    dongle_id = params.get("DongleId", encoding='utf-8')
    if not dongle_id:
        cloudlog.warning("无法获取 Dongle ID")
        return
    
    api_host = API_HOST.replace('https://', 'http://').replace('http://', 'http://')
    route_name = route_path.name
    
    # 查找 qlog 文件
    qlog_files = list(route_path.glob('qlog*'))
    if not qlog_files:
        return
    
    # 处理第一个 qlog 文件
    qlog_path = str(qlog_files[0])
    extract_and_upload_gps(qlog_path, dongle_id, route_name, api_host)


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("用法: python gps_uploader.py <route_path>")
        print("示例: python gps_uploader.py /data/media/0/realdata/2024-01-01--12-00-00")
        sys.exit(1)
    
    process_route_gps(sys.argv[1])
