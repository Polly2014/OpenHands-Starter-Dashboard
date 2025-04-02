import pymongo
from dotenv import load_dotenv
import os

# 加载环境变量
load_dotenv()

# MongoDB 连接配置
mongodb_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
mongodb_db = os.getenv("MONGODB_DB", "openhands_telemetry")

# 连接到 MongoDB
client = pymongo.MongoClient(mongodb_uri)
db = client[mongodb_db]

# 清空特定集合的所有文档
result = db.telemetry_events.delete_many({})
print(f"已删除 {result.deleted_count} 条文档")

# 如需删除整个数据库，取消下面的注释
# client.drop_database(mongodb_db)
# print(f"已删除数据库 {mongodb_db}")

client.close()