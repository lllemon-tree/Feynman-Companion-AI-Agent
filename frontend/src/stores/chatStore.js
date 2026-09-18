import { acceptHMRUpdate, defineStore } from 'pinia'
import { v4 as uuidv4 } from 'uuid'
import { streamChatWithAgent, fetchGreeting, resetFeynmanSession, getReviewResult, getSessionDetail } from '@/api/feynman'
import { appendReactiveMessage } from '@/utils/reactiveMessage'

export const useChatStore = defineStore('chat', {
  state: () => ({
    sessionId: '',
    messages: /** @type {{id: string, role: 'user' | 'ai' | 'system', content: string, ts: number}[]} */ ([]),
    isLocked: false,
    streamStatus: '',
    isReportReady: false,
    reportData: /** @type {{cardPreview: object, finalReport: object, reviewPlan: object | null, provider: string | null, fallbackUsed: boolean, reportId: string, reviewListAdded: boolean, reviewListSource: string | null} | null} */ (null),
    errorMsg: '',
    kpId: '',
    kpName: '',
    materialId: '',
    materialTitle: '',
    chapterId: '',
    chapterTitle: '',
    subject: '',
    // ===== 第八周 复习场景状态 =====
    isReviewMode: false,
    reviewId: '',
    // 复习专用 session_id（来自 /reviews/start，后端据此加载复习上下文）
    reviewSessionId: '',
    baselineReportId: '',
    targetGaps: /** @type {{gap_id: string, dimension: string, score: number, gap_description: string, review_count: number}[]} */ ([]),
    // 复习重点维度（用于对话页提示，不暴露标准答案）
    reviewFocusDimensions: /** @type {string[]} */ ([]),
    // 复习结果（report 生成后通过 GET /reviews/{review_id} 拉取）
    reviewResult: /** @type {object | null} */ (null)
  }),

  getters: {
    hasMessages: (state) => state.messages.length > 0,
    isFinished: (state) => state.isReportReady,
    breadcrumb: (state) => [
      { name: state.subject || '科目', id: 'subject' },
      { name: state.materialTitle || '教材', id: 'material' },
      { name: state.chapterTitle || '章节', id: 'chapter' },
      { name: state.kpName || '知识点', id: 'kp' }
    ].filter(item => item.name && item.name !== '科目' && item.name !== '教材' && item.name !== '章节' && item.name !== '知识点')
  },

  actions: {
    async restoreSession(sessionId) {
      const detail = await getSessionDetail(sessionId)
      this.sessionId = detail.session_id
      this.kpId = detail.kp_id || ''
      this.kpName = detail.kp_name || ''
      this.materialId = detail.material_id || ''
      this.chapterId = detail.chapter_id || ''
      this.messages = (detail.chat_history || []).map(item => ({
        id: uuidv4(),
        role: item.role === 'assistant' ? 'ai' : item.role,
        content: item.content,
        ts: Date.now()
      }))
      this.isReportReady = Boolean(detail.report_data?.final_report)
      this.reportData = this.isReportReady
        ? {
            cardPreview: detail.report_data.card_preview || null,
            finalReport: detail.report_data.final_report,
            reviewPlan: detail.report_data.review_plan || null,
            provider: detail.report_data.provider || null,
            fallbackUsed: Boolean(detail.report_data.fallback_used),
            reportId: detail.report_data.report_id || '',
            reviewListAdded: Boolean(detail.report_data.review_list_added),
            reviewListSource: detail.report_data.review_list_source || null
          }
        : null
      this.isLocked = this.isReportReady
      this.streamStatus = ''
      this.errorMsg = ''
      if (!this.messages.length && this.kpId) {
        const greeting = await fetchGreeting(this.kpId, sessionId)
        this.pushMessage('ai', greeting.reply_text)
      }
      return detail
    },
    setKnowledgePoint(kpId, kpName) {
      this.kpId = kpId
      this.kpName = kpName
    },

    setMaterial(materialId, materialTitle) {
      this.materialId = materialId
      this.materialTitle = materialTitle
    },

    setChapter(chapterId, chapterTitle) {
      this.chapterId = chapterId
      this.chapterTitle = chapterTitle
    },

    setSubject(subject) {
      this.subject = subject
    },

    /**
     * 进入复习场景：设置复习上下文
     * 由 ProfilePage 在调用 startReview 成功后调用
     */
    startReviewContext(payload) {
      this.isReviewMode = true
      this.reviewId = payload.review_id || ''
      this.reviewSessionId = payload.session_id || ''
      this.baselineReportId = payload.baseline_report_id || ''
      this.targetGaps = payload.target_gaps || []
      this.reviewFocusDimensions = (payload.target_gaps || []).map(g => g.dimension)
      this.reviewResult = null
    },

    /**
     * 初始化会话引导语
     * 第八周：复习模式下使用 reviewSessionId，后端返回含重点维度的复习引导语
     * 普通学习保持现有流程
     */
    async bootstrap(kpId = null) {
      const savedKpId = kpId || this.kpId
      const savedKpName = this.kpName
      this.resetLocalState()
      this.kpId = savedKpId || ''
      this.kpName = savedKpName || ''
      // 复习模式：使用 /reviews/start 返回的 session_id（PRD 6.2）
      // 后端根据 session_id 查询 active review_attempt，加载目标漏洞和基线报告
      if (this.isReviewMode && this.reviewSessionId) {
        this.sessionId = this.reviewSessionId
      }
      if (!this.kpId) {
        this.pushMessage('system', '未指定知识点，请先选择知识点。')
        return
      }
      try {
        // 复习模式传入 session_id，后端据此返回复习引导语
        const greeting = await fetchGreeting(
          this.kpId,
          this.isReviewMode ? this.reviewSessionId : null
        )
        if (greeting.kp_id) {
          this.kpId = greeting.kp_id
          this.kpName = greeting.kp_name || ''
        }
        // 复习引导语可能携带重点维度提示
        if (this.isReviewMode && greeting.is_review) {
          this.reviewFocusDimensions = greeting.review_focus_dimensions || this.reviewFocusDimensions
        }
        this.pushMessage('ai', greeting.reply_text)
      } catch (e) {
        this.errorMsg = e.message || '初始化失败'
      }
    },

    async sendUserMessage(text) {
      const content = (text || '').trim()
      if (!content || this.isLocked) return

      const previousUserCount = this.messages.filter(item => item.role === 'user').length
      const userMessage = this.pushMessage('user', content)
      const pending = this.pushMessage('ai', '')
      this.isLocked = true
      this.streamStatus = '正在连接讲解服务…'
      this.errorMsg = ''

      try {
        const data = await streamChatWithAgent(this.sessionId, content, this.kpId, (delta) => {
          pending.content += delta
          if (this.streamStatus !== '正在保存本轮讲解与诊断…') {
            this.streamStatus = '正在输出回复…'
          }
        }, (_stage, text) => {
          this.streamStatus = text
        })
        await this.handleAgentResponse(data, pending.id)
        window.dispatchEvent(new Event('feynman:sessions-updated'))
        return data
      } catch (e) {
        // 若服务端已保存而终止事件在网络中丢失，先恢复历史，避免重试产生重复讲解。
        try {
          const detail = await getSessionDetail(this.sessionId)
          const history = detail?.chat_history || []
          const savedUserCount = history.filter(item => item.role === 'user').length
          if (savedUserCount > previousUserCount && history.at(-2)?.content === content) {
            await this.restoreSession(this.sessionId)
            return { recovered: true }
          }
        } catch (_) { /* 保留原始流错误，输入内容仍留在输入框。 */ }
        this.messages = this.messages.filter(item => item.id !== userMessage.id && item.id !== pending.id)
        this.isLocked = false
        this.errorMsg = `${e.message || '请求失败'}。输入内容已保留，可重试。`
        return null
      } finally {
        this.streamStatus = ''
      }
    },

    async finishAndEvaluate() {
      if (this.isLocked || this.isReportReady) return null
      if (!this.messages.some(item => item.role === 'user' && item.content.trim())) {
        this.errorMsg = '请先讲出你对该知识点的理解，再生成评估。'
        return null
      }
      const pending = this.pushMessage('ai', '')
      this.isLocked = true
      this.streamStatus = '正在整理你的累计讲解…'
      this.errorMsg = ''
      try {
        const data = await streamChatWithAgent(
          this.sessionId,
          '',
          this.kpId,
          (delta) => { pending.content += delta },
          (_stage, text) => { this.streamStatus = text },
          true
        )
        await this.handleAgentResponse(data, pending.id)
        return data
      } catch (error) {
        this.messages = this.messages.filter(item => item.id !== pending.id)
        this.isLocked = false
        this.errorMsg = error.message || '生成评估失败，请重试。'
        return null
      } finally {
        this.streamStatus = ''
      }
    },

    /**
     * 处理 Agent 响应
     * 第八周：报告生成后，若处于复习模式，自动拉取复习结果对比
     */
    async handleAgentResponse(data, pendingId = '') {
      if (!data) {
        this.isLocked = false
        return
      }

      const {
        next_action, reply_text, card_preview, final_report, review_plan,
        provider, fallback_used, report_id, review_list_added, review_list_source
      } = data

      const pending = this.messages.find(item => item.id === pendingId)
      if (reply_text && pending) {
        pending.content = reply_text
      } else if (reply_text) {
        this.pushMessage('ai', reply_text)
      } else if (pending) {
        this.messages = this.messages.filter(item => item.id !== pendingId)
      }

      if (next_action === 'generate_report') {
        this.isReportReady = true
        this.reportData = {
          cardPreview: card_preview || null,
          finalReport: final_report || null,
          reviewPlan: review_plan || null,
          provider: provider || null,
          fallbackUsed: Boolean(fallback_used),
          reportId: report_id || '',
          reviewListAdded: Boolean(review_list_added),
          reviewListSource: review_list_source || null
        }
        // 复习模式：后端生成报告并完成事务后，前端拉取复习结果对比
        if (this.isReviewMode && this.reviewId) {
          try {
            this.reviewResult = await getReviewResult(this.reviewId)
          } catch (e) {
            // 复习结果拉取失败不阻断报告展示
            this.errorMsg = e.message || '复习结果获取失败'
          }
        }
      } else if (next_action === 'follow_up' || next_action === 'guide_topic') {
        this.isLocked = false
      } else {
        this.pushMessage('system', `未知动作：${next_action}`)
        this.isLocked = false
      }
    },

    pushMessage(role, content) {
      const message = {
        id: uuidv4(),
        role,
        content,
        ts: Date.now()
      }
      // 返回 Pinia 响应式数组中的代理对象。返回局部原始对象会导致
      // pending.content += delta 虽然执行了，Vue 却直到 done 才刷新气泡。
      return appendReactiveMessage(this.messages, message)
    },

    setError(msg) {
      this.errorMsg = msg
    },

    async resetSession() {
      const oldSessionId = this.sessionId
      if (oldSessionId) {
        try {
          await resetFeynmanSession(oldSessionId)
        } catch (e) {
          this.errorMsg = e.message || '重置会话失败'
        }
      }
      this.resetLocalState()
    },

    resetLocalState() {
      this.sessionId = uuidv4()
      this.messages = []
      this.isLocked = false
      this.streamStatus = ''
      this.isReportReady = false
      this.reportData = null
      this.errorMsg = ''
      this.reviewResult = null
    },

    clearKnowledgeContext() {
      this.kpId = ''
      this.kpName = ''
      this.materialId = ''
      this.materialTitle = ''
      this.chapterId = ''
      this.chapterTitle = ''
      this.subject = ''
    },

    /**
     * 退出复习场景：清空复习相关状态，回到普通学习模式
     */
    clearReviewContext() {
      this.isReviewMode = false
      this.reviewId = ''
      this.reviewSessionId = ''
      this.baselineReportId = ''
      this.targetGaps = []
      this.reviewFocusDimensions = []
      this.reviewResult = null
    }
  }
})

if (import.meta.hot) {
  import.meta.hot.accept(acceptHMRUpdate(useChatStore, import.meta.hot))
}
