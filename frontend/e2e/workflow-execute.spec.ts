import { test, expect } from '@playwright/test';

test.describe('工作流模块', () => {
  test('未认证访问工作流重定向登录', async ({ page }) => {
    await page.goto('/workflows');
    await expect(page).toHaveURL(/\/login/);
  });
});
