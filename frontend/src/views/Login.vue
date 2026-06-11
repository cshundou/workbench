<script setup lang="ts">
import { reactive, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import type { FormInstance, FormRules } from 'element-plus';
import { User, Lock } from '@element-plus/icons-vue';
import { useUserStore } from '@/stores/user';
import AppLogo from '@/components/layout/AppLogo.vue';

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
    <!-- 顶部 Logo 条 -->
    <header class="login-header">
      <div class="header-inner">
        <AppLogo />
      </div>
    </header>

    <!-- 居中 Hero + 登录表单 -->
    <main class="login-main flex-center">
      <div class="login-content">
        <div class="hero-section">
          <div class="hero-logo-wrap">
            <AppLogo :size="48" :show-text="false" />
          </div>
          <h1 class="hero-title">企业智能协作工作台</h1>
          <p class="hero-subtitle">知识问答 · 任务自动化 · 多智能体协同</p>
        </div>

        <div class="login-form-card">
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
                round
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
    </main>
  </div>
</template>

<style lang="scss" scoped>
.login-page {
  min-height: 100vh;
  background: $bg-white;
  display: flex;
  flex-direction: column;
}

.login-header {
  height: $header-height;
  box-shadow: $shadow-soft;
}

.header-inner {
  display: flex;
  align-items: center;
  height: 100%;
  max-width: $content-max-width;
  margin: 0 auto;
  padding: 0 $content-padding;
}

.login-main {
  flex: 1;
  padding: 48px 24px;
}

.login-content {
  width: 100%;
  max-width: 420px;
}

.hero-section {
  text-align: center;
  margin-bottom: 40px;
}

.hero-logo-wrap {
  display: flex;
  justify-content: center;
  margin-bottom: 20px;
}

.hero-title {
  margin: 0 0 12px;
  font-size: 32px;
  font-weight: 700;
  color: $text-primary;
  letter-spacing: -0.02em;
  line-height: 1.2;
}

.hero-subtitle {
  margin: 0;
  font-size: 15px;
  color: $text-secondary;
  line-height: 1.6;
}

.login-form-card {
  padding: 32px;
  background: $bg-white;
  border-radius: $border-radius-lg;
  box-shadow: $shadow-card;
}

.form-title {
  margin: 0 0 8px;
  font-size: 22px;
  font-weight: 700;
  color: $text-primary;
}

.form-desc {
  margin: 0 0 28px;
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
  .hero-title {
    font-size: 26px;
  }

  .login-form-card {
    padding: 24px;
  }
}
</style>
