# database.py
from sqlmodel import SQLModel, create_engine, Session

# 1. 定义数据库文件的位置。
# 这里的 "sqlite:///feynman.db" 表示在当前运行目录下创建一个名为 feynman.db 的 SQLite 数据库文件。
SQLITE_URL = "sqlite:///feynman.db"

# 2. 创建引擎 (Engine)。
# Engine 是负责和数据库对话的底层核心。
# connect_args={"check_same_thread": False} 是 SQLite 在 FastAPI (异步框架) 中常加的参数，避免多线程报错。
# echo=True 会在终端打印出底层执行的 SQL 语句，方便开发时排错，上线时可以改为 False。
engine = create_engine(SQLITE_URL, echo=True, connect_args={"check_same_thread": False})

def create_db_and_tables():
    """
    初始化数据库表。
    当程序启动时调用此函数，SQLModel 会检查 models 中定义的所有 table=True 的类，
    并在 feynman.db 中自动执行 CREATE TABLE 语句。
    """
    from backend.app.models.knowledge import Material, Chunk, Chapter, KP, LearnSession
    SQLModel.metadata.create_all(engine)

def get_session():
    """
    获取数据库会话 (Session)。
    Session 是你实际用来执行查询 (SELECT) 和写入 (INSERT) 的临时通道。
    使用 yield 是为了配合 FastAPI 的依赖注入系统。
    """
    with Session(engine) as session:
        yield session