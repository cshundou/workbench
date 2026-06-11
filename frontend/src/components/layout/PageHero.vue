<script setup lang="ts">
interface HeroAction {
  label: string;
  type?: 'primary' | 'default';
  accent?: boolean;
  onClick?: () => void;
}

defineProps<{
  title: string;
  subtitle?: string;
  actions?: HeroAction[];
}>();
</script>

<template>
  <section class="page-hero">
    <h1 class="hero-title">{{ title }}</h1>
    <p v-if="subtitle" class="hero-subtitle">{{ subtitle }}</p>
    <div v-if="actions && actions.length > 0" class="hero-actions">
      <el-button
        v-for="(action, index) in actions"
        :key="index"
        :type="action.type || (index === 0 ? 'primary' : 'default')"
        :class="{ 'pill-btn--accent': action.accent }"
        size="large"
        round
        @click="action.onClick?.()"
      >
        {{ action.label }}
      </el-button>
    </div>
    <slot />
  </section>
</template>

<style lang="scss" scoped>
.page-hero {
  text-align: center;
  padding: 48px 0 32px;
}

.hero-title {
  margin: 0 0 12px;
  font-size: 36px;
  font-weight: 700;
  color: $text-primary;
  letter-spacing: -0.02em;
  line-height: 1.2;

  @media (max-width: 768px) {
    font-size: 28px;
  }
}

.hero-subtitle {
  margin: 0 0 28px;
  font-size: 16px;
  color: $text-secondary;
  line-height: 1.6;
}

.hero-actions {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  flex-wrap: wrap;

  :deep(.el-button) {
    min-width: 140px;
    padding: 12px 28px;
    font-size: 15px;
  }

  :deep(.el-button--primary) {
    background-color: $primary-color !important;
    border-color: $primary-color !important;
    color: #ffffff !important;
  }

  :deep(.el-button--default) {
    background-color: $bg-color !important;
    color: $text-primary !important;
  }
}
</style>
