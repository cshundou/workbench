<script setup lang="ts">
import { Collection } from '@element-plus/icons-vue';
</script>

<template>
  <el-card shadow="never" class="placeholder-page">
    <el-empty description="知识库模块开发中">
      <template #image>
        <el-icon :size="64" color="#409eff"><Collection /></el-icon>
      </template>
      <p class="placeholder-desc">后续将在此接入文档上传、增强 RAG 检索与知识库管理功能。</p>
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
