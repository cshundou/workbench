<script setup lang="ts">
import { ref } from 'vue';
import { useRoute } from 'vue-router';
import { getPublishInfo } from '@/api/publish';

const route = useRoute();
const info = ref<{ resource_type?: string; resource_id?: number } | null>(null);

async function loadInfo(): Promise<void> {
  const token = route.params.token as string;
  if (token) {
    info.value = await getPublishInfo(token);
  }
}

loadInfo();
</script>

<template>
  <div class="embed-page">
    <h2>AI Workbench 嵌入页面</h2>
    <p v-if="info">资源类型：{{ info.resource_type }} / ID：{{ info.resource_id }}</p>
    <p class="hint">通过 iframe 嵌入企业系统，支持自定义品牌与 SSO 扩展。</p>
  </div>
</template>

<style scoped>
.embed-page { padding: 24px; max-width: 640px; margin: 0 auto; }
.hint { color: var(--el-text-color-secondary); }
</style>
