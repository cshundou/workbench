<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import type { ErrorSuggestion } from '@/api/workflow';

const props = defineProps<{
  message: string;
  suggestions?: ErrorSuggestion[];
  rawError?: string | null;
  collapsible?: boolean;
}>();

const emit = defineEmits<{
  action: [suggestion: ErrorSuggestion];
  retry: [];
  openNode: [nodeId: string];
}>();

const router = useRouter();
const showRaw = ref<string[]>([]);

function handleSuggestion(suggestion: ErrorSuggestion): void {
  emit('action', suggestion);
  const type = suggestion.action_type;
  const target = suggestion.action_target;
  if (type === 'retry') {
    emit('retry');
    return;
  }
  if (type === 'open_node' && target) {
    emit('openNode', target);
    return;
  }
  if (type === 'route' && target) {
    router.push(target);
  }
}
</script>

<template>
  <div class="error-advice-panel">
    <el-alert type="error" :title="message" show-icon :closable="false">
      <template v-if="suggestions?.length" #default>
        <div class="suggestions">
          <p class="suggestions-title">修改建议</p>
          <ul class="suggestion-list">
            <li v-for="(item, index) in suggestions" :key="index" class="suggestion-item">
              <strong>{{ item.title }}</strong>
              <span> — {{ item.description }}</span>
              <el-button
                v-if="item.action_type"
                link
                type="primary"
                size="small"
                class="suggestion-action"
                @click="handleSuggestion(item)"
              >
                去处理
              </el-button>
            </li>
          </ul>
        </div>
      </template>
    </el-alert>
    <el-collapse v-if="collapsible !== false && rawError" v-model="showRaw" class="raw-collapse">
      <el-collapse-item title="查看技术详情" name="raw">
        <pre class="raw-error">{{ rawError }}</pre>
      </el-collapse-item>
    </el-collapse>
  </div>
</template>

<style lang="scss" scoped>
.error-advice-panel {
  margin-bottom: 12px;
}

.suggestions {
  margin-top: 8px;
}

.suggestions-title {
  margin: 0 0 6px;
  font-size: 13px;
  font-weight: 600;
}

.suggestion-list {
  margin: 0;
  padding-left: 18px;
  font-size: 13px;
  line-height: 1.6;
}

.suggestion-item {
  margin-bottom: 4px;
}

.suggestion-action {
  margin-left: 4px;
}

.raw-collapse {
  margin-top: 8px;
  border: none;

  :deep(.el-collapse-item__header) {
    height: 32px;
    font-size: 12px;
    color: var(--el-text-color-secondary);
  }
}

.raw-error {
  margin: 0;
  padding: 8px;
  font-size: 12px;
  background: var(--el-fill-color-light);
  border-radius: 4px;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
