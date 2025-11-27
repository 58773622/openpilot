#!/usr/bin/env python3
"""
GPS 数据解析模块
从 qlog 文件中提取 GPS 轨迹数据
"""

import os
import json
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

try:
    from openpilot.tools.lib.logreader import LogReader
    LOGREADER_AVAILABLE = True
except ImportError:
    LOGREADER_AVAILABLE = False
    print("⚠️ LogReader 不可用，将使用备用解析方法")


class GPSTrack:
    """GPS 轨迹数据"""
    def __init__(self):
        self.points: List[Dict] = []
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.total_distance: float = 0.0
        self.max_speed: float = 0.0
        
    def add_point(self, lat: float, lon: float, timestamp: float, 
                  speed: float = 0.0, bearing: float = 0.0, altitude: float = 0.0):
        """添加 GPS 点"""
        if lat == 0.0 and lon == 0.0:
            return  # 跳过无效坐标
            
        point = {
            'lat': lat,
            'lon': lon,
            'timestamp': timestamp,
            'speed': speed,  # m/s
            'bearing': bearing,  # 度
            'altitude': altitude  # 米
        }
        
        self.points.append(point)
        
        if self.start_time is None:
            self.start_time = timestamp
        self.end_time = timestamp
        
        if speed > self.max_speed:
            self.max_speed = speed
    
    def to_dict(self):
        """转换为字典"""
        return {
            'points': self.points,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'duration': (self.end_time - self.start_time) if self.end_time and self.start_time else 0,
            'total_distance': self.total_distance,
            'max_speed': self.max_speed,
            'point_count': len(self.points)
        }


def parse_qlog(qlog_path: str) -> Optional[GPSTrack]:
    """
    解析 qlog 文件，提取 GPS 轨迹
    
    Args:
        qlog_path: qlog 文件路径
        
    Returns:
        GPSTrack 对象，如果解析失败返回 None
    """
    if not os.path.exists(qlog_path):
        print(f"⚠️ 文件不存在: {qlog_path}")
        return None
    
    track = GPSTrack()
    
    try:
        if LOGREADER_AVAILABLE:
            # 使用 LogReader 解析
            lr = LogReader(qlog_path)
            
            for msg in lr:
                # 提取 GPS 数据
                if msg.which() == 'gpsLocationExternal':
                    gps = msg.gpsLocationExternal
                    
                    # 检查数据有效性
                    if hasattr(gps, 'latitude') and hasattr(gps, 'longitude'):
                        lat = gps.latitude
                        lon = gps.longitude
                        timestamp = msg.logMonoTime / 1e9  # 纳秒转秒
                        
                        # 提取其他信息
                        speed = gps.speed if hasattr(gps, 'speed') else 0.0
                        bearing = gps.bearingDeg if hasattr(gps, 'bearingDeg') else 0.0
                        altitude = gps.altitude if hasattr(gps, 'altitude') else 0.0
                        
                        track.add_point(lat, lon, timestamp, speed, bearing, altitude)
                
                # 也可以从 liveLocationKalman 获取融合后的位置
                elif msg.which() == 'liveLocationKalman':
                    loc = msg.liveLocationKalman
                    
                    if hasattr(loc, 'positionGeodetic'):
                        pos = loc.positionGeodetic
                        if hasattr(pos, 'value') and len(pos.value) >= 2:
                            lat = pos.value[0]
                            lon = pos.value[1]
                            alt = pos.value[2] if len(pos.value) > 2 else 0.0
                            timestamp = msg.logMonoTime / 1e9
                            
                            # 速度信息
                            speed = 0.0
                            if hasattr(loc, 'velocityCalibrated') and hasattr(loc.velocityCalibrated, 'value'):
                                vel = loc.velocityCalibrated.value
                                if len(vel) >= 2:
                                    speed = (vel[0]**2 + vel[1]**2)**0.5
                            
                            track.add_point(lat, lon, timestamp, speed, 0.0, alt)
        
        else:
            # 备用方法：尝试直接读取 JSON 格式（如果有的话）
            print("⚠️ 使用备用解析方法")
            # 这里可以添加其他解析逻辑
            
    except Exception as e:
        print(f"⚠️ 解析 qlog 失败: {e}")
        import traceback
        traceback.print_exc()
        return None
    
    if len(track.points) == 0:
        print("⚠️ 未找到 GPS 数据")
        return None
    
    # 计算总距离
    track.total_distance = calculate_distance(track.points)
    
    print(f"✓ 解析完成: {len(track.points)} 个 GPS 点")
    return track


def calculate_distance(points: List[Dict]) -> float:
    """
    计算轨迹总距离（使用 Haversine 公式）
    
    Args:
        points: GPS 点列表
        
    Returns:
        总距离（米）
    """
    import math
    
    if len(points) < 2:
        return 0.0
    
    total = 0.0
    R = 6371000  # 地球半径（米）
    
    for i in range(1, len(points)):
        lat1, lon1 = points[i-1]['lat'], points[i-1]['lon']
        lat2, lon2 = points[i]['lat'], points[i]['lon']
        
        # Haversine 公式
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        
        a = (math.sin(dlat/2)**2 + 
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * 
             math.sin(dlon/2)**2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        total += R * c
    
    return total


def export_to_geojson(track: GPSTrack, output_path: str):
    """
    导出轨迹为 GeoJSON 格式
    
    Args:
        track: GPS 轨迹
        output_path: 输出文件路径
    """
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[p['lon'], p['lat'], p.get('altitude', 0)] for p in track.points]
                },
                "properties": {
                    "start_time": track.start_time,
                    "end_time": track.end_time,
                    "duration": track.end_time - track.start_time if track.end_time and track.start_time else 0,
                    "distance": track.total_distance,
                    "max_speed": track.max_speed,
                    "point_count": len(track.points)
                }
            }
        ]
    }
    
    with open(output_path, 'w') as f:
        json.dump(geojson, f)
    
    print(f"✓ GeoJSON 已导出: {output_path}")


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("用法: python gps_parser.py <qlog_file>")
        sys.exit(1)
    
    qlog_file = sys.argv[1]
    track = parse_qlog(qlog_file)
    
    if track:
        print(f"轨迹信息:")
        print(f"  点数: {len(track.points)}")
        print(f"  距离: {track.total_distance/1000:.2f} km")
        print(f"  最高速度: {track.max_speed*3.6:.1f} km/h")
        print(f"  时长: {(track.end_time - track.start_time)/60:.1f} 分钟")
        
        # 导出 GeoJSON
        output = qlog_file.replace('.bz2', '').replace('.qlog', '') + '_track.geojson'
        export_to_geojson(track, output)
