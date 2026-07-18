import fitz  # PyMuPDF

def generate_full_textbook(output_path="full_data_structures_textbook.pdf"):
    # 教材结构数据字典
    textbook_data = [
        {
            "title": "第1章：数据结构与算法绪论",
            "kps": [
                ("1.1 数据结构基本概念", "数据结构是相互之间存在一种或多种特定关系的数据元素的集合，包括逻辑结构与物理结构。"),
                ("1.2 复杂度分析原理", "大O表示法用于评估算法随着输入规模增长时，时间与空间资源的消耗趋势与渐进上界。")
            ]
        },
        {
            "title": "第2章：线性表",
            "kps": [
                ("2.1 顺序表的内存分布", "顺序表利用一段物理地址连续的存储单元依次存储数据，支持 O(1) 的随机访问，但插入删除较慢。"),
                ("2.2 链表的指针机制", "链表通过节点中的指针链接非连续的内存空间，实现了 O(1) 的插入与删除，但丧失了随机访问能力。")
            ]
        },
        {
            "title": "第3章：栈与队列",
            "kps": [
                ("3.1 栈的后进先出 (LIFO)", "栈是一种只允许在表尾进行插入或删除操作的线性表，常用于函数调用、表达式求值与递归算法。"),
                ("3.2 队列的先进先出 (FIFO)", "队列允许在表的一端进行插入，在另一端进行删除，广泛应用于广度优先搜索与操作系统任务调度。")
            ]
        },
        {
            "title": "第4章：串与数组",
            "kps": [
                ("4.1 字符串匹配 (KMP算法)", "KMP算法通过构建 next 数组，在字符串匹配失败时避免主串指针回溯，将时间复杂度优化至 O(n+m)。"),
                ("4.2 多维数组与矩阵压缩", "特殊矩阵（如对称矩阵、稀疏矩阵）可以通过特定的一维数组映射公式进行压缩存储，节约内存。")
            ]
        },
        {
            "title": "第5章：树与二叉树",
            "kps": [
                ("5.1 二叉树的性质与遍历", "二叉树的每个节点最多有两个子树。深度优先遍历包括前序、中序和后序，广度优先使用层序遍历。"),
                ("5.2 哈夫曼树与数据编码", "哈夫曼树是带权路径长度最短的二叉树，其产生的哈夫曼编码是一种前缀编码，常用于数据无损压缩。")
            ]
        },
        {
            "title": "第6章：图论基础",
            "kps": [
                ("6.1 图的存储结构", "图的存储主要分为邻接矩阵（适合稠密图）和邻接表（适合稀疏图），用于表示顶点关系与边权重。"),
                ("6.2 DFS 与 BFS 遍历", "深度优先搜索(DFS)基于栈实现回溯，广度优先搜索(BFS)基于队列实现层级推进，两者是图算法的基础。")
            ]
        },
        {
            "title": "第7章：最短路径与最小生成树",
            "kps": [
                ("7.1 Dijkstra 最短路径算法", "Dijkstra算法基于贪心策略，通过不断松弛边，求解非负权图中单源最短路径问题。"),
                ("7.2 Kruskal 最小生成树算法", "Kruskal算法通过并查集检测环路，按权值从小到大选取边，以最小代价连通图中所有顶点。")
            ]
        },
        {
            "title": "第8章：查找算法",
            "kps": [
                ("8.1 二分查找的核心逻辑", "二分查找要求线性表必须采用顺序存储且按关键字有序，每次比较使搜索范围减半，复杂度 O(log n)。"),
                ("8.2 哈希表与冲突解决", "哈希表通过散列函数映射地址，解决冲突的常用方法包括开放定址法与链地址法。")
            ]
        },
        {
            "title": "第9章：排序算法",
            "kps": [
                ("9.1 基础排序 (冒泡与插入)", "基础排序算法逻辑简单但效率较低，平均时间复杂度通常为 O(n^2)，适合小规模或基本有序的数据。"),
                ("9.2 高级排序 (快排与归并)", "快速排序基于分治法与基准元划分；归并排序基于合并有序子序列。两者在处理大规模数据时极具优势。")
            ]
        },
        {
            "title": "第10章：高级数据结构",
            "kps": [
                ("10.1 B树与B+树", "B树是多路平衡查找树；B+树将所有数据存储在叶子节点并形成链表，是数据库索引的底层核心结构。"),
                ("10.2 红黑树自平衡原理", "红黑树通过颜色约束和旋转操作（左旋/右旋）保持近似平衡，保障最坏情况下的查询、插入、删除性能。")
            ]
        }
    ]

    doc = fitz.open()
    
    # 封面设计：添加 fontname="china-ss" 强制使用中文字体
    p_cover = doc.new_page()
    p_cover.insert_text((100, 300), "《数据结构与算法核心教程》", fontsize=24, fontname="china-ss")
    p_cover.insert_text((220, 350), "产品级演示专用版", fontsize=16, fontname="china-ss")
    p_cover.insert_text((180, 700), "包含 10 章核心理论与 20 个基础知识点", fontsize=12, fontname="china-ss")

    toc = []
    current_page = 2  # 封面为第1页，正文从第2页开始

    # 遍历生成每章内容
    for chapter in textbook_data:
        page = doc.new_page()
        
        # 插入章节标题
        page.insert_text((50, 60), chapter["title"], fontsize=18, fontname="china-ss")
        
        # 将该章加入目录元数据 [层级, 标题, 物理页码]
        toc.append([1, chapter["title"], current_page])
        
        # 插入知识点小节
        y_offset = 120
        for kp_title, kp_content in chapter["kps"]:
            # 小节标题
            page.insert_text((50, y_offset), kp_title, fontsize=14, fontname="china-ss")
            # 小节正文 (利用粗略的手动断行避免文字超出 PDF 边界)
            if len(kp_content) > 35:
                line1 = kp_content[:35]
                line2 = kp_content[35:]
                page.insert_text((50, y_offset + 25), line1, fontsize=12, fontname="china-ss")
                page.insert_text((50, y_offset + 45), line2, fontsize=12, fontname="china-ss")
            else:
                page.insert_text((50, y_offset + 25), kp_content, fontsize=12, fontname="china-ss")
            
            y_offset += 100 # 拉开两个知识点之间的间距
            
        current_page += 1

    # 写入目录信息并保存
    doc.set_toc(toc)
    doc.save(output_path)
    print(f"✅ 10章完整版教材 PDF 已生成: {output_path}")

if __name__ == "__main__":
    generate_full_textbook()