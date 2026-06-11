<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import type { FormInstance, FormRules } from 'element-plus';
import { Download, Plus, Search, Upload } from '@element-plus/icons-vue';
import { createUser, deleteUser, exportUsersCsv, getUsers, importUsersCsv, updateUser } from '@/api/user';
import { getRoles } from '@/api/role';
import { useUserStore } from '@/stores/user';
import SectionHeader from '@/components/layout/SectionHeader.vue';
import type { RoleInfo, UserListItem } from '@/types/api';

const userStore = useUserStore();

const loading = ref(false);
const tableData = ref<UserListItem[]>([]);
const total = ref(0);
const roleOptions = ref<RoleInfo[]>([]);

const queryParams = reactive({
  page: 1,
  page_size: 10,
  keyword: '',
});

const dialogVisible = ref(false);
const dialogTitle = ref('新建用户');
const isEdit = ref(false);
const editingId = ref<number | null>(null);
const formRef = ref<FormInstance>();
const submitLoading = ref(false);

const userForm = reactive({
  username: '',
  email: '',
  password: '',
  role_id: null as number | null,
  status: 1,
});

const formRules: FormRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 2, max: 50, message: '用户名长度为 2-50 个字符', trigger: 'blur' },
  ],
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '请输入有效的邮箱地址', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, max: 50, message: '密码长度不能少于 6 位', trigger: 'blur' },
  ],
  role_id: [{ required: true, message: '请选择角色', trigger: 'change' }],
};

const canWrite = computed(() => userStore.hasPermission('user:write'));
const importLoading = ref(false);
const fileInputRef = ref<HTMLInputElement | null>(null);

/** 加载用户列表 */
async function fetchUsers(): Promise<void> {
  loading.value = true;
  try {
    const res = await getUsers(queryParams);
    tableData.value = res.items;
    total.value = res.total;
  } catch (error) {
    console.error('[Fetch Users Error]', error);
  } finally {
    loading.value = false;
  }
}

/** 加载角色选项 */
async function fetchRoleOptions(): Promise<void> {
  try {
    const res = await getRoles({ page: 1, page_size: 100 });
    roleOptions.value = res.items;
  } catch (error) {
    console.error('[Fetch Roles Error]', error);
  }
}

function handleSearch(): void {
  queryParams.page = 1;
  fetchUsers();
}

function handlePageChange(page: number): void {
  queryParams.page = page;
  fetchUsers();
}

function resetForm(): void {
  userForm.username = '';
  userForm.email = '';
  userForm.password = '';
  userForm.role_id = null;
  userForm.status = 1;
  editingId.value = null;
  isEdit.value = false;
}

function openCreateDialog(): void {
  resetForm();
  dialogTitle.value = '新建用户';
  dialogVisible.value = true;
}

function openEditDialog(row: UserListItem): void {
  resetForm();
  isEdit.value = true;
  editingId.value = row.id;
  dialogTitle.value = '编辑用户';
  userForm.username = row.username;
  userForm.email = row.email;
  userForm.role_id = row.role_id;
  userForm.status = row.status;
  dialogVisible.value = true;
}

async function handleSubmit(): Promise<void> {
  if (!formRef.value) return;

  const valid = await formRef.value.validate().catch(() => false);
  if (!valid) return;

  submitLoading.value = true;
  try {
    if (isEdit.value && editingId.value !== null) {
      const payload: Record<string, unknown> = {
        username: userForm.username,
        email: userForm.email,
        role_id: userForm.role_id,
        status: userForm.status,
      };
      if (userForm.password) {
        payload.password = userForm.password;
      }
      await updateUser(editingId.value, payload);
      ElMessage.success('用户更新成功');
    } else {
      await createUser({
        username: userForm.username,
        email: userForm.email,
        password: userForm.password,
        role_id: userForm.role_id,
      });
      ElMessage.success('用户创建成功');
    }
    dialogVisible.value = false;
    fetchUsers();
  } catch (error) {
    console.error('[Submit User Error]', error);
  } finally {
    submitLoading.value = false;
  }
}

async function handleDelete(row: UserListItem): Promise<void> {
  try {
    await ElMessageBox.confirm(`确定要删除用户「${row.username}」吗？`, '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    });
    await deleteUser(row.id);
    ElMessage.success('用户删除成功');
    fetchUsers();
  } catch (error) {
    if (error !== 'cancel') {
      console.error('[Delete User Error]', error);
    }
  }
}

function formatStatus(status: number): string {
  return status === 1 ? '启用' : '禁用';
}

async function handleExport(): Promise<void> {
  try {
    await exportUsersCsv();
    ElMessage.success('用户导出成功');
  } catch (error) {
    console.error('[Export Users Error]', error);
    ElMessage.error('用户导出失败');
  }
}

function triggerImport(): void {
  fileInputRef.value?.click();
}

async function handleImportFile(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = '';
  if (!file) {
    return;
  }

  importLoading.value = true;
  try {
    const result = await importUsersCsv(file);
    if (result.failed_count > 0) {
      ElMessage.warning(
        `导入完成：成功 ${result.success_count} 条，失败 ${result.failed_count} 条`,
      );
    } else {
      ElMessage.success(`导入成功，共 ${result.success_count} 条`);
    }
    fetchUsers();
  } catch (error) {
    console.error('[Import Users Error]', error);
    ElMessage.error('用户导入失败');
  } finally {
    importLoading.value = false;
  }
}

onMounted(() => {
  fetchUsers();
  fetchRoleOptions();
});
</script>

<template>
  <div class="user-management">
    <SectionHeader
      title="用户管理"
      description="管理系统用户账号、角色分配与状态"
    >
      <template #actions>
        <el-button v-if="canWrite" :icon="Upload" :loading="importLoading" round @click="triggerImport">
          导入 CSV
        </el-button>
        <el-button :icon="Download" round @click="handleExport">导出 CSV</el-button>
        <el-button v-if="canWrite" type="primary" :icon="Plus" round @click="openCreateDialog">
          新建用户
        </el-button>
        <input
          ref="fileInputRef"
          type="file"
          accept=".csv"
          class="hidden-file-input"
          @change="handleImportFile"
        />
      </template>
    </SectionHeader>

    <el-card shadow="never">

      <div class="search-bar">
        <el-input
          v-model="queryParams.keyword"
          placeholder="搜索用户名或邮箱"
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
        <el-table-column prop="username" label="用户名" min-width="120" />
        <el-table-column prop="email" label="邮箱" min-width="180" />
        <el-table-column label="角色" min-width="120">
          <template #default="{ row }">
            {{ row.role?.name || '-' }}
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.status === 1 ? 'success' : 'danger'" size="small">
              {{ formatStatus(row.status) }}
            </el-tag>
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
      width="480px"
      destroy-on-close
      @closed="resetForm"
    >
      <el-form ref="formRef" :model="userForm" :rules="formRules" label-width="80px">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="userForm.username" placeholder="请输入用户名" />
        </el-form-item>
        <el-form-item label="邮箱" prop="email">
          <el-input v-model="userForm.email" placeholder="请输入邮箱" />
        </el-form-item>
        <el-form-item
          label="密码"
          prop="password"
          :rules="
            isEdit
              ? [{ min: 6, max: 50, message: '密码长度不能少于 6 位', trigger: 'blur' }]
              : formRules.password
          "
        >
          <el-input
            v-model="userForm.password"
            type="password"
            show-password
            :placeholder="isEdit ? '留空则不修改密码' : '请输入密码'"
          />
        </el-form-item>
        <el-form-item label="角色" prop="role_id">
          <el-select v-model="userForm.role_id" placeholder="请选择角色" style="width: 100%">
            <el-option
              v-for="role in roleOptions"
              :key="role.id"
              :label="role.name"
              :value="role.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item v-if="isEdit" label="状态">
          <el-radio-group v-model="userForm.status">
            <el-radio :value="1">启用</el-radio>
            <el-radio :value="0">禁用</el-radio>
          </el-radio-group>
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

.pagination-wrap {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

.hidden-file-input {
  display: none;
}
</style>
