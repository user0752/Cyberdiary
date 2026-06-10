/**
 * Unified API client — single axios instance with shared config.
 * All API modules should import client from here instead of using raw fetch/axios.
 */
import axios, { type AxiosInstance } from 'axios'

const BASE_URL = '/api/v1'

const client: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

// Response interceptor — unwrap ApiResponse<T> envelope
client.interceptors.response.use(
  (res) => {
    if (res.data && typeof res.data.code === 'number') {
      if (res.data.code !== 0) {
        return Promise.reject(new Error(res.data.message || 'API error'))
      }
    }
    return res
  },
  (err) => {
    // Normalize error message from response body when available
    const detail = err.response?.data?.message || err.message
    return Promise.reject(new Error(detail))
  },
)

export default client
export { BASE_URL }
