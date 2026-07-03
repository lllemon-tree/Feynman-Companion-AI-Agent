import axios from 'axios'
import { MOCK_FOLLOW_UP, MOCK_GENERATE_REPORT, MOCK_GREETING } from './mockData'

/**
 * 是否走 Mock
 * 通过 .env.development 中的 VITE_USE_MOCK 切换
 */
const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true'
const BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1'

const http = axios.create({
  baseURL: BASE_URL,
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' }
})

// 简易拦截器：把后端 200 包壳格式解出来
http.interceptors.response.use(
  (resp) => resp.data,
  (err) => {
    const message =
      err?.response?.data?.msg || err?.message || '网络异常，请稍后重试'
    return Promise.reject(new Error(message))
  }
)

/**
 * 调用 /feynman/chat
 * @param {string} sessionId
 * @param {string} userInput
 * @returns {Promise<{next_action, reply_text, card_preview, final_report}>}
 */
export async function chatWithAgent(sessionId, userInput) {
  if (USE_MOCK) {
    return mockChat(sessionId, userInput)
  }
  const data = await http.post('/feynman/chat', {
    session_id: sessionId,
    user_input: userInput
  })
  return data?.data
}

/**
 * 获取首屏引导语
 * - Mock：直接返回固定问候
 * - 真实后端：可调用一个轻量接口或同样走 /feynman/chat
 */
export async function fetchGreeting() {
  if (USE_MOCK) {
    await delay(400)
    return MOCK_GREETING.data
  }
  // 真实联调时如有专属接口，在这里替换
  const data = await http.get('/feynman/greeting')
  return data?.data
}

// ---------- Mock 控制器 ----------
// 策略：
//   - 第 1 次调用 -> MOCK_FOLLOW_UP
//   - 第 2 次调用 -> MOCK_FOLLOW_UP
//   - 第 3 次调用 -> MOCK_GENERATE_REPORT（强制熔断演示）
// 实际项目里熔断由后端控制，前端不感知"轮次"

const mockCallCount = new Map() // sessionId -> 已追问次数

async function mockChat(sessionId, userInput) {
  await delay(900 + Math.random() * 600)

  const count = mockCallCount.get(sessionId) || 0
  const next = count + 1
  mockCallCount.set(sessionId, next)

  // 最多 3 轮追问，第 3 轮必返回报告
  if (next >= 3) {
    return MOCK_GENERATE_REPORT.data
  }
  return MOCK_FOLLOW_UP.data
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}
