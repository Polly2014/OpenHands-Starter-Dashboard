# test_api.py
import requests
import json
from datetime import datetime

# 配置
API_URL = "http://localhost:9999"

# 测试数据
test_data = {
    "anonymousId": "test123",
    "sessionId": f"test-session-{datetime.now().strftime('%Y%m%d%H%M%S')}",
    "step": "install",
    "status": "completed",
    "timestamp": datetime.utcnow().isoformat(),
    "scriptVersion": "1.0",
    "osVersion": "Windows 10",
    "osName": "Windows",
    "cpuArchitecture": "x64",
    "memoryGB": 16,
    "metrics": {
        "success": True,
        "duration_seconds": 120
    }
}

# 发送测试数据
print(f"发送数据到 {API_URL}/api/telemetry")
response = requests.post(f"{API_URL}/api/telemetry", json=test_data)
print(f"状态码: {response.status_code}")
print(f"响应: {response.text}")

# 获取统计数据确认
print("\n获取统计数据")
stats_response = requests.get(f"{API_URL}/api/telemetry/stats")
print(f"状态码: {stats_response.status_code}")
print(f"响应: {json.dumps(stats_response.json(), indent=2)}")