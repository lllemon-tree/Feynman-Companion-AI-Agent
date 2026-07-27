import os
from typing import List, Dict, Any
import chromadb
from chromadb.config import Settings
from chromadb.api.types import EmbeddingFunction, Documents, Embeddings
from sentence_transformers import SentenceTransformer

# ---------------------------------------------------------------------------
# 1. 配置向量数据库在本地物理磁盘的持久化存储目录
# 优先从系统的环境变量中读取 CHROMA_PERSIST_DIR，若无则默认在项目根目录生成 chroma_db 文件夹
# ---------------------------------------------------------------------------
CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")


class BGEEmbeddingFunction(EmbeddingFunction):
    """
    【自定义 Embedding 翻译官】
    Chroma 本身只是个存储和比对向量的数据库，它不知道怎么把“中文”转成“数学向量”。
    所以我们继承 Chroma 的 EmbeddingFunction 接口，把 BGE 模型包装进去，
    给 Chroma 当作它的“文本转向量工具”。
    """
    def __init__(self, model_name: str = "BAAI/bge-large-zh-v1.5"):
        # SentenceTransformer 会自动下载并加载模型（若本地不存在）
        # 第一次运行会从网上拉取约 1.5GB 的模型权重文件
        self.model = SentenceTransformer(model_name, local_files_only=True)

    def __call__(self, input: Documents) -> Embeddings:
        """
        当 Chroma 需要把一段或多段文字转成向量时，会自动触发调用这个 __call__ 方法。
        :param input: 文本列表，例如 ["极限的定义是...", "导数计算法则..."]
        :return: 对应的二维浮点数向量列表
        """
        # normalize_embeddings=True 表示输出标准化的向量，便于后续计算余弦相似度
        embeddings = self.model.encode(input, normalize_embeddings=True).tolist()
        return embeddings


class VectorStoreService:
    """
    【向量数据库核心服务类】
    对外暴露统一的接口，负责管理向量集合（Collection）的创建、切片写入（增）、
    语义检索（查）以及清理（删）。
    """
    def __init__(self):
        # 实例化持久化客户端：指定数据存到本地硬盘的 CHROMA_PERSIST_DIR 目录
        # anonymized_telemetry=False 表示关闭 Chroma 官方的匿名数据收集功能，加快启动速度
        self.client = chromadb.PersistentClient(
            path=CHROMA_PERSIST_DIR,
            settings=Settings(anonymized_telemetry=False)
        )
        # 实例化我们上面写好的 Embedding 模型翻译官
        self.embedding_fn = BGEEmbeddingFunction()

    def _get_collection_name(self, material_id: int | str) -> str:
        """
        【辅助函数：集合命名规范】
        根据教材 ID 生成唯一的 Collection（数据集）名称，例如 "vec_mat_12"。
        实现不同教材在向量空间上的物理隔离，避免串书。
        """
        return f"vec_mat_{material_id}"

    def add_chunks(self, material_id: int | str, chunks: List[Dict[str, Any]]):
        """
        【增：批量写入切片向量】
        :param material_id: 教材 ID
        :param chunks: 待入库的切片字典列表，格式形如：
                       [{"id": 101, "text": "导数定义是...", "page_no": 12}, ...]
        """
        if not chunks:
            return

        collection_name = self._get_collection_name(material_id)
        
        # get_or_create_collection: 如果这个教材的集合已经存在就获取它，不存在就自动新建
        # 必须传入 embedding_function，这样 Chroma 知道往里存文字时用什么模型转向量
        collection = self.client.get_or_create_collection(
            name=collection_name,
            embedding_function=self.embedding_fn,
            metadata={"description": f"Material ID: {material_id}"}
        )

        # 准备 Chroma 所需的三组并行数据数组
        ids = []        # 向量条目的唯一 ID，例如 "chunk-101"
        documents = []  # 原始文本内容，Chroma 会用 embedding_fn 对它转向量
        metadatas = []  # 附带的元数据（比如页码），用于后续打分溯源

        for chunk in chunks:
            chunk_id = str(chunk["id"])
            ids.append(f"chunk-{chunk_id}")
            documents.append(chunk["text"])
            # 按 PRD 要求写入溯源必须的页码和原始 chunk_id
            metadatas.append({
                "chunk_id": chunk_id,
                "page_no": chunk.get("page_no", 0)
            })

        # 执行 upsert 操作（插入或覆盖更新）
        # 这样即使同一个 Chunk 跑了两次，也会自动更新而不会报主键重复错误
        collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas
        )

    def search(self, material_id: int | str, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        【查：RAG 语义检索】
        :param material_id: 搜索范围限定在某本教材内
        :param query: 用户的提问或讲解文本（例如："极限怎么算？"）
        :param top_k: 期望返回最相似的前几条原文切片
        :return: 匹配到的切片信息列表
        """
        collection_name = self._get_collection_name(material_id)
        try:
            # 尝试获取对应教材的向量集合
            collection = self.client.get_collection(
                name=collection_name,
                embedding_function=self.embedding_fn
            )
        except ValueError:
            # 如果这本教材从来没生成过向量集合，直接安全返回空列表
            return []

        # 执行语义查询
        # Chroma 会自动把 query 字符串传给 BGE 模型转成向量，然后在 Collection 里搜索夹角最近的原文
        results = collection.query(
            query_texts=[query],
            n_results=top_k
        )

        formatted_results = []
        # 处理 Chroma 返回的结果结构 (Chroma 返回的格式是二维嵌套列表)
        if results["ids"] and len(results["ids"][0]) > 0:
            for i in range(len(results["ids"][0])):
                formatted_results.append({
                    "chunk_id": results["metadatas"][0][i]["chunk_id"],
                    "page_no": results["metadatas"][0][i]["page_no"],
                    "text": results["documents"][0][i],
                    # score 代表距离/相似度得分
                    "score": results["distances"][0][i] if results["distances"] else 0.0
                })

        return formatted_results

    def delete_material(self, material_id: int | str):
        """
        【删：清理整本教材的向量】
        当用户删除某本教材时调用，把硬盘里的向量集合彻底删除，释放空间
        """
        collection_name = self._get_collection_name(material_id)
        try:
            self.client.delete_collection(name=collection_name)
        except ValueError:
            pass  # 如果本身就不存在，直接跳过


# ---------------------------------------------------------------------------
# 全局单例对象
# 导入时即实例化，避免多次 load BGE 模型导致内存溢出
# ---------------------------------------------------------------------------
vector_store = VectorStoreService()