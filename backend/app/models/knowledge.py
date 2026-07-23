# knowledge.py
from datetime import datetime, timezone
from typing import Any, List, Optional

from pydantic import BaseModel, model_validator
from sqlmodel import Field, SQLModel

# 辅助函数：生成当前的 UTC 时间，用作创建和更新时间的默认值
def utc_now():
    return datetime.now(timezone.utc)

# ---------------------------------------------------------
# 1. Material (教材表)
# ---------------------------------------------------------
class Material(SQLModel, table=True):
    __tablename__ = "material" # 显式指定表名为小写

    # 主键，类似 "mat-xxx"。因为是我们自己生成的字符串，所以不使用自增。
    id: str = Field(primary_key=True)
    subject: str                  # 科目：计算机/政治/数学等
    name: Optional[str] = None     # 用户填写的教材展示名称
    filename: str                 # 原始文件名
    raw_path: str                 # 本地存储路径
    
    # default_factory 允许传入一个函数，在插入数据时自动执行该函数生成值
    uploaded_at: datetime = Field(default_factory=utc_now)
    
    # 状态枚举：parsing/chunking/extracting/generating/done/failed
    status: str = Field(default="parsing")
    progress_step: Optional[str] = None  # 当前步骤文案
    progress: float = Field(default=0.0) # 0~1 的进度值
    error: Optional[str] = None          # 失败原因

# ---------------------------------------------------------
# 2. Chapter (章节表)
# ---------------------------------------------------------
class Chapter(SQLModel, table=True):
    __tablename__ = "chapter"

    id: str = Field(primary_key=True)
    
    # 外键：告诉数据库该字段关联 material 表的 id 字段。
    # ondelete="CASCADE" 意味着如果教材被删了，它下面的所有章节也会自动被数据库删除。
    material_id: str = Field(foreign_key="material.id", ondelete="CASCADE")
    
    chapter_no: Optional[str] = None     # 章节号，如 "第6章"
    title: str                           # 标题，如 "图论"
    page_start: Optional[int] = None     # 章节起始页
    page_end: Optional[int] = None       # 章节结束页

# ---------------------------------------------------------
# 3. Chunk (切片表)
# ---------------------------------------------------------
class Chunk(SQLModel, table=True):
    __tablename__ = "chunk"

    id: str = Field(primary_key=True)
    material_id: str = Field(foreign_key="material.id", ondelete="CASCADE")
    
    # 按照 PRD：未分章时 chapter_id 为空，所以类型是 Optional[str]
    # ondelete="SET NULL" 意味着如果章节被删，切片不删除，只是归属章节字段置空。
    chapter_id: Optional[str] = Field(default=None, foreign_key="chapter.id", ondelete="SET NULL")
    
    page_no: int    # 切片所在页码，这是后续知识点找原文的关键
    seq: int        # 同页内的顺序，保证拼接时文本连贯
    text: str       # 切片的具体文本内容

# ---------------------------------------------------------
# 4. KP (知识点表)
# ---------------------------------------------------------
class KP(SQLModel, table=True):
    __tablename__ = "kp"

    id: str = Field(primary_key=True)
    chapter_id: str = Field(foreign_key="chapter.id", ondelete="CASCADE")
    
    name: str                       # 知识点名称
    summary: Optional[str] = None   # 一句话摘要
    rubric: Optional[str] = None    # 四维 JSON 字符串，初始生成前为空
    
    # grounding (文本溯源) 的关键入口
    page_start: int
    page_end: int
    
    # 状态枚举：done/failed/pending_regenerate
    status: str = Field(default="pending_regenerate")
    
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


# ---------------------------------------------------------
# 5. LearnSession (對話/追問會話表)
# 注意：為了避免與 sqlmodel 的 Session 衝突，類別命名為 LearnSession
# ---------------------------------------------------------
class LearnSession(SQLModel, table=True):
    __tablename__ = "session" # 在資料庫中的實體表名依然是 session

    id: str = Field(primary_key=True)      # 例如 "sess-xxx"
    kp_id: str                             # 關聯的知識點 (Knowledge Point) ID
    status: str = Field(default="ongoing") # 狀態：ongoing(進行中), completed(已完成), failed(失敗)
    current_turn: int = Field(default=0)   # 記錄當前是第幾輪追問 (依 PRD，最多 3 輪)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


# ==========================================
# 下方是 API 接口的数据传输模型 (Pydantic Schemas)
# 与上面的 SQLModel(数据库模型) 不同，这些仅用于规范接口的输入输出格式
# ==========================================

# 1. 查询状态接口的内部 Data 结构
class MaterialStatusData(BaseModel):
    material_id: str
    status: str
    step: str
    progress: float
    error: Optional[str] = None

# 1.1 查询状态接口的完整响应外壳
class MaterialStatusResponse(BaseModel):
    code: int = 200
    msg: str = "success"
    data: MaterialStatusData

# ------------------------------------------

# 1.2 科目列表接口
class SubjectListResponse(BaseModel):
    code: int = 200
    msg: str = "success"
    data: List[str]

# ------------------------------------------

# 2. 知识点树接口的层级嵌套结构 (从内向外定义)
class KnowledgePointItem(BaseModel):
    kp_id: str
    name: str
    summary: str
    page_start: int
    page_end: int
    status: str
    tag: Optional[str] = None # 预留给 "高频考点" 等标签

class ChapterItem(BaseModel):
    chapter_id: str
    title: str
    knowledge_points: List[KnowledgePointItem]

class MaterialTreeData(BaseModel):
    material_id: str
    title: str
    status: str
    step: Optional[str] = None
    progress: float = 0.0
    error: Optional[str] = None
    chapters: List[ChapterItem]


# 2.1 知识点树接口的完整响应外壳
class MaterialTreeResponse(BaseModel):
    code: int = 200
    msg: str = "success"
    data: List[MaterialTreeData]  # 外层是一个列表，包含多个教材的树状结构

# ---------------------------------------------------------
# 3. 上传接口 (POST /api/v1/material/upload)
# ---------------------------------------------------------
class MaterialUploadData(BaseModel):
    material_id: str
    status: str

class MaterialUploadResponse(BaseModel):
    code: int = 200
    msg: str = "success"
    data: MaterialUploadData

 # ==========================================
# 知识点 (KP) 相关 API 模型
# ==========================================

# ---------------------------------------------------------
# 1. 查询详情 (GET /api/v1/kp/{kp_id})
# 场景：前端点击某个知识点，想要看大模型生成的详细解析和引用的原文
# ---------------------------------------------------------

class RubricDimension(BaseModel):
    name: str
    content: Any


class KPRubric(BaseModel):
    concept_prerequisite: RubricDimension = Field(
        default_factory=lambda: RubricDimension(name="概念前提", content="暂无说明")
    )
    core_mechanism: RubricDimension = Field(
        default_factory=lambda: RubricDimension(name="核心机制", content="暂无说明")
    )
    principle_proof: RubricDimension = Field(
        default_factory=lambda: RubricDimension(name="原理证明", content="暂无说明")
    )
    common_misunderstandings: RubricDimension = Field(
        default_factory=lambda: RubricDimension(name="常见误区", content=[])
    )

class KPSourceChunk(BaseModel):
    """
    大模型生成解析时，参考的 PDF 原文切片 (用于文本溯源 Grounding)。
    """
    chunk_id: str
    page: int   # 原文在第几页
    text: str   # 原文的具体文字内容

class KPDetailData(BaseModel):
    """详情接口的核心数据区"""
    kp_id: str
    name: str                            # 知识点名称
    summary: str                         # 一句话摘要
    page_start: int
    page_end: int
    status: str
    rubric: KPRubric                     # 嵌套上面的四维解析
    source_chunks: List[KPSourceChunk]   # 嵌套上面的原文切片列表

class KPDetailResponse(BaseModel):
    """详情接口的最终返回外壳 (前端直接接这个)"""
    code: int = 200
    msg: str = "success"
    data: KPDetailData


# ==========================================
# 大模型内部交互契约 (LLM Data Contracts)
# ==========================================

class ExtractedKP(BaseModel):
    """单条知识点提取结构"""
    name: str = Field(..., description="知识点名称")
    summary: str = Field(..., description="知识点摘要")
    page_no: int = Field(..., description="物理页码")


# 知识点提取并生成四维Rubric
class KPExtractionResponse(BaseModel):
    """知识点提取的完整 JSON 响应结构"""
    knowledge_points: List[ExtractedKP] = Field(default_factory=list)

class RubricSchema(BaseModel):
    concept_prerequisite: str = Field(..., description="概念前提解释")
    core_mechanism: str = Field(..., description="核心运行机制")
    principle_proof: str = Field(..., description="原理证明与必要性")
    common_misunderstandings: List[str] = Field(..., description="4个常见的认知误区")
# ---------------------------------------------------------
# 2. 新增知识点 (POST /api/v1/kp)
# 场景：用户手动圈定了几页 PDF，想要新建一个知识点
# ---------------------------------------------------------

class KPCreateRequest(BaseModel):
    """
    【注意】：以 Request 结尾的，代表这是“前端发给后端”的数据格式。
    FastAPI 会用这个模型来严格检查前端发来的 JSON 对不对。
    """
    chapter_id: str                      # 挂载在哪个章节下
    name: str                            # 用户起的知识点名字
    page_start: int = Field(ge=1)        # 起始页码
    page_end: int = Field(ge=1)          # 结束页码
    summary: Optional[str] = ""          # 摘要，允许前端不传，不传默认为空字符串

    @model_validator(mode="after")
    def validate_page_range(self):
        if self.page_end < self.page_start:
            raise ValueError("page_end must be greater than or equal to page_start")
        return self

class KPCreateData(BaseModel):
    """新增成功后，后端返回给前端的核心数据"""
    kp_id: str                           # 后端新生成的 ID
    status: str                          # 状态通常是 pending_regenerate (排队等大模型生成)

class KPCreateResponse(BaseModel):
    """新增接口的最终返回外壳"""
    code: int = 200
    msg: str = "success"
    data: KPCreateData


# ---------------------------------------------------------
# 3. 修改知识点 (PATCH /api/v1/kp/{kp_id})
# 场景：用户发现页码标错了，或者想改个名字。
# ---------------------------------------------------------

class KPUpdateRequest(BaseModel):
    """
    前端发来的修改请求。
    使用了 Optional = None，意味着前端可以“想改哪个传哪个”。
    比如只改名字，就只传 name，页码不传。
    """
    name: Optional[str] = None
    summary: Optional[str] = None
    page_start: Optional[int] = Field(default=None, ge=1)
    page_end: Optional[int] = Field(default=None, ge=1)

class KPUpdateData(BaseModel):
    kp_id: str
    regenerate_triggered: bool           # 关键字段：告诉前端“这次修改有没有导致大模型重新干活”。如果改了页码就会触发 True。
    status: str                          # 当前状态

class KPUpdateResponse(BaseModel):
    code: int = 200
    msg: str = "success"
    data: KPUpdateData


# ---------------------------------------------------------
# 4. 删除知识点 (DELETE /api/v1/kp/{kp_id})
# 场景：用户想删掉这个知识点
# ---------------------------------------------------------

class KPDeleteData(BaseModel):
    kp_id: str
    deleted: bool                        # 明确告诉前端：True (删得死死的了)

class KPDeleteResponse(BaseModel):
    code: int = 200
    msg: str = "success"
    data: KPDeleteData


# ---------------------------------------------------------
# 5. 重新生成 (POST /api/v1/kp/{kp_id}/regenerate)
# 场景：用户觉得大模型这次生成的解析太烂了，要求强制重写一份
# ---------------------------------------------------------

class KPRegenerateResponse(BaseModel):
    """
    因为重新生成的操作，本质上也是让状态变回 pending_regenerate，
    它返回给前端的数据结构（ID + 状态）和“新增知识点”是一模一样的。
    所以我们在这里偷个懒，直接复用 KPCreateData 这个内部结构。
    """
    code: int = 200
    msg: str = "success"
    data: KPCreateData
