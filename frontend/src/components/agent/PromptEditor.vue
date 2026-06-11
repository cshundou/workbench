<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue';
import * as monaco from 'monaco-editor';

const props = withDefaults(
  defineProps<{
    modelValue: string;
    height?: string;
    readonly?: boolean;
  }>(),
  {
    height: '240px',
    readonly: false,
  },
);

const emit = defineEmits<{
  'update:modelValue': [value: string];
}>();

const containerRef = ref<HTMLDivElement | null>(null);
const isFullscreen = ref(false);
let editor: monaco.editor.IStandaloneCodeEditor | null = null;

function initEditor(): void {
  if (!containerRef.value) {
    return;
  }
  editor = monaco.editor.create(containerRef.value, {
    value: props.modelValue,
    language: 'markdown',
    theme: 'vs',
    readOnly: props.readonly,
    minimap: { enabled: false },
    lineNumbers: 'on',
    wordWrap: 'on',
    scrollBeyondLastLine: false,
    automaticLayout: true,
    fontSize: 13,
  });
  editor.onDidChangeModelContent(() => {
    emit('update:modelValue', editor?.getValue() || '');
  });
}

watch(
  () => props.modelValue,
  (value) => {
    if (editor && editor.getValue() !== value) {
      editor.setValue(value);
    }
  },
);

watch(
  () => props.readonly,
  (readonly) => {
    editor?.updateOptions({ readOnly: readonly });
  },
);

function toggleFullscreen(): void {
  isFullscreen.value = !isFullscreen.value;
  setTimeout(() => editor?.layout(), 100);
}

onMounted(() => {
  initEditor();
});

onBeforeUnmount(() => {
  editor?.dispose();
  editor = null;
});
</script>

<template>
  <div class="prompt-editor" :class="{ fullscreen: isFullscreen }">
    <div class="editor-toolbar">
      <span class="toolbar-label">系统提示词</span>
      <el-button text size="small" @click="toggleFullscreen">
        {{ isFullscreen ? '退出全屏' : '全屏编辑' }}
      </el-button>
    </div>
    <div ref="containerRef" class="editor-container" :style="{ height }" />
  </div>
</template>

<style lang="scss" scoped>
.prompt-editor {
  border: 1px solid $border-color;
  border-radius: $border-radius-md;
  overflow: hidden;
  background: #fff;

  &.fullscreen {
    position: fixed;
    inset: 24px;
    z-index: 3000;
    box-shadow: $shadow-card;

    .editor-container {
      height: calc(100% - 40px) !important;
    }
  }
}

.editor-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 4px 12px;
  background: $bg-color;
  border-bottom: 1px solid $border-color;
}

.toolbar-label {
  font-size: 12px;
  color: $text-secondary;
}

.editor-container {
  width: 100%;
}
</style>
