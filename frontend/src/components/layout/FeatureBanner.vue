<script setup lang="ts">
import type { Component } from 'vue';

export interface FeatureSlide {
  title: string;
  features: {
    icon?: Component;
    title: string;
    subtitle: string;
  }[];
}

defineProps<{
  slides: FeatureSlide[];
}>();
</script>

<template>
  <section class="feature-banner section-block">
    <el-carousel
      v-if="slides.length > 0"
      :interval="5000"
      :loop="slides.length > 1"
      arrow="hover"
      indicator-position="outside"
      height="280px"
      class="feature-carousel"
    >
      <el-carousel-item v-for="(slide, index) in slides" :key="index">
        <div class="banner-slide gradient-banner">
          <h3 class="banner-title">{{ slide.title }}</h3>
          <div class="feature-cards">
            <div v-for="(feature, idx) in slide.features" :key="idx" class="feature-card">
              <div v-if="feature.icon" class="feature-icon">
                <el-icon :size="18"><component :is="feature.icon" /></el-icon>
              </div>
              <div class="feature-text">
                <p class="feature-title">{{ feature.title }}</p>
                <p class="feature-subtitle">{{ feature.subtitle }}</p>
              </div>
            </div>
          </div>
        </div>
      </el-carousel-item>
    </el-carousel>
  </section>
</template>

<style lang="scss" scoped>
.feature-banner {
  position: relative;
}

.feature-carousel {
  border-radius: $border-radius-lg;
  overflow: hidden;

  :deep(.el-carousel__container) {
    height: 280px;
  }

  :deep(.el-carousel__arrow) {
    width: 36px;
    height: 36px;
    background: $bg-white;
    color: $text-regular;
    box-shadow: $shadow-soft;
    border: none;

    &:hover {
      background: $bg-white;
      color: $primary-color;
    }
  }

  :deep(.el-carousel__indicators--outside) {
    margin-top: 16px;

    .el-carousel__button {
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: $border-color;
      opacity: 1;
      transition: all 0.35s cubic-bezier(0.22, 1, 0.36, 1);
    }

    .is-active .el-carousel__button {
      width: 24px;
      border-radius: $border-radius-pill;
      background: $primary-color;
    }
  }
}

.banner-slide {
  padding: 40px 48px;
  min-height: 200px;
  box-sizing: border-box;

  @media (max-width: 768px) {
    padding: 28px 24px;
  }
}

.banner-title {
  margin: 0 0 24px;
  font-size: 20px;
  font-weight: 700;
  color: #fff;
}

.feature-cards {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}

.feature-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px 20px;
  background: $bg-white;
  border-radius: $border-radius-pill;
  box-shadow: $shadow-card;
  min-width: 200px;
  flex: 1;
  max-width: 280px;

  @media (max-width: 768px) {
    min-width: 100%;
    max-width: 100%;
  }
}

.feature-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  background: rgba($primary-color, 0.1);
  color: $primary-color;
  border-radius: 50%;
  flex-shrink: 0;
}

.feature-title {
  margin: 0 0 2px;
  font-size: 14px;
  font-weight: 600;
  color: $text-primary;
}

.feature-subtitle {
  margin: 0;
  font-size: 12px;
  color: $text-secondary;
}
</style>
