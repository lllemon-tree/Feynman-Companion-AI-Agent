# database.py
from sqlalchemy import inspect, text
from sqlmodel import SQLModel, create_engine, Session

# 1. 定义数据库文件的位置。
# 这里的 "sqlite:///feynman.db" 表示在当前运行目录下创建一个名为 feynman.db 的 SQLite 数据库文件。
SQLITE_URL = "sqlite:///feynman.db"

# 2. 创建引擎 (Engine)。
# Engine 是负责和数据库对话的底层核心。
# connect_args={"check_same_thread": False} 是 SQLite 在 FastAPI (异步框架) 中常加的参数，避免多线程报错。
# SQL 调试日志默认关闭，避免大模型调用时被大量查询日志淹没。
engine = create_engine(SQLITE_URL, echo=False, connect_args={"check_same_thread": False})

def create_db_and_tables():
    """
    初始化数据库表。
    当程序启动时调用此函数，SQLModel 会检查 models 中定义的所有 table=True 的类，
    并在 feynman.db 中自动执行 CREATE TABLE 语句。
    """
    from backend.app.models.knowledge import Material, Chunk, Chapter, KP, LearnSession
    SQLModel.metadata.create_all(engine)
    with engine.begin() as connection:
        columns = {column["name"] for column in inspect(connection).get_columns("material")}
        if "name" not in columns:
            connection.execute(text("ALTER TABLE material ADD COLUMN name VARCHAR"))
        connection.execute(
            text("UPDATE material SET name = filename WHERE name IS NULL OR name = ''")
        )

def get_session():
    """
    获取数据库会话 (Session)。
    Session 是你实际用来执行查询 (SELECT) 和写入 (INSERT) 的临时通道。
    使用 yield 是为了配合 FastAPI 的依赖注入系统。
    """
    with Session(engine) as session:
        yield session
