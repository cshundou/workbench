<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import SectionHeader from '@/components/layout/SectionHeader.vue';
import {
  listSkills,
  setSkillStatus,
  testSkill,
  type SkillInfo,
} from '@/api/plugins';

const router = useRouter();
const loading = ref(false);
const skills = ref<SkillInfo[]>([]);
const testDialogVisible = ref(false);
const testingSkill = ref<SkillInfo | null>(null);
const testParams = ref('{}');
const testResult = ref('');
const testLoading = ref(false);

async function fetchSkills(): Promise<void> {
  loading.value = true;
  try {
    skills.value = await listSkills();
  } finally {
    loading.value = false;
  }
}

async function toggleSkill(skill: SkillInfo): Promise<void> {
  const enabled = !skill.is_enabled;
  await setSkillStatus(skill.skill_key, enabled);
  ElMessage.success(enabled ? '已启用' : '已禁用');
  fetchSkills();
}

function openTest(skill: SkillInfo): void {
  testingSkill.value = skill;
  testParams.value = '{}';
  testResult.value = '';
  testDialogVisible.value = true;
}

async function runTest(): Promise<void> {
  if (!testingSkill.value) return;
  testLoading.value = true;
  try {
    const parameters = JSON.parse(testParams.value);
    const result = await testSkill(testingSkill.value.skill_key, parameters);
    testResult.value = JSON.stringify(result, null, 2);
  } catch (err) {
    testResult.value = String(err);
  } finally {
    testLoading.value = false;
  }
}

onMounted(fetchSkills);
</script>

<template>
  <div>
    <SectionHeader title="技能配置" description="管理平台原生、MCP 与插件 Skill">
      <template #actions>
        <el-button @click="router.push({ name: 'PluginMarketplace' })">插件市场</el-button>
        <el-button @click="router.push({ name: 'McpServers' })">MCP 服务器</el-button>
      </template>
    </SectionHeader>
    <el-table v-loading="loading" :data="skills" stripe>
      <el-table-column prop="name" label="Skill" width="160">
        <template #default="{ row }">
          <span>{{ row.icon || '⚡' }} {{ row.name }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="skill_key" label="Key" width="180" show-overflow-tooltip />
      <el-table-column prop="source_type" label="来源" width="90" />
      <el-table-column prop="description" label="说明" show-overflow-tooltip />
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="row.is_enabled ? 'success' : 'info'" size="small">
            {{ row.is_enabled ? '启用' : '禁用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="180">
        <template #default="{ row }">
          <el-button link type="primary" @click="openTest(row)">测试</el-button>
          <el-button link @click="toggleSkill(row)">
            {{ row.is_enabled ? '禁用' : '启用' }}
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="testDialogVisible" title="Skill 测试" width="560px">
      <p v-if="testingSkill"><strong>{{ testingSkill.name }}</strong></p>
      <el-form label-width="80px">
        <el-form-item label="参数 JSON">
          <el-input v-model="testParams" type="textarea" :rows="4" />
        </el-form-item>
        <el-form-item label="结果">
          <el-input v-model="testResult" type="textarea" :rows="6" readonly />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="testDialogVisible = false">关闭</el-button>
        <el-button type="primary" :loading="testLoading" @click="runTest">运行测试</el-button>
      </template>
    </el-dialog>
  </div>
</template>
