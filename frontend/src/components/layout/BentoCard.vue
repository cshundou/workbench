<script setup lang="ts">
import type { Component } from 'vue';

defineProps<{
  title: string;
  description?: string;
  value?: string;
  unit?: string;
  icon?: Component;
  badge?: string;
  clickable?: boolean;
}>();

const emit = defineEmits<{
  click: [];
}>();

function handleClick(): void {
  emit('click');
}
</script>

<template>
  <div
    class="bento-card"
    :class="{ 'is-clickable': clickable }"
    @click="clickable ? handleClick() : undefined"
  >
    <span v-if="badge" class="bento-badge">{{ badge }}</span>

    <div class="bento-body">
      <div class="bento-info">
        <p class="bento-title">{{ title }}</p>
        <p v-if="value !== undefined" class="bento-value">
          {{ value }}
          <span v-if="unit" class="bento-unit">{{ unit }}</span>
        </p>
        <p v-if="description" class="bento-desc">{{ description }}</p>
      </div>
      <div v-if="icon" class="bento-icon">
        <el-icon :size="28"><component :is="icon" /></el-icon>
      </div>
    </div>

    <slot />
  </div>
</template>

<style lang="scss" scoped>
.bento-card {
  position: relative;
  padding: 24px;
  background: $bg-white;
  border: none;
  border-radius: $border-radius-lg;
  box-shadow: $shadow-card;
  transition: box-shadow 0.2s ease, transform 0.2s ease;

  &.is-clickable {
    cursor: pointer;

    &:hover {
      box-shadow: $shadow-card-hover;
      transform: translateY(-2px);
    }
  }
}

.bento-badge {
  position: absolute;
  top: 16px;
  right: 16px;
  padding: 2px 10px;
  background: $primary-color;
  color: #fff;
  font-size: 11px;
  font-weight: 600;
  border-radius: $border-radius-pill;
}

.bento-body {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.bento-title {
  margin: 0 0 8px;
  font-size: 14px;
  font-weight: 600;
  color: $text-secondary;
}

.bento-value {
  margin: 0 0 6px;
  font-size: 28px;
  font-weight: 700;
  color: $text-primary;
  line-height: 1.2;
}

.bento-unit {
  font-size: 14px;
  font-weight: 400;
  color: $text-secondary;
  margin-left: 2px;
}

.bento-desc {
  margin: 0;
  font-size: 13px;
  color: $text-secondary;
  line-height: 1.5;
}

.bento-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 52px;
  height: 52px;
  background: rgba($primary-color, 0.08);
  color: $primary-color;
  border-radius: $border-radius-md;
  flex-shrink: 0;
}
</style>
