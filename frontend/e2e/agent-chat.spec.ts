import { test, expect } from '@playwright/test';

test.describe('智能体模块', () => {
  test('未认证访问智能体列表重定向登录', async ({ page }) => {
    await page.goto('/agents');
    await expect(page).toHaveURL(/\/login/);
  });
});
