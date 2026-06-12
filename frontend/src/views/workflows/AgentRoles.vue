<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import SectionHeader from '@/components/layout/SectionHeader.vue';
import {
  createProfessionalRole,
  deleteProfessionalRole,
  listProfessionalRoles,
  type ProfessionalRole,
} from '@/api/agentRoles';

const roles = ref<ProfessionalRole[]>([]);
const loading = ref(false);
const showCreate = ref(false);
const form = ref({
  role_id: '',
  name: '',
  avatar: '🤖',
  category: 'custom',
  system_prompt: '',
  tools: [] as string[],
  responsibility: '',
  color: '#1677FF',
});

async function loadRoles(): Promise<void> {
  loading.value = true;
  try {
    roles.value = await listProfessionalRoles();
  } catch (err) {
    ElMessage.error('加载角色库失败');
  } finally {
    loading.value = false;
  }
}

async function handleCreate(): Promise<void> {
  if (!form.value.role_id || !form.value.name || !form.value.system_prompt) {
    ElMessage.warning('请填写必填项');
    return;
  }
  try {
    await createProfessionalRole(form.value);
    ElMessage.success('角色创建成功');
    showCreate.value = false;
    form.value = {
      role_id: '',
      name: '',
      avatar: '🤖',
      category: 'custom',
      system_prompt: '',
      tools: [],
      responsibility: '',
      color: '#1677FF',
    };
    await loadRoles();
  } catch (err) {
    ElMessage.error('创建失败');
  }
}

async function handleDelete(role: ProfessionalRole): Promise<void> {
  if (role.is_preset) return;
  try {
    await ElMessageBox.confirm(`确定删除角色「${role.name}」？`, '确认删除');
    await deleteProfessionalRole(role.id);
    ElMessage.success('已删除');
    await loadRoles();
  } catch {
    /* 用户取消 */
  }
}

onMounted(loadRoles);
</script>

<template>
  <div class="agent-roles-page">
    <SectionHeader title="专业角色库" subtitle="管理系统预设与自定义专业角色">
      <template #extra>
        <el-button type="primary" @click="showCreate = true">创建自定义角色</el-button>
      </template>
    </SectionHeader>

    <el-table v-loading="loading" :data="roles" stripe>
      <el-table-column label="角色" width="160">
        <template #default="{ row }">
          <span class="role-cell">{{ row.avatar }} {{ row.name }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="role_id" label="标识" width="140" />
      <el-table-column prop="category" label="分类" width="100" />
      <el-table-column prop="responsibility" label="职责" show-overflow-tooltip />
      <el-table-column label="工具" width="180">
        <template #default="{ row }">
          <el-tag v-for="t in row.tools.slice(0, 3)" :key="t" size="small" class="tool-tag">
            {{ t }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="类型" width="90">
        <template #default="{ row }">
          <el-tag :type="row.is_preset ? 'info' : 'success'" size="small">
            {{ row.is_preset ? '预设' : '自定义' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="80" fixed="right">
        <template #default="{ row }">
          <el-button
            v-if="!row.is_preset"
            type="danger"
            text
            size="small"
            @click="handleDelete(row)"
          >
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="showCreate" title="创建自定义角色" width="520px">
      <el-form label-position="top">
        <el-form-item label="角色标识" required>
          <el-input v-model="form.role_id" placeholder="如 legal_advisor" />
        </el-form-item>
        <el-form-item label="角色名称" required>
          <el-input v-model="form.name" placeholder="如 法律顾问" />
        </el-form-item>
        <el-form-item label="头像 Emoji">
          <el-input v-model="form.avatar" maxlength="4" />
        </el-form-item>
        <el-form-item label="职责描述" required>
          <el-input v-model="form.responsibility" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="系统提示词" required>
          <el-input v-model="form.system_prompt" type="textarea" :rows="4" />
        </el-form-item>
        <el-form-item label="可用工具（逗号分隔）">
          <el-input
            :model-value="form.tools.join(',')"
            placeholder="search, knowledge, python"
            @update:model-value="(v: string) => { form.tools = v.split(',').map((s) => s.trim()).filter(Boolean); }"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreate = false">取消</el-button>
        <el-button type="primary" @click="handleCreate">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style lang="scss" scoped>
.agent-roles-page {
  padding: 0 4px;
}

.role-cell {
  font-weight: 500;
}

.tool-tag {
  margin-right: 4px;
}
</style>
