/**
 * Auth API — register, login, current user.
 */
import client from './client'
import { ApiError } from './client'

export interface TokenResponse {
  access_token: string
  token_type: string
  username: string
}

export interface UserResponse {
  id: string
  username: string
  is_active: boolean
}

export async function register(username: string, password: string): Promise<TokenResponse> {
  const res = await client.post('/auth/register', { username, password })
  return res.data.data
}

export async function login(username: string, password: string): Promise<TokenResponse> {
  const res = await client.post('/auth/login', { username, password })
  return res.data.data
}

export async function logout(): Promise<void> {
  // Best-effort server-side revocation. Local token is cleared regardless
  // of the response — the client considers itself logged out either way.
  try {
    await client.post('/auth/logout')
  } catch {
    /* network/401 errors are acceptable — token may already be invalid */
  }
}

export async function getMe(): Promise<UserResponse | null> {
  try {
    const res = await client.get('/auth/me')
    return res.data.data
  } catch (e) {
    if (e instanceof ApiError && e.statusCode === 401) return null
    throw e
  }
}
