<script setup lang="ts">
import { Cpu } from '@element-plus/icons-vue';
</script>

<template>
  <el-card shadow="never" class="placeholder-page">
    <el-empty description="智能体模块开发中">
      <template #image>
        <el-icon :size="64" color="#67c23a"><Cpu /></el-icon>
      </template>
      <p class="placeholder-desc">后续将在此接入单 Agent 对话、工具调用与智能体配置功能。</p>
    </el-empty>
  </el-card>
</template>

<style lang="scss" scoped>
.placeholder-page {
  min-height: 400px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.placeholder-desc {
  margin: 8px 0 0;
  font-size: 14px;
  color: $text-secondary;
}
</style>
