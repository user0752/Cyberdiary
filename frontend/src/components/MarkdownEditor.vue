<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue'
import { EditorView, keymap, lineNumbers, placeholder as cmPlaceholder } from '@codemirror/view'
import { EditorState } from '@codemirror/state'
import { defaultKeymap } from '@codemirror/commands'
import { markdown, markdownLanguage } from '@codemirror/lang-markdown'
import { oneDark } from '@codemirror/theme-one-dark'
import { languages } from '@codemirror/language-data'

const props = defineProps<{
  modelValue: string
  placeholder?: string
}>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
}>()

const editorRef = ref<HTMLDivElement>()
let view: EditorView | null = null

onMounted(() => {
  if (!editorRef.value) return

  const updateListener = EditorView.updateListener.of((update) => {
    if (update.docChanged) {
      emit('update:modelValue', update.state.doc.toString())
    }
  })

  view = new EditorView({
    state: EditorState.create({
      doc: props.modelValue,
      extensions: [
        lineNumbers(),
        cmPlaceholder(props.placeholder || '写点什么...'),
        markdown({ base: markdownLanguage, codeLanguages: languages }),
        oneDark,
        keymap.of(defaultKeymap),
        updateListener,
        EditorView.theme({
          '&': { height: '100%', fontSize: '0.9rem' },
          '.cm-scroller': { overflow: 'auto' },
          '.cm-content': { padding: '12px 0', fontFamily: 'var(--font-mono)' },
          '.cm-gutters': { border: 'none', background: 'transparent', color: 'var(--text-muted)' },
        }),
      ],
    }),
    parent: editorRef.value,
  })
})

// Destroy the CodeMirror view on unmount to avoid dangling DOM listeners
// and EditorState lingering in memory after the component is gone.
onUnmounted(() => {
  view?.destroy()
  view = null
})

watch(() => props.modelValue, (val) => {
  if (view && val !== view.state.doc.toString()) {
    view.dispatch({
      changes: { from: 0, to: view.state.doc.length, insert: val },
    })
  }
})
</script>

<template>
  <div ref="editorRef" class="markdown-editor"></div>
</template>

<style scoped>
.markdown-editor {
  height: 100%;
  min-height: 300px;
  background: var(--bg-primary);
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  overflow: hidden;
}
</style>
