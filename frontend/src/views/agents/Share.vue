<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import request from '@/api/request';
import type { AgentInfo } from '@/api/agent';
import SectionHeader from '@/components/layout/SectionHeader.vue';

const route = useRoute();
const router = useRouter();
const shareToken = computed(() => String(route.params.token));
const agent = ref<AgentInfo | null>(null);
const loading = ref(false);

async function loadSharedAgent(): Promise<void> {
  loading.value = true;
  try {
    agent.value = (await request.get(`/agents/share/${shareToken.value}`)) as AgentInfo;
  } catch {
    ElMessage.error('分享链接无效或已失效');
  } finally {
    loading.value = false;
  }
}

async function handleCopyToMine(): Promise<void> {
  try {
    const copied = (await request.post(
      `/agents/share/${shareToken.value}/copy`,
    )) as AgentInfo;
    ElMessage.success('已复制到我的智能体');
    router.push({ name: 'AgentConfig', params: { id: copied.id } });
  } catch {
    ElMessage.error('复制失败，请先登录');
    router.push({ name: 'Login' });
  }
}

onMounted(() => {
  void loadSharedAgent();
});
</script>

<template>
  <div v-loading="loading" class="share-page">
    <SectionHeader title="智能体分享" description="查看并复制他人分享的智能体配置" />
    <el-card v-if="agent" shadow="never">
      <h3>{{ agent.name }}</h3>
      <p class="desc">{{ agent.description || '暂无描述' }}</p>
      <el-descriptions :column="1" border size="small" class="mt-4">
        <el-descriptions-item label="模型">{{ agent.model_name }}</el-descriptions-item>
        <el-descriptions-item label="温度">{{ agent.temperature }}</el-descriptions-item>
        <el-descriptions-item label="工具">{{ agent.tools.join(', ') || '无' }}</el-descriptions-item>
      </el-descriptions>
      <el-button type="primary" class="mt-4" @click="handleCopyToMine">
        复制到我的智能体
      </el-button>
    </el-card>
  </div>
</template>

<style scoped>
.desc {
  color: var(--el-text-color-secondary);
}
.mt-4 {
  margin-top: 16px;
}
</style>
