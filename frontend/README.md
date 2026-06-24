# CyberNote Frontend

Vue 3 + Vite + TypeScript 前端应用，提供赛博笔记的 Web 交互界面。

## 技术栈

- Vue 3 (Composition API + `<script setup>`)
- Vite 6
- TypeScript
- Pinia 状态管理
- CodeMirror 6 (Markdown 编辑器)
- force-graph / Three.js (知识图谱可视化)
- Phaser.js v3 (塔防游戏模块)

## 启动

```bash
npm install
npm run dev
```

默认访问 `http://localhost:5173`

## 目录结构

```
src/
├── api/          # API 请求封装
├── assets/       # 静态资源
├── components/   # 通用组件 + graph/ 图谱子组件
├── composables/  # 组合式函数 (SSE流、图谱渲染等)
├── router/       # Vue Router 路由配置
├── stores/       # Pinia 状态存储
├── styles/       # 全局样式变量
├── types/        # TypeScript 类型定义
└── views/        # 页面视图
```
