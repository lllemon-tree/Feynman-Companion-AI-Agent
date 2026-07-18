# test_db.py
from app.core.database import create_db_and_tables

# 【极其关键的一步】：必须在这里导入你刚才写的那些表。
# 只有被导入了，SQLModel 才能在内存里“看到”它们，进而去数据库里建表。
from backend.app.models.knowledge import Material, Chapter, Chunk, KP

if __name__ == "__main__":
    print("🚀 准备连接 SQLite...")
    print("🔨 开始创建数据库和表结构...")
    
    # 调用建表函数
    create_db_and_tables()
    
    print("✅ 执行完毕！请看左侧资源管理器，有没有多出一个 feynman.db 文件？")