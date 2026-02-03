#!/usr/bin/env python3
"""
错误自动上报模块
捕获 openpilot 运行时错误并自动上传到服务器
实时监控和上报所有异常
"""

import requests
import traceback
import sys
import json
import threading
import queue
from datetime import datetime
from openpilot.common.params import Params
from openpilot.common.api import API_HOST

class ErrorReporter:
    def __init__(self):
        self.params = Params()
        self.dongle_id = self.params.get("DongleId", encoding='utf-8')
        self.api_host = API_HOST.replace('https://', 'http://').replace('http://', 'http://')
        
        # 错误队列，用于异步上传
        self.error_queue = queue.Queue()
        self.upload_thread = None
        self.running = False
        
    def start_background_uploader(self):
        """启动后台上传线程"""
        if self.upload_thread and self.upload_thread.is_alive():
            return
            
        self.running = True
        self.upload_thread = threading.Thread(target=self._upload_worker, daemon=True)
        self.upload_thread.start()
        print("✓ 错误上报后台线程已启动")
    
    def _upload_worker(self):
        """后台上传工作线程"""
        while self.running:
            try:
                # 从队列获取错误（阻塞等待）
                error_data = self.error_queue.get(timeout=1)
                self._do_upload(error_data)
            except queue.Empty:
                continue
            except Exception as e:
                print(f"⚠️ 上传线程异常: {e}")
    
    def _do_upload(self, error_data):
        """执行实际的上传"""
        if not self.dongle_id:
            return False
            
        try:
            url = f"{self.api_host}/v1/devices/{self.dongle_id}/errors"
            response = requests.post(url, json=error_data, timeout=5)
            
            if response.status_code == 200:
                print(f"✓ 错误已上报: {error_data['error_type']}")
                return True
            else:
                print(f"⚠️ 错误上报失败: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"⚠️ 错误上报异常: {e}")
            return False
        
    def report_error(self, error_type, error_message, stack_trace=None, context=None):
        """上报错误到服务器（异步）"""
        if not self.dongle_id:
            print("⚠️ 无法获取 Dongle ID，跳过错误上报")
            return False
        
        # 添加时间戳
        if context is None:
            context = {}
        context['timestamp'] = datetime.now().isoformat()
            
        payload = {
            'error_type': error_type,
            'error_message': error_message,
            'stack_trace': stack_trace or '',
            'context': context
        }
        
        # 加入队列，异步上传
        try:
            self.error_queue.put_nowait(payload)
            return True
        except queue.Full:
            print("⚠️ 错误队列已满")
            return False
    
    def report_exception(self, exc_type, exc_value, exc_traceback, context=None):
        """上报异常"""
        error_type = exc_type.__name__ if exc_type else 'UnknownError'
        error_message = str(exc_value)
        stack_trace = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        
        return self.report_error(error_type, error_message, stack_trace, context)
    
    def install_global_handler(self):
        """安装全局异常处理器"""
        # 启动后台上传线程
        self.start_background_uploader()
        
        def exception_handler(exc_type, exc_value, exc_traceback):
            # 打印到控制台
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            
            # 立即上报到服务器（异步）
            self.report_exception(exc_type, exc_value, exc_traceback)
        
        sys.excepthook = exception_handler
        print("✓ 全局错误捕获已启用")
    
    def watch_process(self, process_name):
        """监控特定进程的错误（可选）"""
        # 可以添加进程监控逻辑
        pass


# 全局实例
_reporter = None

def get_reporter():
    """获取全局 ErrorReporter 实例"""
    global _reporter
    if _reporter is None:
        _reporter = ErrorReporter()
    return _reporter

def report_error(error_type, error_message, stack_trace=None, context=None):
    """便捷函数：上报错误"""
    return get_reporter().report_error(error_type, error_message, stack_trace, context)

def install_error_reporter():
    """便捷函数：安装全局错误处理器并启动后台上传"""
    reporter = get_reporter()
    reporter.start_background_uploader()
    reporter.install_global_handler()
    return reporter


if __name__ == '__main__':
    # 测试
    reporter = ErrorReporter()
    reporter.report_error(
        error_type='TestError',
        error_message='这是一个测试错误',
        stack_trace='测试堆栈跟踪',
        context={'test': True, 'timestamp': datetime.now().isoformat()}
    )
