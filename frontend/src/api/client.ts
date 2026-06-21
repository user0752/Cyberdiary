/**
 * Unified API client — single axios instance with shared config.
 * All API modules should import client from here instead of using raw fetch/axios.
 *
 * NOTE: SSE streaming endpoints (chat, compile) use fetch() directly via
 * useSSEStream / streamMultiAgentCompile, NOT this axios client. This is
 * intentional — axios timeout does not apply to SSE streams, which are
 * managed via AbortController in the calling stores.
 */
import axios, { type AxiosInstance } from 'axios'

const BASE_URL = '/api/v1'

/** Error with HTTP status code preserved for callers to branch on (401/403/500/etc). */
export class ApiError extends Error {
  statusCode: number
  response?: unknown

  constructor(message: string, statusCode: number, response?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.statusCode = statusCode
    this.response = response
  }
}

const client: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  timeout: 120000,
  headers: { 'Content-Type': 'application/json' },
})

// Response interceptor — unwrap ApiResponse<T> envelope
client.interceptors.response.use(
  (res) => {
    if (res.data && typeof res.data.code === 'number') {
      if (res.data.code !== 0) {
        return Promise.reject(new ApiError(res.data.message || 'API error', res.status, res.data))
      }
    }
    return res
  },
  (err) => {
    // Normalize error message from response body when available
    const statusCode = err.response?.status || 0
    const detail = err.response?.data?.message || err.message
    return Promise.reject(new ApiError(detail, statusCode, err.response?.data))
  },
)

export default client
export { BASE_URL }
