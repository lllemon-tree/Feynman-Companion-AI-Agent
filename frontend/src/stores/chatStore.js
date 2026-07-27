import { defineStore } from 'pinia'
import { v4 as uuidv4 } from 'uuid'
import { chatWithAgent, fetchGreeting, resetFeynmanSession } from '@/api/feynman'

export const useChatStore = defineStore('chat', {
  state: () => ({
    sessionId: '',
    messages: /** @type {{id: string, role: 'user' | 'ai' | 'system', content: string, ts: number}[]} */ ([]),
    isLocked: false,
    isReportReady: false,
    reportData: /** @type {{cardPreview: object, finalReport: object} | null} */ (null),
    errorMsg: '',
    kpId: '',
    kpName: '',
    materialId: '',
    materialTitle: '',
    chapterId: '',
    chapterTitle: '',
    subject: ''
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

    async bootstrap(kpId = null) {
      this.resetLocalState()
      try {
        const effectiveKpId = kpId || this.kpId
        const greeting = await fetchGreeting(effectiveKpId)
        if (greeting.kp_id) {
          this.kpId = greeting.kp_id
          this.kpName = greeting.kp_name || ''
        }
        this.pushMessage('ai', greeting.reply_text)
      } catch (e) {
        this.errorMsg = e.message || '初始化失败'
      }
    },

    async sendUserMessage(text) {
      const content = (text || '').trim()
      if (!content || this.isLocked) return

      this.pushMessage('user', content)
      this.isLocked = true
      this.errorMsg = ''

      try {
        const data = await chatWithAgent(this.sessionId, content, this.kpId)
        this.handleAgentResponse(data)
        return data
      } catch (e) {
        this.pushMessage(
          'system',
          '网络异常：' + (e.message || '请稍后再试')
        )
        this.isLocked = false
        this.errorMsg = e.message || '请求失败'
        return null
      }
    },

    handleAgentResponse(data) {
      if (!data) {
        this.isLocked = false
        return
      }

      const { next_action, reply_text, card_preview, final_report } = data

      if (reply_text) {
        this.pushMessage('ai', reply_text)
      }

      if (next_action === 'generate_report') {
        this.isReportReady = true
        this.reportData = {
          cardPreview: card_preview || null,
          finalReport: final_report || null
        }
      } else if (next_action === 'follow_up' || next_action === 'guide_topic') {
        this.isLocked = false
      } else {
        this.pushMessage('system', `未知动作：${next_action}`)
        this.isLocked = false
      }
    },

    pushMessage(role, content) {
      this.messages.push({
        id: uuidv4(),
        role,
        content,
        ts: Date.now()
      })
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
      this.isReportReady = false
      this.reportData = null
      this.errorMsg = ''
    },

    clearKnowledgeContext() {
      this.kpId = ''
      this.kpName = ''
      this.materialId = ''
      this.materialTitle = ''
      this.chapterId = ''
      this.chapterTitle = ''
      this.subject = ''
    }
  }
})
