<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import SectionHeader from '@/components/layout/SectionHeader.vue';
import { deleteTeamTemplate, listTeamTemplates, saveTeamTemplate, type TeamTemplateItem } from '@/api/agentRoles';

const loading = ref(false);
const officialTemplates = ref<TeamTemplateItem[]>([]);
const customTemplates = ref<TeamTemplateItem[]>([]);
const createDialogVisible = ref(false);
const form = ref({
  name: '',
  description: '',
  scenario: 'enterprise',
  is_public: false,
  team_config: {
    team_id: '',
    task_description: '企业任务模板',
    team_size: 0,
    members: [],
    workflow: '',
    max_review_rounds: 3,
  },
});

async function loadTemplates(): Promise<void> {
  loading.value = true;
  try {
    const data = await listTeamTemplates();
    officialTemplates.value = data.official;
    customTemplates.value = data.custom;
  } catch (error) {
    ElMessage.error('加载团队模板失败');
  } finally {
    loading.value = false;
  }
}

async function createTemplate(): Promise<void> {
  if (!form.value.name.trim()) {
    ElMessage.warning('请输入模板名称');
    return;
  }
  try {
    await saveTeamTemplate(form.value);
    ElMessage.success('模板保存成功');
    createDialogVisible.value = false;
    form.value.name = '';
    form.value.description = '';
    await loadTemplates();
  } catch (error) {
    ElMessage.error('模板保存失败');
  }
}

async function removeTemplate(row: TeamTemplateItem): Promise<void> {
  if (!row.id || row.is_official) {
    return;
  }
  try {
    await ElMessageBox.confirm(`确认删除模板「${row.name}」？`, '删除模板');
    await deleteTeamTemplate(Number(row.id));
    ElMessage.success('模板已删除');
    await loadTemplates();
  } catch (error) {
    // ignore cancel
  }
}

onMounted(() => {
  void loadTemplates();
});
</script>

<template>
  <div class="team-management-page">
    <SectionHeader title="多 Agent 团队管理" subtitle="管理内置企业团队与自定义团队模板">
      <template #extra>
        <el-button type="primary" @click="createDialogVisible = true">新增团队模板</el-button>
      </template>
    </SectionHeader>

    <el-card v-loading="loading" shadow="never" class="card-block">
      <template #header>内置团队（数据库远程加载）</template>
      <el-table :data="officialTemplates" stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="团队名称" min-width="220" />
        <el-table-column prop="scenario" label="场景" width="120" />
        <el-table-column prop="description" label="说明" min-width="240" show-overflow-tooltip />
      </el-table>
    </el-card>

    <el-card v-loading="loading" shadow="never" class="card-block">
      <template #header>自定义团队</template>
      <el-table :data="customTemplates" stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="团队名称" min-width="220" />
        <el-table-column prop="scenario" label="场景" width="120" />
        <el-table-column prop="description" label="说明" min-width="220" show-overflow-tooltip />
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button type="danger" text @click="removeTemplate(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="createDialogVisible" title="新增团队模板" width="560px">
      <el-form label-position="top">
        <el-form-item label="模板名称" required>
          <el-input v-model="form.name" placeholder="如：企业调研执行团队" />
        </el-form-item>
        <el-form-item label="场景">
          <el-input v-model="form.scenario" placeholder="enterprise / marketing / finance" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item label="公开模板">
          <el-switch v-model="form.is_public" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="createTemplate">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped lang="scss">
.team-management-page {
  padding: 0 4px;
}

.card-block {
  margin-top: 12px;
}
</style>
