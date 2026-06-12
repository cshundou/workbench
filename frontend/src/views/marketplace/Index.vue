<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import SectionHeader from '@/components/layout/SectionHeader.vue';
import { listMarketplaceTemplates, type MarketplaceTemplateItem } from '@/api/marketplace';
import { createWorkflowFromTemplate } from '@/api/workflow';

const router = useRouter();
const loading = ref(false);
const templates = ref<MarketplaceTemplateItem[]>([]);
const keyword = ref('');
const category = ref('');
const industry = ref('');

async function fetchTemplates(): Promise<void> {
  loading.value = true;
  try {
    const result = await listMarketplaceTemplates({
      keyword: keyword.value || undefined,
      category: category.value || undefined,
      industry: industry.value || undefined,
    });
    templates.value = result.items;
  } finally {
    loading.value = false;
  }
}

async function useTemplate(row: MarketplaceTemplateItem): Promise<void> {
  try {
    const wf = await createWorkflowFromTemplate(row.id, row.name);
    ElMessage.success('已从模板创建工作流');
    router.push(`/workflows/${wf.id}/edit`);
  } catch (err) {
    console.error('[Marketplace]', err);
  }
}

onMounted(fetchTemplates);
</script>

<template>
  <div>
    <SectionHeader
      title="模板市场"
      :description="`官方模板 ${templates.length} 个，支持分类搜索与一键使用`"
    />
    <div class="filters">
      <el-input v-model="keyword" placeholder="搜索模板" clearable style="width: 220px" />
      <el-select v-model="category" placeholder="分类" clearable style="width: 160px">
        <el-option label="客服" value="客服" />
        <el-option label="销售" value="销售" />
        <el-option label="市场" value="市场" />
        <el-option label="人事" value="人事" />
        <el-option label="财务" value="财务" />
        <el-option label="行政" value="行政" />
        <el-option label="行业方案" value="行业方案" />
      </el-select>
      <el-select v-model="industry" placeholder="行业" clearable style="width: 140px">
        <el-option label="制造业" value="制造业" />
        <el-option label="金融" value="金融" />
        <el-option label="医疗" value="医疗" />
        <el-option label="教育" value="教育" />
        <el-option label="零售" value="零售" />
      </el-select>
      <el-button type="primary" @click="fetchTemplates">搜索</el-button>
    </div>
    <el-table v-loading="loading" :data="templates" stripe>
      <el-table-column prop="name" label="名称" min-width="180">
        <template #default="{ row }">
          {{ row.name }}
          <el-tag v-if="row.is_official" size="small" type="success" class="official-tag">官方</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="category" label="分类" width="100" />
      <el-table-column prop="industry" label="行业" width="100" />
      <el-table-column prop="description" label="描述" min-width="240" show-overflow-tooltip />
      <el-table-column prop="node_count" label="节点数" width="80" />
      <el-table-column label="操作" width="120">
        <template #default="{ row }">
          <el-button type="primary" link @click="useTemplate(row)">使用</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<style scoped>
.filters {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}
</style>
