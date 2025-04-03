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
            "username": event.get("username"),
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
async def get_telemetry_stats(start_date: str = None):
    """获取遥测数据统计摘要，支持日期过滤"""
    try:
        # 处理起始日期过滤
        query = {}
        if start_date:
            try:
                start = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                query["timestamp"] = {"$gte": start}
            except (ValueError, TypeError):
                pass
        
        # 获取会话总数 - 基于所有唯一的会话ID
        sessions_pipeline = [
            {"$match": query}, # 移除对步骤的限制，获取所有记录
            {"$group": {
                "_id": "$sessionId" # 按会话ID分组
            }},
            {"$count": "total"} # 计数
        ]
        
        sessions_result = await telemetry_collection.aggregate(sessions_pipeline).to_list(None)
        total_sessions = sessions_result[0]["total"] if sessions_result else 0
        
        # 获取成功安装数 - 应用日期过滤
        successful_sessions_pipeline = [
            {"$match": {
                "step": "deploy",
                "status": "success",
                **query
            }},
            {"$group": {
                "_id": "$sessionId" # 确保每个会话只统计一次
            }},
            {"$count": "total"}
        ]
        
        successful_result = await telemetry_collection.aggregate(successful_sessions_pipeline).to_list(None)
        completed_installs = successful_result[0]["total"] if successful_result else 0
        
        # 计算成功率
        success_rate = (completed_installs / total_sessions * 100) if total_sessions > 0 else 0
        
        # 获取按操作系统划分的安装数
        os_pipeline = [
            {"$match": query},
            {"$group": {
                "_id": {
                    "sessionId": "$sessionId", 
                    "osName": "$osName"
                }
            }},
            {"$group": {
                "_id": "$_id.osName",
                "count": {"$sum": 1}
            }},
            {"$match": {"_id": {"$ne": None}}}
        ]
        
        os_result = await telemetry_collection.aggregate(os_pipeline).to_list(None)
        installation_by_os = {item["_id"]: item["count"] for item in os_result}
        
        # 获取按步骤划分的状态统计
        steps_pipeline = [
            {"$match": query},
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
            {"$match": query},
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
    """获取安装趋势数据，包括每日、每周和每月安装量"""
    try:
        # 处理起始日期过滤
        query = {}
        if start_date:
            try:
                start = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                query["timestamp"] = {"$gte": start}
            except (ValueError, TypeError):
                pass
        
        # 按天统计安装数量 - 修改为分开计算总安装和成功安装
        # 1. 首先统计所有唯一会话ID（总安装数）
        daily_sessions_pipeline = [
            {"$match": query},
            {"$sort": {"timestamp": 1}},
            {"$group": {
                "_id": {
                    "sessionId": "$sessionId",
                    "year": {"$year": "$timestamp"},
                    "month": {"$month": "$timestamp"},
                    "day": {"$dayOfMonth": "$timestamp"}
                },
                "timestamp": {"$first": "$timestamp"}
            }},
            {"$group": {
                "_id": {
                    "year": "$_id.year",
                    "month": "$_id.month",
                    "day": "$_id.day"
                },
                "total": {"$sum": 1},
                "date": {"$first": {
                    "$dateFromParts": {
                        "year": "$_id.year",
                        "month": "$_id.month",
                        "day": "$_id.day"
                    }
                }}
            }},
            {"$project": {
                "_id": 0,
                "date": 1,
                "total": 1
            }},
            {"$sort": {"date": 1}}
        ]
        
        # 2. 然后统计成功会话数（部署成功的会话）
        daily_success_pipeline = [
            {"$match": {
                "step": "deploy",
                "status": "success",
                **query
            }},
            {"$sort": {"timestamp": 1}},
            {"$group": {
                "_id": {
                    "sessionId": "$sessionId",
                    "year": {"$year": "$timestamp"},
                    "month": {"$month": "$timestamp"},
                    "day": {"$dayOfMonth": "$timestamp"}
                },
                "timestamp": {"$first": "$timestamp"}
            }},
            {"$group": {
                "_id": {
                    "year": "$_id.year",
                    "month": "$_id.month",
                    "day": "$_id.day"
                },
                "successful": {"$sum": 1},
                "date": {"$first": {
                    "$dateFromParts": {
                        "year": "$_id.year",
                        "month": "$_id.month",
                        "day": "$_id.day"
                    }
                }}
            }},
            {"$project": {
                "_id": 0,
                "date": 1,
                "successful": 1
            }},
            {"$sort": {"date": 1}}
        ]
        
        # 执行查询获取结果
        daily_sessions_result = await telemetry_collection.aggregate(daily_sessions_pipeline).to_list(None)
        daily_success_result = await telemetry_collection.aggregate(daily_success_pipeline).to_list(None)
        
        # 合并结果到一个字典
        daily_data = {}
        for item in daily_sessions_result:
            date_str = item["date"].strftime("%Y-%m-%d")
            daily_data[date_str] = {"date": date_str, "total": item["total"], "successful": 0}
        
        for item in daily_success_result:
            date_str = item["date"].strftime("%Y-%m-%d")
            if date_str in daily_data:
                daily_data[date_str]["successful"] = item["successful"]
            else:
                # 这种情况不应该发生，但为了健壮性添加
                daily_data[date_str] = {"date": date_str, "total": 0, "successful": item["successful"]}
        
        # 计算成功率并整理数据
        daily_installs = []
        for date_str, data in daily_data.items():
            success_rate = 0
            if data["total"] > 0:
                success_rate = (data["successful"] / data["total"]) * 100
            
            daily_installs.append({
                "date": date_str,
                "total": data["total"],
                "successful": data["successful"],
                "success_rate": success_rate
            })
        
        # 按日期排序
        daily_installs.sort(key=lambda x: x["date"])
        
        # 使用相同的方法修复周统计
        # 1. 总安装数（所有唯一会话）
        weekly_sessions_pipeline = [
            {"$match": query},
            {"$sort": {"timestamp": 1}},
            {"$group": {
                "_id": {
                    "sessionId": "$sessionId",
                    "year": {"$year": "$timestamp"},
                    "week": {"$week": "$timestamp"}
                },
                "timestamp": {"$first": "$timestamp"},
                "firstDay": {"$first": "$timestamp"}
            }},
            {"$group": {
                "_id": {
                    "year": "$_id.year",
                    "week": "$_id.week"
                },
                "total": {"$sum": 1},
                "week_start": {"$min": "$firstDay"}
            }},
            {"$sort": {"_id.year": 1, "_id.week": 1}}
        ]
        
        # 2. 成功安装数
        weekly_success_pipeline = [
            {"$match": {
                "step": "deploy",
                "status": "success",
                **query
            }},
            {"$sort": {"timestamp": 1}},
            {"$group": {
                "_id": {
                    "sessionId": "$sessionId",
                    "year": {"$year": "$timestamp"},
                    "week": {"$week": "$timestamp"}
                },
                "timestamp": {"$first": "$timestamp"},
                "firstDay": {"$first": "$timestamp"}
            }},
            {"$group": {
                "_id": {
                    "year": "$_id.year",
                    "week": "$_id.week"
                },
                "successful": {"$sum": 1},
                "week_start": {"$min": "$firstDay"}
            }},
            {"$sort": {"_id.year": 1, "_id.week": 1}}
        ]
        
        weekly_sessions_result = await telemetry_collection.aggregate(weekly_sessions_pipeline).to_list(None)
        weekly_success_result = await telemetry_collection.aggregate(weekly_success_pipeline).to_list(None)
        
        # 合并周数据
        weekly_data = {}
        for item in weekly_sessions_result:
            # 获取周开始日期（周一）
            week_start = item["week_start"]
            while week_start.weekday() != 0:  # 0代表周一
                week_start = week_start - timedelta(days=1)
            
            week_key = week_start.strftime("%Y-%m-%d")
            weekly_data[week_key] = {"week_start": week_key, "total": item["total"], "successful": 0}
        
        for item in weekly_success_result:
            # 获取周开始日期（周一）
            week_start = item["week_start"]
            while week_start.weekday() != 0:  # 0代表周一
                week_start = week_start - timedelta(days=1)
            
            week_key = week_start.strftime("%Y-%m-%d")
            if week_key in weekly_data:
                weekly_data[week_key]["successful"] = item["successful"]
            else:
                weekly_data[week_key] = {"week_start": week_key, "total": 0, "successful": item["successful"]}
        
        # 计算每周成功率
        weekly_installs = []
        for week_key, data in weekly_data.items():
            success_rate = 0
            if data["total"] > 0:
                success_rate = (data["successful"] / data["total"]) * 100
            
            weekly_installs.append({
                "week_start": week_key,
                "total": data["total"],
                "successful": data["successful"],
                "success_rate": success_rate
            })
            
        # 排序结果
        weekly_installs.sort(key=lambda x: x["week_start"])
        
        # 计算月度数据 - 从日数据中按月聚合
        monthly_data = {}
        
        # 从日数据中按月聚合
        for item in daily_installs:
            date = datetime.strptime(item["date"], "%Y-%m-%d")
            month_key = date.strftime("%Y-%m-01")  # 使用月的第一天作为键
            
            if month_key not in monthly_data:
                monthly_data[month_key] = {"month": month_key, "total": 0, "successful": 0}
            
            monthly_data[month_key]["total"] += item["total"]
            monthly_data[month_key]["successful"] += item["successful"]
        
        # 生成月度数据列表
        monthly_installs = []
        for month_key, data in monthly_data.items():
            success_rate = 0
            if data["total"] > 0:
                success_rate = (data["successful"] / data["total"]) * 100
                
            monthly_installs.append({
                "month": month_key,
                "total": data["total"],
                "successful": data["successful"],
                "success_rate": success_rate
            })
            
        # 排序月度数据
        monthly_installs.sort(key=lambda x: x["month"])
        
        # 获取今日、本周、本月的安装数据
        today = datetime.utcnow().strftime("%Y-%m-%d")
        this_week_start = (datetime.utcnow() - timedelta(days=datetime.utcnow().weekday())).strftime("%Y-%m-%d")
        this_month = datetime.utcnow().strftime("%Y-%m-01")
        
        today_data = next((item for item in daily_installs if item["date"] == today), {"total": 0, "successful": 0})
        this_week_data = next((item for item in weekly_installs if item["week_start"] == this_week_start), {"total": 0, "successful": 0})
        this_month_data = next((item for item in monthly_installs if item["month"] == this_month), {"total": 0, "successful": 0})
        
        # 汇总数据
        summary = {
            "today": {
                "total": today_data["total"],
                "successful": today_data["successful"]
            },
            "this_week": {
                "total": this_week_data["total"],
                "successful": this_week_data["successful"]
            },
            "this_month": {
                "total": this_month_data["total"],
                "successful": this_month_data["successful"]
            }
        }
            
        return {
            "daily_installs": daily_installs,
            "weekly_installs": weekly_installs,
            "monthly_installs": monthly_installs,
            "summary": summary
        }
    
    except Exception as e:
        logger.error(f"Error generating installation trends: {str(e)}")
        import traceback
        logger.error(f"Exception traceback: {traceback.format_exc()}")
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
        
        # 统计活跃用户 - 修改为使用 step=deploy, status=success 的条件
        active_pipeline = [
            {"$match": {
                "step": "deploy",
                "status": "success",
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
        # 构建查询条件 - 保持查询 install 步骤来获取所有会话
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
            
            # 检查是否有成功的 deploy 事件来判断成功状态
            deploy_success_event = await telemetry_collection.find_one({
                "sessionId": session_id,
                "step": "deploy",
                "status": "success"
            })
            
            is_success = bool(deploy_success_event)
            
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

@router.get("/debug_session/{session_id}")
async def debug_session(session_id: str):
    """调试特定会话的成功状态和所有事件"""
    try:
        # 获取该会话的所有事件
        events = await telemetry_collection.find({"sessionId": session_id}).sort("timestamp", 1).to_list(None)
        
        if not events:
            return {"status": "No events found for this session"}
        
        # 处理所有事件的ObjectId
        all_events = []
        for event in events:
            event_copy = {k: v for k, v in event.items() if k != "_id"}
            event_copy["_id"] = str(event["_id"])
            all_events.append(event_copy)
        
        # 查找安装和部署事件
        install_events = [e for e in events if e.get("step") == "install"]
        deploy_events = [e for e in events if e.get("step") == "deploy"]
        
        # 检查是否有成功的部署事件
        deploy_success_events = [e for e in deploy_events if e.get("status") == "success"]
        
        # 分析安装事件（保留旧指标以供参考）
        install_results = []
        for event in install_events:
            metrics = event.get("metrics", {})
            success_exists = "success" in metrics
            success_value = metrics.get("success")
            
            install_results.append({
                "event_id": str(event["_id"]),
                "timestamp": event.get("timestamp"),
                "status": event.get("status"),
                "success_field_exists": success_exists,
                "success_value": success_value,
                "success_type": str(type(success_value)),
                "would_count_as_success_old_rule": success_exists and success_value is True
            })
        
        # 分析部署事件（新规则）
        deploy_results = []
        for event in deploy_events:
            deploy_results.append({
                "event_id": str(event["_id"]),
                "timestamp": event.get("timestamp"),
                "status": event.get("status"),
                "would_count_as_success_new_rule": event.get("status") == "success"
            })
            
        return {
            "session_id": session_id,
            "total_events": len(events),
            "has_install_events": len(install_events) > 0,
            "has_deploy_events": len(deploy_events) > 0,
            "has_deploy_success_events": len(deploy_success_events) > 0,
            "is_success_by_new_rule": len(deploy_success_events) > 0,
            "install_events_analysis": install_results,
            "deploy_events_analysis": deploy_results,
            "all_events": all_events
        }
    
    except Exception as e:
        return {"error": str(e)}

@router.get("/users/overview")
async def get_users_overview(start_date: str = None):
    """
    获取用户概览数据，包括用户总数、活跃度指标和版本分布情况，包含匿名用户
    """
    try:
        # 处理起始日期过滤
        query = {}
        if start_date:
            try:
                start = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                query["timestamp"] = {"$gte": start}
            except (ValueError, TypeError):
                pass
        
        # 获取所有会话ID（包括匿名和有用户名的）
        all_sessions = await telemetry_collection.distinct("sessionId", query)
        total_sessions = len(all_sessions)
        
        # 获取用户名（非空的）
        named_users = await telemetry_collection.distinct("username", {
            "username": {"$exists": True, "$ne": None},
            **query
        })
        named_users_count = len(named_users)
        
        # 估算匿名用户数量 - 获取没有username但有anonymousId的记录
        anonymous_users_pipeline = [
            {"$match": {
                "$or": [
                    {"username": {"$exists": False}},
                    {"username": None}
                ],
                "anonymousId": {"$exists": True, "$ne": None},
                **query
            }},
            {"$group": {
                "_id": "$anonymousId"
            }},
            {"$count": "count"}
        ]
        
        anonymous_result = await telemetry_collection.aggregate(anonymous_users_pipeline).to_list(None)
        anonymous_count = anonymous_result[0]["count"] if anonymous_result else 0
        
        total_users = named_users_count + anonymous_count
        
        # 获取活跃用户数（过去30天有活动的用户，包括匿名用户）
        now = datetime.utcnow()
        thirty_days_ago = now - timedelta(days=30)
        
        active_users_pipeline = [
            {"$match": {
                "timestamp": {"$gte": thirty_days_ago},
                **query
            }},
            {"$group": {
                "_id": {
                    "$cond": [
                        {"$and": [
                            {"$eq": [{"$ifNull": ["$username", None]}, None]}
                        ]},
                        "$anonymousId",  # 如果没有username，就用anonymousId
                        "$username"      # 否则使用username
                    ]
                }
            }},
            {"$count": "active_count"}
        ]
        
        active_users_result = await telemetry_collection.aggregate(active_users_pipeline).to_list(None)
        active_users = active_users_result[0]["active_count"] if active_users_result else 0
        
        # 计算新用户（过去30天首次出现的用户）- 修复：添加此部分
        new_users_pipeline = [
            {"$match": {
                "timestamp": {"$gte": thirty_days_ago},
                **query
            }},
            {"$sort": {"timestamp": 1}},
            {"$group": {
                "_id": {
                    "$cond": [
                        {"$and": [
                            {"$eq": [{"$ifNull": ["$username", None]}, None]}
                        ]},
                        "$anonymousId",  # 如果没有username，就用anonymousId
                        "$username"      # 否则使用username
                    ]
                },
                "firstSeen": {"$first": "$timestamp"}
            }},
            {"$match": {
                "firstSeen": {"$gte": thirty_days_ago}
            }},
            {"$count": "new_user_count"}
        ]
        
        new_users_result = await telemetry_collection.aggregate(new_users_pipeline).to_list(None)
        new_users = new_users_result[0]["new_user_count"] if new_users_result else 0
        
        # 获取每月新用户趋势 - 修复：添加此部分
        monthly_new_users_pipeline = [
            {"$match": query},
            {"$sort": {"timestamp": 1}},
            {"$group": {
                "_id": {
                    "$cond": [
                        {"$and": [
                            {"$eq": [{"$ifNull": ["$username", None]}, None]}
                        ]},
                        "$anonymousId",  # 如果没有username，就用anonymousId
                        "$username"      # 否则使用username
                    ]
                },
                "firstSeen": {"$first": "$timestamp"}
            }},
            {"$project": {
                "year": {"$year": "$firstSeen"},
                "month": {"$month": "$firstSeen"}
            }},
            {"$group": {
                "_id": {
                    "year": "$year",
                    "month": "$month"
                },
                "count": {"$sum": 1}
            }},
            {"$sort": {"_id.year": 1, "_id.month": 1}}
        ]
        
        monthly_new_users = await telemetry_collection.aggregate(monthly_new_users_pipeline).to_list(None)
        
        # 格式化月份数据 - 修复：添加此部分
        new_users_trend = []
        for item in monthly_new_users:
            year = item["_id"]["year"]
            month = item["_id"]["month"]
            # 创建月份的第一天作为日期标识
            date_str = datetime(year, month, 1).strftime("%Y-%m-%d")
            new_users_trend.append({
                "date": date_str,
                "count": item["count"],
                "month_name": calendar.month_name[month]
            })
        
        # 获取版本分布情况 - 包括匿名用户
        version_users_pipeline = [
            {"$match": {
                "scriptVersion": {"$exists": True},
                **query
            }},
            {"$sort": {"timestamp": 1}},
            {"$group": {
                "_id": {
                    "$cond": [
                        {"$and": [
                            {"$eq": [{"$ifNull": ["$username", None]}, None]}
                        ]},
                        "$anonymousId",  # 如果没有username，就用anonymousId
                        "$username"      # 否则使用username
                    ]
                },
                "latestVersion": {"$last": "$scriptVersion"},
                "lastSeen": {"$last": "$timestamp"},
                "isAnonymous": {"$last": {"$cond": [
                    {"$and": [
                        {"$eq": [{"$ifNull": ["$username", None]}, None]}
                    ]},
                    True,
                    False
                ]}}
            }},
            {"$group": {
                "_id": {"$ifNull": ["$latestVersion", "未知版本"]},
                "userCount": {"$sum": 1},
                "anonymousCount": {"$sum": {"$cond": ["$isAnonymous", 1, 0]}},
                "namedCount": {"$sum": {"$cond": ["$isAnonymous", 0, 1]}},
                "users": {"$push": {
                    "id": "$_id", 
                    "lastSeen": "$lastSeen",
                    "isAnonymous": "$isAnonymous"
                }}
            }},
            {"$project": {
                "userCount": 1,
                "anonymousCount": 1,
                "namedCount": 1,
                "activeUsers": {
                    "$size": {
                        "$filter": {
                            "input": "$users",
                            "as": "user",
                            "cond": {"$gte": ["$$user.lastSeen", thirty_days_ago]}
                        }
                    }
                }
            }},
            {"$sort": {"userCount": -1}}
        ]
        
        version_users = await telemetry_collection.aggregate(version_users_pipeline).to_list(None)
        version_distribution = []
        
        for item in version_users:
            version = str(item["_id"]) if item["_id"] is not None else "未知版本"
            version_distribution.append({
                "version": version,
                "userCount": item["userCount"],
                "anonymousCount": item["anonymousCount"],
                "namedCount": item["namedCount"],
                "activeUsers": item["activeUsers"],
                "activePercentage": round((item["activeUsers"] / item["userCount"]) * 100, 1) if item["userCount"] > 0 else 0
            })
            
        # 获取版本采用趋势（按月），包括匿名用户 - 修复：更新查询以包括匿名用户
        version_trend_pipeline = [
            {"$match": {
                "scriptVersion": {"$exists": True, "$ne": None},
                **query
            }},
            {"$sort": {"timestamp": 1}},
            {"$group": {
                "_id": {
                    "$cond": [
                        {"$and": [
                            {"$eq": [{"$ifNull": ["$username", None]}, None]}
                        ]},
                        "$anonymousId",  # 如果没有username，就用anonymousId
                        "$username"      # 否则使用username
                    ]
                },
                "firstVersion": {"$first": "$scriptVersion"},
                "firstSeen": {"$first": "$timestamp"},
                "year": {"$first": {"$year": "$timestamp"}},
                "month": {"$first": {"$month": "$timestamp"}}
            }},
            {"$group": {
                "_id": {
                    "year": "$year",
                    "month": "$month",
                    "version": "$firstVersion"
                },
                "count": {"$sum": 1}
            }},
            {"$sort": {"_id.year": 1, "_id.month": 1}}
        ]
        
        version_trend = await telemetry_collection.aggregate(version_trend_pipeline).to_list(None)
        
        # 格式化版本趋势数据
        version_adoption_trend = []
        for item in version_trend:
            year = item["_id"]["year"]
            month = item["_id"]["month"]
            version = str(item["_id"]["version"]) 
            date_str = datetime(year, month, 1).strftime("%Y-%m-%d")
            version_adoption_trend.append({
                "date": date_str,
                "version": version,
                "count": item["count"],
                "month_name": calendar.month_name[month]
            })
        
        # 获取最活跃的用户列表（top N），包括匿名用户 - 修复：更新查询以包括匿名用户
        top_users_pipeline = [
            {"$match": query}, # 移除username过滤以包含所有类型用户
            {"$group": {
                "_id": {
                    "$cond": [
                        {"$and": [
                            {"$eq": [{"$ifNull": ["$username", None]}, None]}
                        ]},
                        "$anonymousId",  # 如果没有username，就用anonymousId
                        "$username"      # 否则使用username
                    ]
                },
                "isAnonymous": {"$last": {"$cond": [
                    {"$and": [
                        {"$eq": [{"$ifNull": ["$username", None]}, None]}
                    ]},
                    True,
                    False
                ]}},
                "installCount": {"$sum": {"$cond": [{"$eq": ["$step", "install"]}, 1, 0]}},
                "deployCount": {"$sum": {"$cond": [{"$eq": ["$step", "deploy"]}, 1, 0]}},
                "successCount": {"$sum": {"$cond": [
                    {"$and": [{"$eq": ["$step", "deploy"]}, {"$eq": ["$status", "success"]}]}, 
                    1, 0
                ]}},
                "lastSeen": {"$max": "$timestamp"},
                "latestVersion": {"$last": "$scriptVersion"}
            }},
            {"$sort": {"successCount": -1, "installCount": -1}},
            {"$limit": 10}
        ]
        
        top_users_result = await telemetry_collection.aggregate(top_users_pipeline).to_list(None)
        top_users = []
        
        for user in top_users_result:
            user_id = user["_id"]
            # 匿名用户显示为"anonymous_"+前8位ID
            display_name = user_id if not user["isAnonymous"] else f"匿名用户_{user_id[:8] if user_id else 'unknown'}"
            
            top_users.append({
                "username": display_name,
                "isAnonymous": user["isAnonymous"],
                "installCount": user["installCount"],
                "deployCount": user["deployCount"],
                "successCount": user["successCount"],
                "lastSeen": user["lastSeen"],
                "latestVersion": user["latestVersion"] if user["latestVersion"] else "未知版本",
                "isActive": (now - user["lastSeen"]).total_seconds() < (30 * 24 * 60 * 60)  # 30天内活跃
            })
            
        return {
            "total_users": total_users,
            "named_users": named_users_count, 
            "anonymous_users": anonymous_count,
            "active_users": active_users,
            "inactive_users": total_users - active_users,
            "new_users_30d": new_users,  # 修复：现在有定义了
            "new_users_trend": new_users_trend,  # 修复：现在有定义了
            "version_distribution": version_distribution,
            "version_adoption_trend": version_adoption_trend,
            "top_users": top_users
        }
    
    except Exception as e:
        logger.error(f"Error generating user overview: {str(e)}")
        # 添加更多详细的错误日志，帮助调试
        import traceback
        logger.error(f"Exception traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate user overview: {str(e)}"
        )

@router.get("/users/{username}")
async def get_user_details(username: str, start_date: str = None):
    """
    获取指定用户的详细信息
    """
    try:
        # 处理起始日期过滤
        query = {"username": username}
        if start_date:
            try:
                start = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                query["timestamp"] = {"$gte": start}
            except (ValueError, TypeError):
                pass
        
        # 检查用户是否存在
        user_exists = await telemetry_collection.count_documents({"username": username}) > 0
        if not user_exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User '{username}' not found"
            )
        
        # 用户基本统计数据
        user_stats_pipeline = [
            {"$match": query},
            {"$group": {
                "_id": "$username",
                "installCount": {"$sum": {"$cond": [{"$eq": ["$step", "install"]}, 1, 0]}},
                "deployCount": {"$sum": {"$cond": [{"$eq": ["$step", "deploy"]}, 1, 0]}},
                "successCount": {"$sum": {"$cond": [
                    {"$and": [{"$eq": ["$step", "deploy"]}, {"$eq": ["$status", "success"]}]}, 
                    1, 0
                ]}},
                "firstSeen": {"$min": "$timestamp"},
                "lastSeen": {"$max": "$timestamp"},
                "versions": {"$addToSet": "$scriptVersion"},
                "sessions": {"$addToSet": "$sessionId"}
            }},
            {"$project": {
                "installCount": 1,
                "deployCount": 1,
                "successCount": 1,
                "successRate": {
                    "$cond": [
                        {"$gt": ["$deployCount", 0]},
                        {"$multiply": [{"$divide": ["$successCount", "$deployCount"]}, 100]},
                        0
                    ]
                },
                "firstSeen": 1,
                "lastSeen": 1,
                "daysSinceFirstSeen": {
                    "$divide": [
                        {"$subtract": [datetime.utcnow(), "$firstSeen"]},
                        24 * 60 * 60 * 1000
                    ]
                },
                "daysSinceLastSeen": {
                    "$divide": [
                        {"$subtract": [datetime.utcnow(), "$lastSeen"]},
                        24 * 60 * 60 * 1000
                    ]
                },
                "versions": 1,
                "versionCount": {"$size": "$versions"},
                "sessionCount": {"$size": "$sessions"}
            }}
        ]
        
        user_stats_result = await telemetry_collection.aggregate(user_stats_pipeline).to_list(None)
        user_stats = user_stats_result[0] if user_stats_result else {}
        
        # 获取用户版本历史
        version_history_pipeline = [
            {"$match": query},
            {"$sort": {"timestamp": 1}},
            {"$group": {
                "_id": {
                    "sessionId": "$sessionId", 
                    "version": "$scriptVersion"
                },
                "firstSeen": {"$first": "$timestamp"},
                "step": {"$first": "$step"},
                "status": {"$first": "$status"}
            }},
            {"$match": {"_id.version": {"$ne": None}}},
            {"$sort": {"firstSeen": 1}}
        ]
        
        version_history_result = await telemetry_collection.aggregate(version_history_pipeline).to_list(None)
        version_history = []
        
        for entry in version_history_result:
            version_history.append({
                "timestamp": entry["firstSeen"],
                "version": entry["_id"]["version"],
                "sessionId": entry["_id"]["sessionId"],
                "step": entry["step"],
                "status": entry["status"]
            })
            
        # 获取用户最近的会话列表
        recent_sessions_pipeline = [
            {"$match": query},
            {"$sort": {"timestamp": -1}},
            {"$group": {
                "_id": "$sessionId",
                "firstEvent": {"$last": "$timestamp"},
                "lastEvent": {"$first": "$timestamp"},
                "scriptVersion": {"$first": "$scriptVersion"}
            }},
            {"$project": {
                "sessionId": "$_id",
                "firstEvent": 1,
                "lastEvent": 1,
                "duration": {"$subtract": ["$lastEvent", "$firstEvent"]},
                "scriptVersion": 1
            }},
            {"$sort": {"lastEvent": -1}},
            {"$limit": 10}
        ]
        
        recent_sessions_result = await telemetry_collection.aggregate(recent_sessions_pipeline).to_list(None)
        recent_sessions = []
        
        for session in recent_sessions_result:
            # 查询该会话是否成功
            success_result = await telemetry_collection.count_documents({
                "sessionId": session["sessionId"],
                "step": "deploy",
                "status": "success"
            })
            
            recent_sessions.append({
                "sessionId": session["sessionId"],
                "startTime": session["firstEvent"],
                "endTime": session["lastEvent"],
                "duration_seconds": session["duration"] / 1000 if session["duration"] else 0,
                "version": session["scriptVersion"] or "未知版本",
                "success": success_result > 0
            })
        
        return {
            "username": username,
            "stats": user_stats,
            "version_history": version_history,
            "recent_sessions": recent_sessions,
            "is_active": user_stats.get("daysSinceLastSeen", 999) <= 30 if user_stats else False
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving user details for {username}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve user details: {str(e)}"
        )