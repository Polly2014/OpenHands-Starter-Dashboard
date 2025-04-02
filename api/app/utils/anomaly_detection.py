# app/utils/anomaly_detection.py
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from ..config.db import telemetry_collection

async def detect_failure_anomalies():
    """
    检测异常失败模式
    返回: 异常会话列表
    """
    # 获取最近24小时内失败的安装
    one_day_ago = datetime.utcnow() - timedelta(hours=24)
    
    # 查找失败的安装
    failed_installs = await telemetry_collection.find({
        "step": "install",
        "status": "failure",
        "timestamp": {"$gte": one_day_ago}
    }).to_list(None)
    
    # 查找最近24小时内的安装总数
    total_installs = await telemetry_collection.count_documents({
        "step": "install",
        "timestamp": {"$gte": one_day_ago}
    })
    
    # 计算失败率
    failure_rate = len(failed_installs) / total_installs if total_installs > 0 else 0
    
    # 如果失败率超过30%，发出警报
    anomalies = []
    if failure_rate > 0.3 and total_installs > 5:
        # 分析失败模式
        failure_steps = {}
        for install in failed_installs:
            session_id = install["sessionId"]
            
            # 获取该会话中所有失败的步骤
            failed_steps = await telemetry_collection.find({
                "sessionId": session_id,
                "status": "failure"
            }).to_list(None)
            
            for step in failed_steps:
                step_name = step["step"]
                if step_name not in failure_steps:
                    failure_steps[step_name] = 0
                failure_steps[step_name] += 1
        
        # 找出最常见的失败步骤
        if failure_steps:
            most_common_step = max(failure_steps, key=failure_steps.get)
            anomalies.append({
                "type": "high_failure_rate",
                "failure_rate": failure_rate,
                "total_installs": total_installs,
                "most_common_failure": most_common_step,
                "timestamp": datetime.utcnow()
            })
    
    return anomalies