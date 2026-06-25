<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()

interface GameItem {
  id: string
  name: string
  subtitle: string
  desc: string
  icon: string
  route?: string
  status: 'live' | 'beta'
  tags: string[]
  color: string
  glow: string
}

const games: GameItem[] = [
  {
    id: 'arena',
    name: 'KNOWLEDGE ARENA',
    subtitle: '知识防御战',
    desc: 'LLM 根据 Wiki 知识库实时出题，选择题形式检验知识掌握度。限时答题、连击得分、即时反馈。',
    icon: '⚔',
    route: '/game/arena',
    status: 'live',
    tags: ['答题', 'LLM', '即时反馈'],
    color: 'var(--accent)',
    glow: 'var(--accent-glow)',
  },
  {
    id: 'alchemy',
    name: 'CONCEPT ALCHEMY',
    subtitle: '概念炼金术',
    desc: '拖拽两张 Wiki 概念卡片合成新概念。理解知识关联才能预测合成结果，主动建构代替被动回忆。',
    icon: '⚗',
    status: 'beta',
    tags: ['合成', '探索', '知识建构'],
    color: 'var(--neon-green)',
    glow: 'var(--neon-green-glow)',
  },
  {
    id: 'wikiworld',
    name: 'WIKI WORLD',
    subtitle: 'Wiki 世界',
    desc: '知识图谱就是游戏地图。每个 Wiki 节点是一个可探索的区域，wiki_links 是连接区域的路径。',
    icon: '🌐',
    status: 'beta',
    tags: ['探索', '知识图谱', '沉浸式'],
    color: 'var(--neon-magenta)',
    glow: 'var(--neon-magenta-glow)',
  },
  {
    id: 'puzzle',
    name: 'KNOWLEDGE PUZZLE',
    subtitle: '知识解谜',
    desc: '用知识操作游戏世界。LLM 从 Wiki 自动生成环境谜题，不是答题而是「用知识改变世界」。',
    icon: '🧩',
    status: 'beta',
    tags: ['解谜', 'LLM', '情境应用'],
    color: 'var(--neon-yellow)',
    glow: 'rgba(240, 255, 0, 0.08)',
  },
  {
    id: 'defense',
    name: 'CONCEPT DEFENSE',
    subtitle: '概念防御战',
    desc: '防御塔 = 已掌握概念，敌人 = 误解概念。从答题版重构为无答题纯策略部署。理解度 = 塔的强度。',
    icon: '🏰',
    status: 'beta',
    tags: ['策略', '塔防', '知识应用'],
    color: 'var(--neon-orange)',
    glow: 'rgba(255, 107, 0, 0.08)',
  },
]

function enterGame(game: GameItem) {
  if (game.route) {
    router.push(game.route)
  }
}
</script>

<template>
  <div class="game-box">
    <!-- Header -->
    <header class="box-header">
      <div class="header-row">
        <span class="header-icon">&#9632;</span>
        <div>
          <h1 class="header-title">GAME BOX</h1>
          <p class="header-sub">游戏盒子 — 在游戏中学习，在学习中游戏</p>
        </div>
      </div>
    </header>

    <!-- Games Grid - Bento Layout -->
    <div class="games-bento">
      <div
        v-for="game in games"
        :key="game.id"
        class="game-card"
        :class="[`card-${game.id}`, game.status]"
      >
        <!-- Card glow border -->
        <div v-if="game.status === 'live'" class="card-glow"></div>

        <!-- Card inner -->
        <div class="card-inner">
          <!-- Top: icon + status -->
          <div class="card-top">
            <span class="card-icon">{{ game.icon }}</span>
            <span
              class="card-status"
              :style="{
                color: game.status === 'live' ? 'var(--neon-green)' : 'var(--neon-orange)',
                borderColor: game.status === 'live' ? 'var(--neon-green)' : 'var(--neon-orange)',
              }"
            >
              {{ game.status === 'live' ? 'LIVE' : 'BETA' }}
            </span>
          </div>

          <!-- Title area -->
          <div class="card-title-area">
            <h3 class="card-name">{{ game.name }}</h3>
            <span
              class="card-subtitle"
              :style="{ color: game.color }"
            >
              {{ game.subtitle }}
            </span>
          </div>

          <!-- Description -->
          <p class="card-desc">{{ game.desc }}</p>

          <!-- Tags -->
          <div class="card-tags">
            <span
              v-for="tag in game.tags"
              :key="tag"
              class="card-tag"
            >
              {{ tag }}
            </span>
          </div>

          <!-- Action area -->
          <div class="card-action">
            <button
              v-if="game.status === 'live'"
              class="btn-play"
              @click="enterGame(game)"
            >
              <span class="btn-play-text">ENTER GAME</span>
              <span class="btn-play-arrow">&rarr;</span>
            </button>
            <div v-else class="beta-notice">
              <span class="beta-dot"></span>
              <span class="beta-text">开发中，敬请期待</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.game-box {
  padding: 32px;
  max-width: 1100px;
  margin: 0 auto;
  min-height: 100vh;
}

/* ========== Header ========== */
.box-header {
  margin-bottom: 40px;
}

.header-row {
  display: flex;
  align-items: flex-start;
  gap: 14px;
}

.header-icon {
  font-size: 1.4rem;
  color: var(--accent);
  margin-top: 2px;
  text-shadow: var(--glow-sm);
  animation: neon-pulse 3s ease-in-out infinite;
}

.header-title {
  font-family: var(--font-display);
  font-size: 1.5rem;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: 0.2em;
  margin: 0;
  text-shadow: var(--glow-sm);
}

.header-sub {
  font-family: var(--font-mono);
  font-size: 0.7rem;
  color: var(--text-muted);
  margin-top: 4px;
  letter-spacing: 0.05em;
}

/* ========== Bento Grid ========== */
.games-bento {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  grid-template-rows: auto auto;
  gap: 20px;
}

@media (max-width: 900px) {
  .games-bento {
    grid-template-columns: 1fr 1fr;
  }
  .game-box {
    padding: 20px;
  }
}

@media (max-width: 600px) {
  .games-bento {
    grid-template-columns: 1fr;
  }
}

/* Featured game takes 2 cols */
.card-arena {
  grid-column: 1 / 3;
}

@media (max-width: 900px) {
  .card-arena {
    grid-column: 1 / 3;
  }
}

@media (max-width: 600px) {
  .card-arena {
    grid-column: 1;
  }
}

/* ========== Game Card ========== */
.game-card {
  position: relative;
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  overflow: hidden;
  transition: all var(--transition-smooth);
}

.game-card.live {
  border-color: var(--accent-dim);
}

.game-card.live:hover {
  border-color: var(--accent);
  transform: translateY(-2px);
  box-shadow: 0 4px 24px var(--accent-ghost);
}

.game-card.beta {
  opacity: 0.75;
}

.game-card.beta:hover {
  opacity: 0.9;
  border-color: var(--border-bright);
  transform: translateY(-2px);
}

/* Glow effect for live card */
.card-glow {
  position: absolute;
  inset: -1px;
  border-radius: inherit;
  background: linear-gradient(
    135deg,
    var(--accent-dim) 0%,
    transparent 40%,
    transparent 60%,
    var(--accent-dim) 100%
  );
  opacity: 0;
  transition: opacity var(--transition-glow);
  pointer-events: none;
}

.game-card.live:hover .card-glow {
  opacity: 0.15;
}

.card-inner {
  position: relative;
  padding: 24px;
  display: flex;
  flex-direction: column;
  height: 100%;
}

/* Card top row */
.card-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.card-icon {
  font-size: 1.6rem;
  filter: drop-shadow(0 0 4px currentColor);
}

.card-status {
  font-family: var(--font-mono);
  font-size: 0.55rem;
  font-weight: 700;
  letter-spacing: 0.15em;
  padding: 2px 8px;
  border: 1px solid;
  border-radius: var(--radius-sm);
}

/* Title area */
.card-title-area {
  margin-bottom: 10px;
}

.card-name {
  font-family: var(--font-display);
  font-size: 0.95rem;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: 0.1em;
  margin: 0 0 4px 0;
}

.card-arena .card-name {
  font-size: 1.1rem;
}

.card-subtitle {
  font-family: var(--font-sans);
  font-size: 0.75rem;
  font-weight: 500;
  letter-spacing: 0.05em;
}

/* Description */
.card-desc {
  font-family: var(--font-sans);
  font-size: 0.78rem;
  color: var(--text-secondary);
  line-height: 1.55;
  margin: 0 0 14px 0;
  flex: 1;
}

/* Tags */
.card-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}

.card-tag {
  font-family: var(--font-mono);
  font-size: 0.6rem;
  color: var(--text-muted);
  background: var(--bg-tertiary);
  padding: 3px 8px;
  border-radius: var(--radius-sm);
  letter-spacing: 0.05em;
  transition: all var(--transition-fast);
}

.game-card.live:hover .card-tag {
  background: var(--accent-ghost);
  color: var(--accent-dim);
}

/* Action area */
.card-action {
  margin-top: auto;
}

.btn-play {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  background: var(--accent);
  color: var(--bg-void);
  border: none;
  border-radius: var(--radius-sm);
  padding: 10px 22px;
  font-family: var(--font-display);
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0.12em;
  cursor: pointer;
  transition: all var(--transition-fast);
}

.btn-play:hover {
  background: var(--accent-hover);
  box-shadow: var(--glow-md);
  transform: scale(1.02);
}

.btn-play:active {
  transform: scale(0.98);
}

.btn-play-arrow {
  font-size: 1rem;
  transition: transform var(--transition-fast);
}

.btn-play:hover .btn-play-arrow {
  transform: translateX(3px);
}

/* Beta notice */
.beta-notice {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 14px;
  background: var(--bg-tertiary);
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-dim);
}

.beta-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--neon-orange);
  box-shadow: 0 0 6px rgba(255, 107, 0, 0.3);
  animation: blink 2s ease-in-out infinite;
}

.beta-text {
  font-family: var(--font-mono);
  font-size: 0.65rem;
  color: var(--text-muted);
  letter-spacing: 0.08em;
}

/* ========== Animations ========== */
@keyframes neon-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
</style>
