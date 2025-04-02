# app/routers/telemetry.py
from fastapi import APIRouter, HTTPException, status
from datetime import datetime, timedelta
from typing import Dict, Any, List
import calendar

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

@router.get("/trends")
async def get_installation_trends(start_date: str = None):
    """获取安装趋势数据，包括每日和每周安装量"""
    try:
        # 处理起始日期过滤
        query = {}
        if start_date:
            try:
                start = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                query["timestamp"] = {"$gte": start}
            except (ValueError, TypeError):
                pass
        
        # 按天统计安装数量
        daily_pipeline = [
            {"$match": {"step": "install", **query}},
            {"$group": {
                "_id": {
                    "year": {"$year": "$timestamp"},
                    "month": {"$month": "$timestamp"},
                    "day": {"$dayOfMonth": "$timestamp"},
                    "success": {"$cond": [
                        {"$and": [
                            {"$eq": ["$status", "completed"]},
                            {"$eq": [{"$ifNull": ["$metrics.success", False]}, True]}
                        ]},
                        True,
                        False
                    ]}
                },
                "count": {"$sum": 1}
            }},
            {"$project": {
                "_id": 0,
                "date": {
                    "$dateFromParts": {
                        "year": "$_id.year",
                        "month": "$_id.month",
                        "day": "$_id.day"
                    }
                },
                "success": "$_id.success",
                "count": 1
            }},
            {"$sort": {"date": 1}}
        ]
        
        daily_results = await telemetry_collection.aggregate(daily_pipeline).to_list(None)
        
        # 重新组织日期数据，计算每天的总安装数和成功率
        daily_data = {}
        for item in daily_results:
            date_str = item["date"].strftime("%Y-%m-%d")
            if date_str not in daily_data:
                daily_data[date_str] = {"date": date_str, "count": 0, "successful": 0}
            
            daily_data[date_str]["count"] += item["count"]
            if item["success"]:
                daily_data[date_str]["successful"] += item["count"]
        
        # 计算成功率
        daily_installs = []
        for date_str, data in daily_data.items():
            if data["count"] > 0:
                data["success_rate"] = (data["successful"] / data["count"]) * 100
            else:
                data["success_rate"] = 0
            daily_installs.append(data)
        
        # 按周统计安装数量（每周的开始日期为周一）
        weekly_pipeline = [
            {"$match": {"step": "install", **query}},
            {"$group": {
                "_id": {
                    "year": {"$year": "$timestamp"},
                    "week": {"$week": "$timestamp"}
                },
                "count": {"$sum": 1},
                "firstDay": {"$min": "$timestamp"}
            }},
            {"$project": {
                "_id": 0,
                "week_start": "$firstDay",
                "year": "$_id.year",
                "week": "$_id.week",
                "count": 1
            }},
            {"$sort": {"year": 1, "week": 1}}
        ]
        
        weekly_results = await telemetry_collection.aggregate(weekly_pipeline).to_list(None)
        
        # 确保每周的开始日期是周一
        weekly_installs = []
        for item in weekly_results:
            # 获取周开始日期（周一）
            week_start = item["week_start"]
            # 调整到当周的周一
            while week_start.weekday() != 0:  # 0代表周一
                week_start = week_start - timedelta(days=1)
            
            weekly_installs.append({
                "week_start": week_start.strftime("%Y-%m-%d"),
                "count": item["count"]
            })
        
        return {
            "daily_installs": daily_installs,
            "weekly_installs": weekly_installs
        }
    
    except Exception as e:
        logger.error(f"Error generating installation trends: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate installation trends: {str(e)}"
        )

@router.get("/users")
async def get_users_statistics(start_date: str = None):
    """获取用户统计数据，包括独立用户数和活跃度"""
    try:
        # 处理起始日期过滤
        query = {}
        if start_date:
            try:
                start = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                query["timestamp"] = {"$gte": start}
            except (ValueError, TypeError):
                pass
        
        # 统计独立用户数（基于anonymousId）
        unique_users = await telemetry_collection.distinct("anonymousId", query)
        unique_count = len([uid for uid in unique_users if uid])  # 过滤掉空值
        
        # 统计活跃用户（在选定时间段内有多次安装行为的用户）
        active_pipeline = [
            {"$match": {
                "step": "install",
                "status": "completed",
                "anonymousId": {"$ne": None},
                **query
            }},
            {"$group": {
                "_id": "$anonymousId",
                "session_count": {"$sum": 1},
                "last_seen": {"$max": "$timestamp"}
            }},
            {"$sort": {"session_count": -1}}
        ]
        
        user_sessions = await telemetry_collection.aggregate(active_pipeline).to_list(None)
        
        # 计算重复安装的用户数量
        returning_users = len([u for u in user_sessions if u["session_count"] > 1])
        
        # 计算每用户平均安装次数
        total_sessions = sum(u["session_count"] for u in user_sessions)
        avg_sessions = total_sessions / unique_count if unique_count > 0 else 0
        
        # 定义活跃用户：在过去30天内有任何活动的用户
        now = datetime.utcnow()
        thirty_days_ago = now - timedelta(days=30)
        active_users = len([u for u in user_sessions if u["last_seen"] > thirty_days_ago])
        
        return {
            "unique_users": unique_count,
            "active_users": active_users,
            "returning_users": returning_users,
            "avg_sessions_per_user": avg_sessions,
            "total_sessions": total_sessions
        }
    
    except Exception as e:
        logger.error(f"Error generating user statistics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate user statistics: {str(e)}"
        )

# 增强get_recent_sessions函数，支持日期和成功状态过滤
@router.get("/recent")
async def get_recent_sessions(limit: int = 10, start_date: str = None, success: bool = None):
    """获取最近的安装会话，支持日期和成功状态过滤"""
    try:
        # 构建查询条件
        match_query = {"step": "install"}
        
        # 处理日期过滤
        if start_date:
            try:
                start = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                match_query["timestamp"] = {"$gte": start}
            except (ValueError, TypeError):
                pass
        
        # 获取最近安装完成的会话
        pipeline = [
            {"$match": match_query},
            {"$sort": {"timestamp": -1}},
            {"$group": {
                "_id": "$sessionId",
                "lastEvent": {"$first": "$$ROOT"},
                "timestamp": {"$first": "$timestamp"}
            }},
            {"$sort": {"timestamp": -1}}
        ]
        
        recent_sessions = await telemetry_collection.aggregate(pipeline).to_list(None)
        
        # 处理结果
        results = []
        for session in recent_sessions:
            session_id = session["_id"]
            
            # 获取该会话的安装成功/失败状态
            is_success = False
            if session["lastEvent"]["status"] == "completed" and session["lastEvent"].get("metrics", {}).get("success", False):
                is_success = True
            
            # 应用成功状态过滤（如果指定）
            if success is not None and is_success != success:
                continue
                
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
                "success": is_success,
                "os": os_info,
                "duration_seconds": duration
            })
            
            # 应用数量限制
            if len(results) >= limit:
                break
                
        return results
    
    except Exception as e:
        logger.error(f"Error retrieving recent sessions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve recent sessions: {str(e)}"
        )