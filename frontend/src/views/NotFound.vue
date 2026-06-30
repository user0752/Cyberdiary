<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()
</script>

<template>
  <div class="not-found">
    <div class="nf-content">
      <div class="nf-code">404</div>
      <h1 class="nf-title">PAGE NOT FOUND</h1>
      <p class="nf-sub">// 请求的路径不存在于系统中</p>
      <div class="nf-actions">
        <button class="btn btn-ghost" @click="router.back()">← 返回上一页</button>
        <button class="btn btn-primary" @click="router.push('/memos')">回到主页</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.not-found {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 32px;
}

.nf-content {
  text-align: center;
  max-width: 480px;
}

.nf-code {
  font-family: var(--font-display);
  font-size: 6rem;
  font-weight: 900;
  color: var(--accent);
  letter-spacing: 0.1em;
  text-shadow: 0 0 20px var(--accent-glow), 0 0 40px var(--accent-glow);
  line-height: 1;
  margin-bottom: 16px;
  animation: neon-pulse 2.5s ease-in-out infinite;
}

.nf-title {
  font-family: var(--font-display);
  font-size: 1.1rem;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: 0.25em;
  margin-bottom: 8px;
}

.nf-sub {
  font-family: var(--font-mono);
  font-size: 0.78rem;
  color: var(--text-muted);
  margin-bottom: 28px;
}

.nf-actions {
  display: flex;
  gap: 12px;
  justify-content: center;
  flex-wrap: wrap;
}
</style>
