<script setup lang="ts">
defineProps<{
  title: string;
  description?: string;
}>();
</script>

<template>
  <div class="section-header flex-between">
    <div class="section-header-text">
      <h2 class="section-title">{{ title }}</h2>
      <p v-if="description" class="section-desc">{{ description }}</p>
    </div>
    <div v-if="$slots.actions" class="section-actions">
      <slot name="actions" />
    </div>
  </div>
</template>

<style lang="scss" scoped>
.section-header {
  margin-bottom: 24px;
  align-items: flex-end;
  gap: 16px;
  flex-wrap: wrap;
}

.section-title {
  margin: 0 0 6px;
  font-size: 22px;
  font-weight: 700;
  color: $text-primary;
  letter-spacing: -0.01em;
}

.section-desc {
  margin: 0;
  font-size: 14px;
  color: $text-secondary;
  line-height: 1.6;
}

.section-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}
</style>
