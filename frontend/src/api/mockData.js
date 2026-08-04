export const MOCK_FOLLOW_UP = {
  code: 200,
  msg: 'success',
  data: {
    next_action: 'follow_up',
    reply_text:
      '确实如此！那除了边权不能为负数，你能不能解释一下，为什么没访问过的节点里，当前距离最小的那个点，它的最短路径就确定了呢？',
    card_preview: null,
    final_report: null
  }
}

export const MOCK_GENERATE_REPORT = {
  code: 200,
  msg: 'success',
  data: {
    next_action: 'generate_report',
    reply_text:
      '今天的对练结束，这是你的诊断报告：',
    card_preview: {
      total_score: 34,
      summary: '对核心机制掌握扎实，表达清晰有条理'
    },
    final_report: {
      dimensions: [
        {
          name: '理解深度',
          score: 9,
          analysis: '对贪心策略的核心机制理解到位，但在证明其正确性时缺乏系统性推导',
          suggestion: '建议通过反证法理解：假设存在更短路径会与非负权前提矛盾'
        },
        {
          name: '表达完整性',
          score: 8,
          analysis: '覆盖了核心流程，但遗漏了非负权前提的重要性说明',
          suggestion: '讲解时明确指出适用范围，强调负权边会破坏算法正确性'
        },
        {
          name: '逻辑连贯性',
          score: 8,
          analysis: '步骤描述清晰，但各步骤间的逻辑衔接不够自然',
          suggestion: '尝试用"因为...所以..."的句式串联每个操作步骤'
        },
        {
          name: '结构化能力',
          score: 9,
          analysis: '讲解层次分明，能够分点阐述核心概念',
          suggestion: '可以进一步使用对比方式突出算法特点与局限'
        }
      ],
      overall_comment:
        '整体表现优秀！你对 Dijkstra 算法的核心机制掌握扎实，表达清晰有条理。主要提升点在于贪心策略正确性的证明逻辑，建议通过反证法深入理解非负权前提的必要性。继续保持，相信下次会更出色！',
      review_plan: {
        reread_guide: [
          {
            priority: 1,
            material_name: '数据结构教材',
            page_hint: '第 3 章 第 30-33 页',
            focus: '贪心策略的正确性证明——反证法推导过程',
            reason: '理解深度得分偏低（9/10），建议进一步巩固非负权前提的必要性'
          }
        ],
        related_kps: [
          { kp_id: 'kp-mst', kp_name: '最小生成树', relation: '同属图论核心算法，对比理解贪心策略在不同问题中的应用' }
        ],
        priority_order: [
          { rank: 1, dimension: '理解深度', kp_name: 'Dijkstra 算法', suggestion: '通过反证法深入理解贪心选择性质' }
        ]
      }
  }
}

export const MOCK_GREETING = {
  code: 200,
  msg: 'success',
  data: {
    next_action: 'follow_up',
    reply_text:
      '同学你好！请用大白话向我解释一下，Dijkstra 算法是怎么保证一定能找到最短路径的？',
    card_preview: null,
    final_report: null,
    kp_id: 'kp-demo',
    kp_name: 'Dijkstra 算法'
  }
}

export const MOCK_MATERIAL_STATUS_DONE = {
  code: 200,
  msg: 'success',
  data: {
    material_id: 'mat-demo',
    status: 'done',
    step: '完成',
    progress: 1,
    error: null
  }
}

export const MOCK_MATERIAL_STATUS_GENERATING = {
  code: 200,
  msg: 'success',
  data: {
    material_id: 'mat-generating',
    status: 'generating',
    step: 'rubric 生成中',
    progress: 0.6,
    error: null
  }
}

export const MOCK_MATERIAL_STATUS_FAILED = {
  code: 200,
  msg: 'success',
  data: {
    material_id: 'mat-failed',
    status: 'failed',
    step: '解析失败',
    progress: 0,
    error: '教材目录无法识别，请换有目录的 PDF'
  }
}

export const MOCK_KNOWLEDGE_TREE = {
  code: 200,
  msg: 'success',
  data: [
    {
      material_id: 'mat-demo',
      title: '数据结构教材',
      user_id: 'user-demo',
      chapters: [
        {
          chapter_id: 'ch-demo',
          title: '第6章 图论',
          knowledge_points: [
            {
              kp_id: 'kp-demo',
              name: 'Dijkstra 算法',
              summary: '非负权图求单源最短路径的贪心算法',
              page_start: 30,
              page_end: 33,
              status: 'done'
            },
            {
              kp_id: 'kp-mst',
              name: '最小生成树',
              summary: '连通图总权值最小的生成子图',
              page_start: 34,
              page_end: 38,
              status: 'done'
            },
            {
              kp_id: 'kp-topo',
              name: '拓扑排序',
              summary: '有向无环图节点线性排序方式',
              page_start: 39,
              page_end: 42,
              status: 'done'
            }
          ]
        },
        {
          chapter_id: 'ch-tree',
          title: '第5章 树结构',
          knowledge_points: []
        }
      ]
    },
    {
      material_id: 'mat-os',
      title: '操作系统教材',
      chapters: []
    }
  ]
}

export const MOCK_KP_DETAIL = {
  code: 200,
  msg: 'success',
  data: {
    kp_id: 'kp-demo',
    name: 'Dijkstra 算法',
    summary: '非负权图求单源最短路径的贪心算法',
    rubric: {
      concept_prerequisite: {
        name: '概念前提',
        content: 'Dijkstra算法适用于边权非负的带权图。负权边会破坏已访问节点最短路径已确定这一核心结论。'
      },
      core_mechanism: {
        name: '核心机制',
        content: '基于贪心：每次从未访问节点中选距离起点最近的，标记为已访问，并用它松弛相邻节点。'
      },
      principle_proof: {
        name: '原理证明',
        content: '正确性依赖非负权前提：当前距离最小的未访问节点之后不可能再通过其他未访问节点得到更短路径。'
      },
      common_misunderstandings: {
        name: '常见误区',
        content: [
          '认为Dijkstra可以处理负权图',
          '只记步骤无法解释贪心策略正确性',
          '混淆松弛操作的作用',
          '误以为每次选的是边权最小的边'
        ]
      }
    },
    page_start: 30,
    page_end: 33,
    status: 'done',
    source_chunks: [
      { chunk_id: 'chunk-1', page: 30, text: 'Dijkstra算法用于求解...' },
      { chunk_id: 'chunk-2', page: 31, text: '贪心策略：每次选择...' },
      { chunk_id: 'chunk-3', page: 32, text: '松弛操作：用当前节点更新相邻节点距离...' },
      { chunk_id: 'chunk-4', page: 33, text: '正确性依赖边权非负...' }
    ]
  }
}

export const MOCK_GREETING_MAP = {
  'kp-demo': {
    reply_text: '请你向我讲解一下 Dijkstra 算法的核心原理，讲得越详细越好。',
    kp_id: 'kp-demo',
    kp_name: 'Dijkstra 算法'
  },
  'kp-mst': {
    reply_text: '请你向我讲解一下最小生成树的概念与常见算法。',
    kp_id: 'kp-mst',
    kp_name: '最小生成树'
  },
  'kp-topo': {
    reply_text: '请你向我讲解一下拓扑排序的原理和适用场景。',
    kp_id: 'kp-topo',
    kp_name: '拓扑排序'
  }
}

export const MOCK_GREETING_DYNAMIC = {
  code: 200,
  msg: 'success',
  data: MOCK_GREETING_MAP['kp-demo']
}

export const MOCK_KP_CREATE = {
  code: 200,
  msg: 'success',
  data: {
    kp_id: 'kp-mock-new',
    status: 'pending_regenerate'
  }
}

export const MOCK_KP_UPDATE = {
  code: 200,
  msg: 'success',
  data: {
    kp_id: 'kp-demo',
    regenerate_triggered: true,
    status: 'pending_regenerate'
  }
}

export const MOCK_KP_DELETE = {
  code: 200,
  msg: 'success',
  data: {
    kp_id: 'kp-demo',
    deleted: true
  }
}

export const MOCK_KP_REGENERATE = {
  code: 200,
  msg: 'success',
  data: {
    kp_id: 'kp-demo',
    status: 'pending_regenerate'
  }
}

// Auth模块Mock数据
export const MOCK_AUTH_LOGIN = {
  code: 200,
  msg: '登录成功',
  data: {
    token: 'mock-token-demo-123',
    user_id: 'user-demo',
    username: 'teststudent'
  }
}

export const MOCK_AUTH_REGISTER = {
  code: 200,
  msg: '注册成功，请登录',
  data: {
    user_id: 'user-001'
  }
}

export const MOCK_AUTH_CURRENT = {
  code: 200,
  msg: 'success',
  data: {
    user_id: 'user-demo',
    username: 'teststudent'
  }
}

// RAG向量检索Mock数据
export const MOCK_RAG_RETRIEVE = {
  code: 200,
  msg: 'success',
  data: [
    {
      chunk_id: 'chunk-1',
      page_no: 30,
      text: 'Dijkstra算法用于求解非负权带权图单源最短路径，核心为贪心策略。',
      score: 0.97
    },
    {
      chunk_id: 'chunk-8',
      page_no: 36,
      text: '贪心算法全局最优成立条件：不存在后续更短路径，依赖边权非负约束。',
      score: 0.91
    },
    {
      chunk_id: 'chunk-15',
      page_no: 72,
      text: '松弛操作会更新相邻节点最短距离，是Dijkstra核心执行步骤。',
      score: 0.85
    }
  ]
}

// 历史会话Mock数据（P1）
export const MOCK_SESSIONS = {
  code: 200,
  msg: 'success',
  data: [
    {
      session_id: 'ses-demo',
      kp_name: 'Dijkstra 算法',
      material_title: '数据结构教材',
      created_at: '2026-07-20T10:30:00'
    }
  ]
}

// 学情画像Mock数据
export const MOCK_USER_PROFILE = {
  code: 200,
  msg: 'success',
  data: {
    user_id: 'user-demo',
    nickname: '考研小王',
    exam_subject: '计算机',
    exam_sub_category: '408统考',
    preparation_stage: '基础',
    exam_type: '应届',
    pain_points: ['概念理解困难', '输出薄弱'],
    target_school: '',
    target_major: ''
  }
}

export const MOCK_USER_PROFILE_EMPTY = {
  code: 200,
  msg: 'success',
  data: {
    user_id: 'user-demo',
    nickname: null,
    exam_subject: null,
    exam_sub_category: null,
    preparation_stage: null,
    exam_type: null,
    pain_points: [],
    target_school: null,
    target_major: null
  }
}

export const MOCK_USER_PROFILE_SAVE = {
  code: 200,
  msg: '学情信息已保存',
  data: {
    user_id: 'user-demo',
    exam_subject: '计算机'
  }
}

// 知识漏洞库Mock数据
export const MOCK_GAPS = {
  code: 200,
  msg: 'success',
  data: {
    items: [
      {
        gap_id: 'gap-demo-1',
        kp_id: 'kp-demo',
        kp_name: 'Dijkstra 算法',
        dimension: '理解深度',
        score: 4,
        severity: 4,
        status: 'open',
        gap_description: '能描述算法步骤，但无法解释贪心策略的正确性依赖非负权边的前提条件',
        created_at: '2026-07-28T10:30:00'
      },
      {
        gap_id: 'gap-demo-2',
        kp_id: 'kp-demo',
        kp_name: 'Dijkstra 算法',
        dimension: '逻辑连贯性',
        score: 3,
        severity: 5,
        status: 'open',
        gap_description: '无法证明贪心选择性质，混淆算法正确性和反证法的逻辑',
        created_at: '2026-07-28T10:30:00'
      },
      {
        gap_id: 'gap-demo-3',
        kp_id: 'kp-mst',
        kp_name: '最小生成树',
        dimension: '结构化能力',
        score: 5,
        severity: 4,
        status: 'reviewing',
        gap_description: 'Kruskal和Prim算法的使用场景区分不清晰',
        created_at: '2026-07-27T14:20:00'
      },
      {
        gap_id: 'gap-demo-4',
        kp_id: 'kp-topo',
        kp_name: '拓扑排序',
        dimension: '表达完整性',
        score: 6,
        severity: 3,
        status: 'resolved',
        gap_description: '对拓扑排序的应用场景（如任务调度）描述不够完整',
        created_at: '2026-07-25T09:15:00'
      }
    ],
    total: 4,
    page: 1,
    page_size: 20
  }
}

export const MOCK_GAPS_STATS = {
  code: 200,
  msg: 'success',
  data: {
    total: 4,
    by_status: {
      open: 2,
      reviewing: 1,
      resolved: 1
    },
    by_dimension: {
      '理解深度': 1,
      '表达完整性': 1,
      '逻辑连贯性': 1,
      '结构化能力': 1
    }
  }
}

export const MOCK_GAP_UPDATE = {
  code: 200,
  msg: 'success',
  data: {
    gap_id: 'gap-demo-1',
    status: 'resolved'
  }
}

// 历史报告Mock数据
export const MOCK_REPORTS = {
  code: 200,
  msg: 'success',
  data: {
    items: [
      {
        report_id: 'rpt-demo-1',
        kp_id: 'kp-demo',
        kp_name: 'Dijkstra 算法',
        material_name: '数据结构教材',
        total_score: 24,
        dimensions: [
          { name: '理解深度', score: 4 },
          { name: '表达完整性', score: 6 },
          { name: '逻辑连贯性', score: 7 },
          { name: '结构化能力', score: 7 }
        ],
        gaps_identified: 2,
        created_at: '2026-07-28T10:30:00'
      },
      {
        report_id: 'rpt-demo-2',
        kp_id: 'kp-demo2',
        kp_name: 'Floyd 算法',
        material_name: '数据结构教材',
        total_score: 32,
        dimensions: [
          { name: '理解深度', score: 8 },
          { name: '表达完整性', score: 8 },
          { name: '逻辑连贯性', score: 8 },
          { name: '结构化能力', score: 8 }
        ],
        gaps_identified: 0,
        created_at: '2026-07-27T14:20:00'
      }
    ],
    total: 2,
    page: 1,
    page_size: 20
  }
}

export const MOCK_REPORT_DETAIL = {
  code: 200,
  msg: 'success',
  data: {
    report_id: 'rpt-demo-1',
    kp_id: 'kp-demo',
    kp_name: 'Dijkstra 算法',
    material_name: '数据结构教材',
    session_id: 'sess-001',
    dimensions_full: [
      {
        name: '理解深度',
        score: 4,
        analysis: '能描述Dijkstra算法的步骤，但无法解释其正确性依据和复杂度分析的数学原理',
        suggestion: '建议从贪心策略的定义出发，结合反证法理解算法的正确性'
      },
      {
        name: '表达完整性',
        score: 6,
        analysis: '基本覆盖了算法流程，但遗漏了非负权前提条件和算法适用范围的说明',
        suggestion: '讲解时注意明确算法的前提条件，说明适用场景和局限性'
      },
      {
        name: '逻辑连贯性',
        score: 7,
        analysis: '步骤描述基本通顺，但各步骤间的因果关系阐述不够紧密',
        suggestion: '尝试使用"因为...所以..."的句式将步骤串联起来'
      },
      {
        name: '结构化能力',
        score: 7,
        analysis: '整体结构清晰，能够分点阐述，但优化部分的阐述略显分散',
        suggestion: '可以使用表格或对比方式展示不同实现的时间复杂度'
      }
    ],
    total_score: 24,
    overall_comment: '本次讲解体现了对Dijkstra算法的基础了解，但在原理深度和表达完整性方面还有提升空间。建议重点攻克贪心策略的正确性证明，并在讲解时更加注重前提条件和适用范围的说明。',
    review_plan: {
      reread_guide: [
        {
          priority: 1,
          material_name: '数据结构教材',
          page_hint: '第 3 章 第 30-33 页',
          focus: '贪心策略的正确性证明——反证法推导过程',
          reason: '理解深度得分偏低（4/10），未能解释为何非负权边是前提条件'
        }
      ],
      related_kps: [
        { kp_id: 'kp-mst', kp_name: '最小生成树', relation: '同属图论核心算法，对比理解贪心策略在不同问题中的应用' },
        { kp_id: 'kp-topo', kp_name: '拓扑排序', relation: '有向无环图相关，对比DAG与一般图的区别' }
      ],
      priority_order: [
        { rank: 1, dimension: '理解深度', kp_name: 'Dijkstra 算法', suggestion: '优先复习贪心策略正确性证明' },
        { rank: 2, dimension: '表达完整性', kp_name: 'Dijkstra 算法', suggestion: '补充非负权前提条件的说明' }
      ]
    },
    gaps_identified: 2,
    created_at: '2026-07-28T10:30:00'
  }
}

// 今日待复习漏洞Mock数据
export const MOCK_REVIEW_DUE_GAPS = {
  code: 200,
  msg: 'success',
  data: {
    items: [
      {
        gap_id: 'gap-review-1',
        kp_id: 'kp-demo',
        kp_name: 'Dijkstra 算法',
        dimension: '理解深度',
        score: 4,
        severity: 4,
        status: 'open',
        gap_description: '能描述算法步骤，但无法解释贪心策略的正确性依赖非负权边的前提条件',
        created_at: '2026-07-28T10:30:00'
      },
      {
        gap_id: 'gap-review-2',
        kp_id: 'kp-mst',
        kp_name: '最小生成树',
        dimension: '结构化能力',
        score: 5,
        severity: 4,
        status: 'reviewing',
        gap_description: 'Kruskal和Prim算法的使用场景区分不清晰',
        created_at: '2026-07-27T14:20:00'
      }
    ],
    total: 2,
    page: 1,
    page_size: 20
  }
}

// 学情统计Mock数据
export const MOCK_USER_STATS = {
  code: 200,
  msg: 'success',
  data: {
    total_kps_learned: 12,
    total_sessions: 18,
    avg_total_score: 28.5,
    dimension_avg: {
      '理解深度': 6.8,
      '表达完整性': 7.2,
      '逻辑连贯性': 7.5,
      '结构化能力': 7.0
    },
    weakest_dimension: '理解深度',
    recent_trend: [
      { date: '2026-08-02', total_score: 26 },
      { date: '2026-08-03', total_score: 30 },
      { date: '2026-08-04', total_score: 32 }
    ]
  }
}