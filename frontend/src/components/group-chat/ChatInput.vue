<script setup lang="ts">
import { ref } from 'vue';
import { Position } from '@element-plus/icons-vue';

const props = defineProps<{
  disabled?: boolean;
  loading?: boolean;
}>();

const emit = defineEmits<{
  send: [content: string];
}>();

const input = ref('');

function handleSend(): void {
  const text = input.value.trim();
  if (!text || props.disabled || props.loading) return;
  emit('send', text);
  input.value = '';
}

function handleKeydown(e: KeyboardEvent): void {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    handleSend();
  }
}
</script>

<template>
  <footer class="chat-input-bar">
    <el-input
      v-model="input"
      type="textarea"
      :rows="2"
      placeholder="输入补充信息，随时发言..."
      :disabled="disabled"
      resize="none"
      @keydown="handleKeydown"
    />
    <el-button
      type="primary"
      :icon="Position"
      :loading="loading"
      :disabled="disabled || !input.trim()"
      @click="handleSend"
    >
      发送
    </el-button>
  </footer>
</template>

<style lang="scss" scoped>
.chat-input-bar {
  display: flex;
  gap: 12px;
  align-items: flex-end;
  padding: 16px 24px;
  border-top: 1px solid $border-color;
  background: $bg-white;
}
</style>
