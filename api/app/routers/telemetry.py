# app/routers/telemetry.py
from fastapi import APIRouter, HTTPException, status
from datetime import datetime, timedelta
from typing import Dict, Any, List

from ..models.telemetry import TelemetryEvent, TelemetryStats
from ..config.db import telemetry_collection
from ..utils.logger import get_logger

router = APIRouter(prefix="/api/telemetry", tags=["telemetry"])
logger = get_logger("telemetry_router")

@router.post("/", status_code=status.HTTP_201_CREATED)
async def receive_telemetry(event: Dict[str, Any]):
    """接收遥测数据"""
    try:
        # 提取基础字段
        telemetry_data = {
            "anonymousId": event.get("anonymousId"),
            "sessionId": event.get("sessionId"),
            "step": event.get("step"),
            "status": event.get("status"),
            "scriptVersion": event.get("scriptVersion"),
            "osVersion": event.get("osVersion"),
            "osName": event.get("osName"),
            "cpuArchitecture": event.get("cpuArchitecture"),
            "memoryGB": event.get("memoryGB")
        }
        
        # 处理时间戳
        timestamp = event.get("timestamp")
        if timestamp:
            try:
                telemetry_data["timestamp"] = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                telemetry_data["timestamp"] = datetime.utcnow()
        else:
            telemetry_data["timestamp"] = datetime.utcnow()
        
        # 额外的指标数据
        metrics = {}
        for key, value in event.items():
            if key not in telemetry_data:
                metrics[key] = value
        
        telemetry_data["metrics"] = metrics
        logger.info(f"Received telemetry: {event.get('step')} - {event.get('status')}")
        
        # 存储到数据库
        result = await telemetry_collection.insert_one(telemetry_data)
        
        return {"status": "success", "id": str(result.inserted_id)}
    
    except Exception as e:
        logger.error(f"Error processing telemetry: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process telemetry data: {str(e)}"
        )

@router.get("/stats", response_model=TelemetryStats)
async def get_telemetry_stats():
    """获取遥测数据统计摘要"""
    try:
        # 获取会话总数
        total_sessions = len(await telemetry_collection.distinct("sessionId"))
        
        # 获取成功安装数
        completed_installs = await telemetry_collection.count_documents({
            "step": "install",
            "status": "completed",
            "metrics.success": True
        })
        
        # 计算成功率
        success_rate = (completed_installs / total_sessions * 100) if total_sessions > 0 else 0
        
        # 获取按操作系统划分的安装数
        os_pipeline = [
            {"$group": {
                "_id": "$osName",
                "count": {"$sum": 1}
            }},
            {"$match": {"_id": {"$ne": None}}}
        ]
        
        os_result = await telemetry_collection.aggregate(os_pipeline).to_list(None)
        installation_by_os = {item["_id"]: item["count"] for item in os_result}
        
        # 获取按步骤划分的状态统计
        steps_pipeline = [
            {"$group": {
                "_id": {"step": "$step", "status": "$status"},
                "count": {"$sum": 1}
            }}
        ]
        
        steps_result = await telemetry_collection.aggregate(steps_pipeline).to_list(None)
        
        steps_status = {}
        for item in steps_result:
            step = item["_id"]["step"]
            status = item["_id"]["status"]
            count = item["count"]
            
            if step not in steps_status:
                steps_status[step] = {}
            
            steps_status[step][status] = count
        
        # 计算平均安装时间
        time_pipeline = [
            {"$match": {
                "step": "install"
            }},
            {"$group": {
                "_id": "$sessionId",
                "minTime": {"$min": "$timestamp"},
                "maxTime": {"$max": "$timestamp"}
            }},
            {"$project": {
                "_id": 0,
                "duration": {"$subtract": ["$maxTime", "$minTime"]}
            }},
            {"$group": {
                "_id": None,
                "avgDuration": {"$avg": "$duration"}
            }}
        ]
        
        time_result = await telemetry_collection.aggregate(time_pipeline).to_list(None)
        avg_install_time = 0
        
        if time_result:
            # 转换为秒
            avg_install_time = time_result[0]["avgDuration"] / 1000 if time_result else 0
        
        return TelemetryStats(
            total_sessions=total_sessions,
            successful_installs=completed_installs,
            success_rate=success_rate,
            installation_by_os=installation_by_os,
            steps_status=steps_status,
            avg_install_time=avg_install_time
        )
    
    except Exception as e:
        logger.error(f"Error generating telemetry stats: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate telemetry statistics: {str(e)}"
        )

@router.get("/sessions/{session_id}/events")
async def get_session_events(session_id: str):
    """获取指定会话的事件序列"""
    try:
        events = await telemetry_collection.find(
            {"sessionId": session_id}
        ).sort("timestamp", 1).to_list(None)
        
        # 转换 ObjectId 为字符串
        for event in events:
            event["_id"] = str(event["_id"])
        
        if not events:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session with ID {session_id} not found"
            )
            
        return {"session_id": session_id, "events": events}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving session events: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve session events: {str(e)}"
        )

@router.get("/recent")
async def get_recent_sessions(limit: int = 10):
    """获取最近的安装会话"""
    try:
        # 获取最近安装完成的会话
        pipeline = [
            {"$match": {"step": "install"}},
            {"$sort": {"timestamp": -1}},
            {"$group": {
                "_id": "$sessionId",
                "lastEvent": {"$first": "$$ROOT"},
                "timestamp": {"$first": "$timestamp"}
            }},
            {"$sort": {"timestamp": -1}},
            {"$limit": limit}
        ]
        
        recent_sessions = await telemetry_collection.aggregate(pipeline).to_list(None)
        
        # 处理结果
        results = []
        for session in recent_sessions:
            session_id = session["_id"]
            
            # 获取该会话的安装成功/失败状态
            success = False
            if session["lastEvent"]["status"] == "completed" and session["lastEvent"].get("metrics", {}).get("success", False):
                success = True
                
            # 获取系统信息
            system_info = await telemetry_collection.find_one(
                {"sessionId": session_id, "osName": {"$exists": True}}
            )
            
            os_info = "Unknown"
            if system_info:
                os_name = system_info.get("osName", "")
                os_version = system_info.get("osVersion", "")
                os_info = f"{os_name} {os_version}".strip()
            
            # 获取会话持续时间
            first_event = await telemetry_collection.find_one(
                {"sessionId": session_id},
                sort=[("timestamp", 1)]
            )
            
            last_event = await telemetry_collection.find_one(
                {"sessionId": session_id},
                sort=[("timestamp", -1)]
            )
            
            duration = 0
            if first_event and last_event:
                duration = (last_event["timestamp"] - first_event["timestamp"]).total_seconds()
            
            results.append({
                "session_id": session_id,
                "timestamp": session["timestamp"],
                "success": success,
                "os": os_info,
                "duration_seconds": duration
            })
            
        return results
    
    except Exception as e:
        logger.error(f"Error retrieving recent sessions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve recent sessions: {str(e)}"
        )
    
# app/routers/telemetry.py 添加
@router.get("/anomalies")
async def get_anomalies():
    """检测异常并返回告警"""
    try:
        anomalies = await detect_failure_anomalies()
        return {"anomalies": anomalies}
    except Exception as e:
        logger.error(f"Error detecting anomalies: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to detect anomalies: {str(e)}"
        )