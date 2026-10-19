import { test, expect } from "@playwright/test";
test("adopt, care, remember, correct, forget and persist across login", async ({
  page,
}, testInfo) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const username = `human_${testInfo.project.name}_${Date.now()}`;
  await page.goto("/");
  await page.getByRole("button", { name: "创建账号", exact: true }).click();
  await page.getByLabel("用户名").fill(username);
  await page.getByLabel("密码", { exact: true }).fill("a-strong-test-password");
  await page.getByRole("button", { name: "开启陪伴", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "这次相遇，会有一点不同。" }),
  ).toBeVisible();
  await page.getByLabel("给小猫取个名字").fill("奶糖");
  await page.getByRole("button", { name: "带它回家", exact: true }).click();
  await expect(page.getByRole("heading", { name: "奶糖的小窝" })).toBeVisible();
  await page.getByRole("button", { name: "喂点好吃的" }).click();
  await expect(page.locator(".cat-bubble")).toContainText("小鱼干");
  await page.getByRole("button", { name: "成长日记", exact: true }).click();
  await expect(
    page.getByRole("heading", {
      name: "奶糖吃完小鱼干，心满意足地舔了舔爪子。",
    }),
  ).toBeVisible();
  await page.getByRole("button", { name: "共同记忆", exact: true }).click();
  await page.getByRole("button", { name: "留下一条记忆" }).click();
  await page.getByLabel("想让小猫记住什么？").fill("我喜欢用逗猫棒陪奶糖玩");
  await page.getByRole("button", { name: "好好记住", exact: true }).click();
  await expect(page.locator(".memory-card>p")).toHaveText(
    "我喜欢用逗猫棒陪奶糖玩",
  );
  await page.getByLabel("搜索记忆").fill("喜欢用什么玩具");
  await page.getByRole("button", { name: "寻找记忆" }).click();
  await expect(page.locator(".memory-card>p")).toHaveText(
    "我喜欢用逗猫棒陪奶糖玩",
  );
  await page.getByRole("button", { name: "清除搜索" }).click();
  await page
    .getByRole("button", { name: "纠正：我喜欢用逗猫棒陪奶糖玩", exact: true })
    .click();
  await page
    .getByLabel("想让小猫记住什么？")
    .fill("我现在更喜欢用小球陪奶糖玩");
  await page.getByRole("button", { name: "好好记住", exact: true }).click();
  await expect(page.locator(".memory-card>p")).toHaveText(
    "我现在更喜欢用小球陪奶糖玩",
  );
  await page
    .getByRole("button", {
      name: "遗忘：我现在更喜欢用小球陪奶糖玩",
      exact: true,
    })
    .click();
  await page.getByRole("button", { name: "遗忘这条记忆", exact: true }).click();
  await expect(page.locator(".memory-card")).toHaveCount(0);
  await page.getByRole("button", { name: "小窝设置", exact: true }).click();
  await page.getByRole("button", { name: "退出登录", exact: true }).click();
  await page.getByLabel("用户名").fill(username);
  await page.getByLabel("密码", { exact: true }).fill("a-strong-test-password");
  await page.getByRole("button", { name: "回到小窝", exact: true }).click();
  await expect(page.getByRole("heading", { name: "奶糖的小窝" })).toBeVisible();
  await expect(page.locator(".stat strong").first()).toContainText("99");
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  expect(errors).toEqual([]);
  await page.screenshot({
    path: `../.local/${testInfo.project.name}-home.png`,
    fullPage: true,
  });
});
