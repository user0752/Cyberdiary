<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import MarkdownIt from 'markdown-it'
import DOMPurify from 'dompurify'
import hljs from 'highlight.js'
import 'highlight.js/styles/atom-one-dark.css'

const router = useRouter()

const props = defineProps<{
  content: string
}>()

// Simple slugify for wiki links
function slugify(text: string): string {
  return text
    .toLowerCase()
    .trim()
    .replace(/[^\w\s-]/g, '')
    .replace(/[-\s]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 80)
}

// Wiki link plugin for markdown-it
function wikiLinkPlugin(md: MarkdownIt) {
  // Add inline rule for [[...]]
  md.inline.ruler.before('link', 'wiki_link', (state: any, silent: boolean) => {
    const src = state.src.slice(state.pos)
    const match = src.match(/^\[\[([^\]]+)\]\]/)
    if (!match) return false

    const label = match[1].trim()
    const slug = slugify(label)

    if (!silent) {
      const token = state.push('wiki_link_open', 'a', 1)
      token.attrs = [
        ['href', `/wiki/${slug}`],
        ['class', 'wiki-link'],
        ['data-slug', slug],
      ]
      token.markup = '[['

      const textToken = state.push('text', '', 0)
      textToken.content = label

      const closeToken = state.push('wiki_link_close', 'a', -1)
      closeToken.markup = ']]'
    }

    state.pos += match[0].length
    return true
  })
}

const md = new MarkdownIt({
  html: false,
  breaks: true,
  linkify: true,
  highlight(str: string, lang: string) {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return hljs.highlight(str, { language: lang }).value
      } catch {
        // fall through
      }
    }
    return ''
  },
})

md.use(wikiLinkPlugin)

// Allow wiki-link attributes through DOMPurify
DOMPurify.addHook('uponSanitizeAttribute', (node, data) => {
  // Preserve data-slug on wiki-link anchors
  if (data.attrName === 'data-slug' && node.tagName === 'A') {
    data.forceKeepAttr = true
  }
})

const rendered = computed(() => {
  const raw = md.render(props.content)
  return DOMPurify.sanitize(raw, {
    ADD_ATTR: ['data-slug'],
    ADD_TAGS: [],
  })
})

// Intercept wiki link clicks for client-side routing
function handleClick(e: MouseEvent) {
  const target = e.target as HTMLElement
  const link = target.closest('a.wiki-link') as HTMLAnchorElement | null
  if (link) {
    e.preventDefault()
    const slug = link.getAttribute('data-slug')
    if (slug) {
      router.push(`/wiki/${slug}`)
    }
  }
}
</script>

<template>
  <div class="markdown-body" v-html="rendered" @click="handleClick"></div>
</template>

<style>
.markdown-body {
  font-size: 0.9rem;
  line-height: 1.75;
  color: var(--text-primary);
}

.markdown-body h1, .markdown-body h2, .markdown-body h3 {
  margin-top: 1.2em;
  margin-bottom: 0.6em;
  font-weight: 600;
  color: var(--text-primary);
}

.markdown-body h1 { font-size: 1.5rem; }
.markdown-body h2 { font-size: 1.25rem; }
.markdown-body h3 { font-size: 1.1rem; }

.markdown-body p {
  margin-bottom: 0.8em;
}

.markdown-body code {
  font-family: var(--font-mono);
  font-size: 0.85em;
  background: var(--bg-tertiary);
  padding: 2px 6px;
  border-radius: 4px;
}

.markdown-body pre {
  background: var(--bg-tertiary);
  border-radius: var(--radius-sm);
  padding: 14px 16px;
  overflow-x: auto;
  margin: 0.8em 0;
}

.markdown-body pre code {
  background: none;
  padding: 0;
}

.markdown-body blockquote {
  border-left: 3px solid var(--accent);
  padding-left: 14px;
  color: var(--text-secondary);
  margin: 0.8em 0;
}

.markdown-body ul, .markdown-body ol {
  padding-left: 1.5em;
  margin-bottom: 0.8em;
}

.markdown-body a {
  color: var(--accent);
}

.markdown-body a.wiki-link {
  color: var(--accent);
  background: var(--accent-muted);
  padding: 1px 5px;
  border-radius: 3px;
  font-weight: 500;
  text-decoration: none;
  transition: background var(--transition-fast);
}

.markdown-body a.wiki-link:hover {
  background: var(--accent);
  color: #fff;
}

.markdown-body img {
  max-width: 100%;
  border-radius: var(--radius-sm);
}

.markdown-body table {
  width: 100%;
  border-collapse: collapse;
  margin: 0.8em 0;
}

.markdown-body th, .markdown-body td {
  border: 1px solid var(--border);
  padding: 8px 12px;
  text-align: left;
}

.markdown-body th {
  background: var(--bg-tertiary);
  font-weight: 600;
}
</style>
