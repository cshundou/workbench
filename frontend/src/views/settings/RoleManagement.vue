<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import type { FormInstance, FormRules } from 'element-plus';
import { Plus, Search } from '@element-plus/icons-vue';
import { createRole, deleteRole, getRoles, updateRole } from '@/api/role';
import { useUserStore } from '@/stores/user';
import { PERMISSION_OPTIONS } from '@/constants/permissions';
import type { RoleInfo } from '@/types/api';

const userStore = useUserStore();

const loading = ref(false);
const tableData = ref<RoleInfo[]>([]);
const total = ref(0);

const queryParams = reactive({
  page: 1,
  page_size: 10,
  keyword: '',
});

const dialogVisible = ref(false);
const dialogTitle = ref('新建角色');
const isEdit = ref(false);
const editingId = ref<number | null>(null);
const formRef = ref<FormInstance>();
const submitLoading = ref(false);

const roleForm = reactive({
  name: '',
  description: '',
  permissions: [] as string[],
});

const formRules: FormRules = {
  name: [
    { required: true, message: '请输入角色名称', trigger: 'blur' },
    { min: 2, max: 50, message: '角色名称长度为 2-50 个字符', trigger: 'blur' },
  ],
  permissions: [{ required: true, message: '请至少选择一个权限', trigger: 'change', type: 'array' }],
};

const canWrite = computed(() => userStore.hasPermission('role:write'));

/** 加载角色列表 */
async function fetchRoles(): Promise<void> {
  loading.value = true;
  try {
    const res = await getRoles(queryParams);
    tableData.value = res.items;
    total.value = res.total;
  } catch (error) {
    console.error('[Fetch Roles Error]', error);
  } finally {
    loading.value = false;
  }
}

function handleSearch(): void {
  queryParams.page = 1;
  fetchRoles();
}

function handlePageChange(page: number): void {
  queryParams.page = page;
  fetchRoles();
}

function resetForm(): void {
  roleForm.name = '';
  roleForm.description = '';
  roleForm.permissions = [];
  editingId.value = null;
  isEdit.value = false;
}

function openCreateDialog(): void {
  resetForm();
  dialogTitle.value = '新建角色';
  dialogVisible.value = true;
}

function openEditDialog(row: RoleInfo): void {
  resetForm();
  isEdit.value = true;
  editingId.value = row.id;
  dialogTitle.value = '编辑角色';
  roleForm.name = row.name;
  roleForm.description = row.description || '';
  roleForm.permissions = [...row.permissions];
  dialogVisible.value = true;
}

/** 选择全部权限时清空其他选项 */
function handlePermissionChange(values: string[]): void {
  if (values.includes('*')) {
    roleForm.permissions = ['*'];
  }
}

function formatPermissions(permissions: string[]): string {
  if (permissions.includes('*')) return '全部权限';
  return permissions
    .map((p) => PERMISSION_OPTIONS.find((opt) => opt.value === p)?.label || p)
    .join('、');
}

async function handleSubmit(): Promise<void> {
  if (!formRef.value) return;

  const valid = await formRef.value.validate().catch(() => false);
  if (!valid) return;

  submitLoading.value = true;
  try {
    if (isEdit.value && editingId.value !== null) {
      await updateRole(editingId.value, {
        name: roleForm.name,
        description: roleForm.description || undefined,
        permissions: roleForm.permissions,
      });
      ElMessage.success('角色更新成功');
    } else {
      await createRole({
        name: roleForm.name,
        description: roleForm.description || undefined,
        permissions: roleForm.permissions,
      });
      ElMessage.success('角色创建成功');
    }
    dialogVisible.value = false;
    fetchRoles();
  } catch (error) {
    console.error('[Submit Role Error]', error);
  } finally {
    submitLoading.value = false;
  }
}

async function handleDelete(row: RoleInfo): Promise<void> {
  try {
    await ElMessageBox.confirm(`确定要删除角色「${row.name}」吗？`, '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    });
    await deleteRole(row.id);
    ElMessage.success('角色删除成功');
    fetchRoles();
  } catch (error) {
    if (error !== 'cancel') {
      console.error('[Delete Role Error]', error);
    }
  }
}

onMounted(() => {
  fetchRoles();
});
</script>

<template>
  <div class="role-management">
    <el-card shadow="never">
      <template #header>
        <div class="card-header flex-between">
          <span class="card-title">角色管理</span>
          <el-button v-if="canWrite" type="primary" :icon="Plus" @click="openCreateDialog">
            新建角色
          </el-button>
        </div>
      </template>

      <div class="search-bar">
        <el-input
          v-model="queryParams.keyword"
          placeholder="搜索角色名称"
          clearable
          class="search-input"
          @keyup.enter="handleSearch"
        >
          <template #append>
            <el-button :icon="Search" @click="handleSearch" />
          </template>
        </el-input>
      </div>

      <el-table v-loading="loading" :data="tableData" stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="角色名称" min-width="120" />
        <el-table-column prop="description" label="描述" min-width="180" show-overflow-tooltip />
        <el-table-column label="权限" min-width="240">
          <template #default="{ row }">
            <el-tooltip :content="formatPermissions(row.permissions)" placement="top">
              <span class="permission-text">{{ formatPermissions(row.permissions) }}</span>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" min-width="160" />
        <el-table-column v-if="canWrite" label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link @click="openEditDialog(row)">编辑</el-button>
            <el-button type="danger" link @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrap">
        <el-pagination
          v-model:current-page="queryParams.page"
          :page-size="queryParams.page_size"
          :total="total"
          layout="total, prev, pager, next"
          @current-change="handlePageChange"
        />
      </div>
    </el-card>

    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="520px"
      destroy-on-close
      @closed="resetForm"
    >
      <el-form ref="formRef" :model="roleForm" :rules="formRules" label-width="80px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="roleForm.name" placeholder="请输入角色名称" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input
            v-model="roleForm.description"
            type="textarea"
            :rows="2"
            placeholder="请输入角色描述"
          />
        </el-form-item>
        <el-form-item label="权限" prop="permissions">
          <el-checkbox-group v-model="roleForm.permissions" @change="handlePermissionChange">
            <el-checkbox
              v-for="opt in PERMISSION_OPTIONS"
              :key="opt.value"
              :value="opt.value"
              :disabled="roleForm.permissions.includes('*') && opt.value !== '*'"
            >
              {{ opt.label }}
            </el-checkbox>
          </el-checkbox-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitLoading" @click="handleSubmit">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style lang="scss" scoped>
.card-header {
  width: 100%;
}

.card-title {
  font-size: 16px;
  font-weight: 500;
  color: $text-primary;
}

.search-bar {
  margin-bottom: 16px;
}

.search-input {
  width: 320px;
}

.permission-text {
  display: inline-block;
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.pagination-wrap {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

:deep(.el-checkbox-group) {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
</style>
