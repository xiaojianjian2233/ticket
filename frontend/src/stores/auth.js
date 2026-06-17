import { defineStore } from 'pinia'
import { authApi } from '@/api'
import { ROLE_RANK } from '@/dicts'

export const useAuth = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('token') || '',
    user: JSON.parse(localStorage.getItem('user') || 'null'),
  }),
  getters: {
    isLogin: (s) => !!s.token,
    role: (s) => s.user?.role || 'visitor',
    can: (s) => (min) => (ROLE_RANK[s.user?.role] ?? 0) >= (ROLE_RANK[min] ?? 0),
  },
  actions: {
    setSession(token, user) {
      this.token = token
      this.user = user
      localStorage.setItem('token', token)
      localStorage.setItem('user', JSON.stringify(user))
    },
    logout() {
      this.token = ''
      this.user = null
      localStorage.removeItem('token')
      localStorage.removeItem('user')
    },
    async fetchLoginUrl() {
      const { authorize_url } = await authApi.loginUrl()
      return authorize_url
    },
    async handleCallback(code) {
      const data = await authApi.callback(code)
      this.setSession(data.access_token, data.user)
      return data
    },
  },
})
