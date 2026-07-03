/**
 * Mock 响应数据
 * 直接复用 PRD §四 中给出的标准 JSON（场景 A / 场景 B）
 * 真实联调时 USE_MOCK=false 即可走真实后端
 */

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
        '整体表现优秀！你对 Dijkstra 算法的核心机制掌握扎实，表达清晰有条理。主要提升点在于贪心策略正确性的证明逻辑，建议通过反证法深入理解非负权前提的必要性。继续保持，相信下次会更出色！'
    }
  }
}

/**
 * 引导语（首屏 AI 消息）
 * 等同于一次"后端主动发起的 follow_up"，但不带 sessionId
 */
export const MOCK_GREETING = {
  code: 200,
  msg: 'success',
  data: {
    next_action: 'follow_up',
    reply_text:
      '同学你好！请用大白话向我解释一下，Dijkstra 算法是怎么保证一定能找到最短路径的？',
    card_preview: null,
    final_report: null
  }
}
