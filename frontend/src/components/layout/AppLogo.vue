<script setup lang="ts">
import { useId } from 'vue';

defineProps<{
  /** 是否显示品牌文字 */
  showText?: boolean;
  /** 紧凑模式 */
  compact?: boolean;
  /** 图标尺寸 */
  size?: number;
}>();

const gradientId = useId();
</script>

<template>
  <div class="app-logo" :class="{ compact }">
    <!-- 无背景：波形协同标识，MiniMax 风格 -->
    <svg
      class="logo-mark"
      :width="size || 32"
      :height="size || 32"
      viewBox="0 0 32 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <defs>
        <linearGradient :id="gradientId" x1="4" y1="28" x2="28" y2="4" gradientUnits="userSpaceOnUse">
          <stop stop-color="#FF5C4D" />
          <stop offset="1" stop-color="#FF8A65" />
        </linearGradient>
      </defs>
      <!-- 协同弧线 -->
      <path
        d="M4 22 C9 10, 14 10, 16 16 C18 22, 23 22, 28 10"
        :stroke="`url(#${gradientId})`"
        stroke-width="2.2"
        stroke-linecap="round"
        fill="none"
      />
      <!-- 中心节点 -->
      <circle cx="16" cy="16" r="3" :fill="`url(#${gradientId})`" />
      <!-- 卫星节点 -->
      <circle cx="4" cy="22" r="2" :fill="`url(#${gradientId})`" opacity="0.55" />
      <circle cx="28" cy="10" r="2" :fill="`url(#${gradientId})`" opacity="0.55" />
    </svg>

    <div v-if="showText !== false" class="logo-wordmark">
      <span class="logo-brand">
        <span class="logo-brand-accent">智</span>协
      </span>
      <span v-if="!compact" class="logo-tagline">Workbench</span>
    </div>
  </div>
</template>

<style lang="scss" scoped>
.app-logo {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  user-select: none;
}

.logo-mark {
  flex-shrink: 0;
}

.logo-wordmark {
  display: flex;
  align-items: baseline;
  gap: 7px;
}

.logo-brand {
  font-size: 18px;
  font-weight: 700;
  color: $text-primary;
  letter-spacing: 0.02em;
  line-height: 1;
}

.logo-brand-accent {
  background: $gradient-primary;
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}

.logo-tagline {
  font-size: 11px;
  font-weight: 500;
  color: $text-placeholder;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  line-height: 1;

  @media (max-width: 768px) {
    display: none;
  }
}

.compact .logo-brand {
  font-size: 16px;
}
</style>
