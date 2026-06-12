<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import SectionHeader from '@/components/layout/SectionHeader.vue';
import {
  addPluginReview,
  getPluginDetail,
  installPlugin,
  type PluginInfo,
} from '@/api/plugins';

const route = useRoute();
const router = useRouter();
const loading = ref(false);
const plugin = ref<(PluginInfo & { skills: { skill_key: string; name: string; description: string }[]; reviews: { rating: number; comment?: string; created_at: string }[] }) | null>(null);
const reviewRating = ref(5);
const reviewComment = ref('');

const pluginId = route.params.pluginId as string;

async function fetchDetail(): Promise<void> {
  loading.value = true;
  try {
    plugin.value = await getPluginDetail(pluginId);
  } finally {
    loading.value = false;
  }
}

async function handleInstall(): Promise<void> {
  await installPlugin(pluginId);
  ElMessage.success('安装成功');
  fetchDetail();
}

async function submitReview(): Promise<void> {
  await addPluginReview(pluginId, reviewRating.value, reviewComment.value || undefined);
  ElMessage.success('评论已提交');
  reviewComment.value = '';
  fetchDetail();
}

onMounted(fetchDetail);
</script>

<template>
  <div v-loading="loading">
    <SectionHeader :title="plugin?.name || '插件详情'" description="">
      <template #actions>
        <el-button @click="router.push({ name: 'PluginMarketplace' })">返回市场</el-button>
        <el-button type="primary" @click="handleInstall">安装插件</el-button>
      </template>
    </SectionHeader>
    <div v-if="plugin" class="detail">
      <div class="hero">
        <span class="icon">{{ plugin.icon || '🔌' }}</span>
        <div>
          <h1>{{ plugin.name }}</h1>
          <p class="meta">
            作者：{{ plugin.author }} · 版本 v{{ plugin.version }} ·
            ⭐ {{ plugin.rating_avg.toFixed(1) }} ({{ plugin.rating_count }} 条评价)
          </p>
          <p class="desc">{{ plugin.description }}</p>
        </div>
      </div>

      <el-card class="section">
        <template #header>功能 Skill</template>
        <el-table :data="plugin.skills" stripe>
          <el-table-column prop="name" label="Skill" />
          <el-table-column prop="description" label="说明" show-overflow-tooltip />
        </el-table>
      </el-card>

      <el-card class="section">
        <template #header>权限声明</template>
        <el-tag v-for="perm in plugin.permissions" :key="perm" class="perm-tag">{{ perm }}</el-tag>
      </el-card>

      <el-card class="section">
        <template #header>用户评价</template>
        <div v-for="r in plugin.reviews" :key="r.created_at" class="review">
          <el-rate :model-value="r.rating" disabled />
          <p>{{ r.comment || '无评论' }}</p>
        </div>
        <div class="review-form">
          <el-rate v-model="reviewRating" />
          <el-input v-model="reviewComment" type="textarea" placeholder="写下你的评价..." />
          <el-button type="primary" @click="submitReview">提交评价</el-button>
        </div>
      </el-card>
    </div>
  </div>
</template>

<style scoped>
.hero {
  display: flex;
  gap: 20px;
  margin-bottom: 24px;
}
.icon {
  font-size: 48px;
}
.hero h1 {
  margin: 0 0 8px;
}
.meta {
  color: #909399;
  font-size: 14px;
}
.desc {
  margin-top: 12px;
  line-height: 1.6;
}
.section {
  margin-bottom: 16px;
}
.perm-tag {
  margin: 0 8px 8px 0;
}
.review {
  margin-bottom: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid #ebeef5;
}
.review-form {
  margin-top: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-width: 480px;
}
</style>
