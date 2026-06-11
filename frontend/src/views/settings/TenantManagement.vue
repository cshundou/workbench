<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import type { FormInstance, FormRules } from 'element-plus';
import SectionHeader from '@/components/layout/SectionHeader.vue';
import {
  createTenant,
  deleteTenant,
  getTenants,
  updateTenant,
  type TenantInfo,
} from '@/api/tenant';

const loading = ref(false);
const tenants = ref<TenantInfo[]>([]);
const total = ref(0);
const queryParams = reactive({ page: 1, page_size: 10 });

const dialogVisible = ref(false);
const isEdit = ref(false);
const editingId = ref<number | null>(null);
const formRef = ref<FormInstance>();
const submitLoading = ref(false);

const form = reactive({ name: '', domain: '', status: 1 });
const rules: FormRules = {
  name: [{ required: true, message: '请输入租户名称', trigger: 'blur' }],
  domain: [{ required: true, message: '请输入域标识', trigger: 'blur' }],
};

async function fetchList(): Promise<void> {
  loading.value = true;
  try {
    const result = await getTenants(queryParams);
    tenants.value = result.items;
    total.value = result.total;
  } finally {
    loading.value = false;
  }
}

function openCreate(): void {
  isEdit.value = false;
  editingId.value = null;
  form.name = '';
  form.domain = '';
  form.status = 1;
  dialogVisible.value = true;
}

function openEdit(row: TenantInfo): void {
  isEdit.value = true;
  editingId.value = row.id;
  form.name = row.name;
  form.domain = row.domain;
  form.status = row.status;
  dialogVisible.value = true;
}

async function handleSubmit(): Promise<void> {
  const valid = await formRef.value?.validate().catch(() => false);
  if (!valid) return;
  submitLoading.value = true;
  try {
    if (isEdit.value && editingId.value) {
      await updateTenant(editingId.value, { ...form });
      ElMessage.success('更新成功');
    } else {
      await createTenant({ ...form });
      ElMessage.success('创建成功');
    }
    dialogVisible.value = false;
    fetchList();
  } finally {
    submitLoading.value = false;
  }
}

async function handleDelete(row: TenantInfo): Promise<void> {
  await ElMessageBox.confirm(`确定删除租户「${row.name}」？`, '删除确认', { type: 'warning' });
  await deleteTenant(row.id);
  ElMessage.success('删除成功');
  fetchList();
}

onMounted(() => {
  fetchList();
});
</script>

<template>
  <div>
    <SectionHeader title="租户管理" description="超级管理员专用，管理多租户实例">
      <template #actions>
        <el-button type="primary" @click="openCreate">新建租户</el-button>
      </template>
    </SectionHeader>

    <el-table v-loading="loading" :data="tenants" stripe>
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="name" label="名称" min-width="160" />
      <el-table-column prop="domain" label="域标识" min-width="160" />
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.status === 1 ? 'success' : 'info'" size="small">
            {{ row.status === 1 ? '启用' : '禁用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" width="180" />
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <el-button text type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button text type="danger" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" :title="isEdit ? '编辑租户' : '新建租户'" width="480px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="域标识" prop="domain">
          <el-input v-model="form.domain" />
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="form.status" :active-value="1" :inactive-value="0" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitLoading" @click="handleSubmit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>
