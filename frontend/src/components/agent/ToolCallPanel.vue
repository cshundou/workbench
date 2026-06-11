<script setup lang="ts">
import { Loading } from '@element-plus/icons-vue';
import type { ToolCallStep } from '@/api/agent';

defineProps<{
  steps: ToolCallStep[];
  thinkingText?: string;
  isActive?: boolean;
}>();

function formatJson(value: unknown): string {
  if (value === undefined || value === null) {
    return '';
  }
  if (typeof value === 'string') {
    try {
      return JSON.stringify(JSON.parse(value), null, 2);
    } catch {
      return value;
    }
  }
  return JSON.stringify(value, null, 2);
}
</script>

<template>
  <div class="tool-call-panel">
    <div v-if="thinkingText && isActive" class="thinking-status">
      <el-icon class="is-loading"><Loading /></el-icon>
      <span>{{ thinkingText }}</span>
    </div>

    <el-empty
      v-if="steps.length === 0 && !thinkingText"
      description="暂无工具调用"
      :image-size="60"
    />

    <el-collapse v-else accordion>
      <el-collapse-item
        v-for="(step, index) in steps"
        :key="`${step.tool_name}-${index}`"
        :name="index"
      >
        <template #title>
          <div class="step-title">
            <el-tag size="small" type="primary">{{ step.tool_label || step.tool_name }}</el-tag>
            <span class="step-summary">工具调用完成</span>
          </div>
        </template>

        <div class="step-detail">
          <div class="detail-block">
            <h4>入参</h4>
            <pre>{{ formatJson(step.tool_input) }}</pre>
          </div>
          <div class="detail-block">
            <h4>返回结果</h4>
            <pre>{{ formatJson(step.tool_output) }}</pre>
          </div>
        </div>
      </el-collapse-item>
    </el-collapse>
  </div>
</template>

<style lang="scss" scoped>
.tool-call-panel {
  height: 100%;
  overflow-y: auto;
  padding: 12px;
}

.thinking-status {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px;
  margin-bottom: 12px;
  background: rgba($primary-color, 0.06);
  border: 1px solid rgba($primary-color, 0.2);
  border-radius: $border-radius;
  color: $text-regular;
  font-size: 14px;
}

.step-title {
  display: flex;
  align-items: center;
  gap: 8px;
}

.step-summary {
  font-size: 13px;
  color: $text-secondary;
}

.step-detail {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.detail-block {
  h4 {
    margin: 0 0 6px;
    font-size: 13px;
    color: $text-primary;
  }

  pre {
    margin: 0;
    padding: 10px;
    background: #f5f7fa;
    border-radius: 6px;
    font-size: 12px;
    line-height: 1.5;
    overflow-x: auto;
    white-space: pre-wrap;
    word-break: break-all;
  }
}
</style>
