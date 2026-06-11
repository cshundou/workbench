<script setup lang="ts">
import { reactive, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import type { FormInstance, FormRules } from 'element-plus';
import { User, Lock } from '@element-plus/icons-vue';
import { useUserStore } from '@/stores/user';

const route = useRoute();
const router = useRouter();
const userStore = useUserStore();

const loginFormRef = ref<FormInstance>();
const loading = ref(false);

const loginForm = reactive({
  username: '',
  password: '',
});

const loginRules: FormRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 2, max: 50, message: '用户名长度为 2-50 个字符', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, max: 50, message: '密码长度不能少于 6 位', trigger: 'blur' },
  ],
};

async function handleLogin(): Promise<void> {
  if (!loginFormRef.value) return;

  const valid = await loginFormRef.value.validate().catch(() => false);
  if (!valid) return;

  loading.value = true;
  try {
    await userStore.login(loginForm.username, loginForm.password);
    const redirect = (route.query.redirect as string) || '/dashboard';
    router.push(redirect);
  } catch (error) {
    console.error('[Login Error]', error);
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="login-page">
    <div class="login-left">
      <h1 class="brand-title">企业智能协作工作台</h1>
      <p class="brand-subtitle">知识问答 · 任务自动化 · 多智能体协同</p>
    </div>

    <div class="login-right flex-center">
      <div class="login-form-wrap">
        <h2 class="form-title">登录</h2>
        <p class="form-desc">使用您的账号登录系统</p>

        <el-form
          ref="loginFormRef"
          :model="loginForm"
          :rules="loginRules"
          size="large"
          class="login-form"
          @keyup.enter="handleLogin"
        >
          <el-form-item prop="username">
            <el-input
              v-model="loginForm.username"
              placeholder="请输入用户名"
              :prefix-icon="User"
              autocomplete="username"
            />
          </el-form-item>

          <el-form-item prop="password">
            <el-input
              v-model="loginForm.password"
              type="password"
              placeholder="请输入密码"
              :prefix-icon="Lock"
              show-password
              autocomplete="current-password"
            />
          </el-form-item>

          <el-form-item>
            <el-button
              type="primary"
              class="login-btn"
              :loading="loading"
              @click="handleLogin"
            >
              登 录
            </el-button>
          </el-form-item>
        </el-form>

        <p class="login-tip">默认账号：admin / admin123</p>
      </div>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.login-page {
  display: flex;
  width: 100%;
  height: 100vh;
  background: $bg-white;
}

.login-left {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 80px;
  border-right: 1px solid $border-color;
}

.brand-title {
  margin: 0 0 16px;
  font-size: 36px;
  font-weight: 700;
  color: $text-primary;
  line-height: 1.3;
}

.brand-subtitle {
  margin: 0;
  font-size: 16px;
  color: $text-secondary;
  line-height: 1.6;
}

.login-right {
  flex: 0 0 480px;
  padding: 40px;
}

.login-form-wrap {
  width: 100%;
  max-width: 360px;
}

.form-title {
  margin: 0 0 8px;
  font-size: 24px;
  font-weight: 600;
  color: $text-primary;
}

.form-desc {
  margin: 0 0 32px;
  font-size: 14px;
  color: $text-secondary;
}

.login-btn {
  width: 100%;
}

.login-tip {
  margin: 16px 0 0;
  text-align: center;
  font-size: 12px;
  color: $text-secondary;
}

@media (max-width: 768px) {
  .login-page {
    flex-direction: column;
  }

  .login-left {
    flex: none;
    padding: 40px 24px;
    border-right: none;
    border-bottom: 1px solid $border-color;
  }

  .brand-title {
    font-size: 24px;
  }

  .login-right {
    flex: 1;
    width: 100%;
  }
}
</style>
