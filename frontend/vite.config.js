import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

// 前端经 nginx 代理在 /fpy/ 下访问（http://dl.piaozone.com:18025/fpy/）
export default defineConfig({
  base: '/fpy/',
  plugins: [vue()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  server: {
    host: '0.0.0.0',
    port: 8080,
    proxy: {
      // 生产经宿主 nginx /ticket-api/ 剥前缀到后端；本地预览同样剥掉 /ticket-api
      '/ticket-api': {
        target: process.env.VITE_PROXY_TARGET || 'http://127.0.0.1:8000',
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/ticket-api/, ''),
      },
      '/api': { target: process.env.VITE_PROXY_TARGET || 'http://127.0.0.1:8000', changeOrigin: true },
      '/webhook': { target: process.env.VITE_PROXY_TARGET || 'http://127.0.0.1:8000', changeOrigin: true },
    },
  },
})
