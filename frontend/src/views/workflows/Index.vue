<script setup lang="ts">
import { Share } from '@element-plus/icons-vue';
</script>

<template>
  <el-card shadow="never" class="placeholder-page">
    <el-empty description="工作流模块开发中">
      <template #image>
        <el-icon :size="64" color="#e6a23c"><Share /></el-icon>
      </template>
      <p class="placeholder-desc">后续将在此接入 LangGraph 多智能体工作流编排与执行监控功能。</p>
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
