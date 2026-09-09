import { test, expect, type Page } from "@playwright/test";
import fs from "node:fs";
const credentials = process.env.E2E_PASSWORD
  ? {
      username: process.env.E2E_USERNAME ?? "owner",
      password: process.env.E2E_PASSWORD,
    }
  : JSON.parse(fs.readFileSync("../backend/data/demo-login.json", "utf8"));
async function login(page: Page) {
  await page.goto("/");
  await page.getByLabel("Username", { exact: true }).fill(credentials.username);
  await page.getByLabel("Password", { exact: true }).fill(credentials.password);
  await page.getByRole("button", { name: "Open my workspace" }).click();
  await expect(
    page.getByRole("heading", { name: "Portfolio overview", exact: true }),
  ).toBeVisible();
}
test("private workspace full investor journey", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const failed: string[] = [];
  page.on("console", (m) => {
    if (m.type() === "error" && !m.text().includes("401 (Unauthorized)"))
      errors.push(m.text());
  });
  page.on("response", (r) => {
    if (
      r.status() >= 400 &&
      !(r.status() === 401 && r.url().endsWith("/auth/me"))
    )
      failed.push(r.url());
  });
  await login(page);
  await expect(
    page.getByText("TOTAL PORTFOLIO VALUE", { exact: true }),
  ).toBeVisible();
  await expect(page.locator(".recharts-surface").first()).toBeVisible();
  await page.screenshot({
    path: "../artifacts/overview-desktop.png",
    fullPage: true,
  });
  await page.getByRole("link", { name: "Holdings", exact: true }).click();
  await page.getByLabel("Search holdings", { exact: true }).fill("MSFT");
  await expect(page.locator("tbody tr")).toHaveCount(1);
  await page.getByLabel("Search holdings", { exact: true }).fill("");
  await page.getByRole("link", { name: "Watchlist", exact: true }).click();
  await page.getByRole("button", { name: "Add symbol", exact: true }).click();
  await page.getByLabel("Ticker", { exact: true }).fill("AAPL");
  await page
    .getByLabel("Notes", { exact: true })
    .fill("Browser QA investment note");
  await page.getByRole("button", { name: "Save to watchlist" }).click();
  await expect(page.getByText("Browser QA investment note")).toBeVisible();
  await page.reload();
  await expect(page.getByText("Browser QA investment note")).toBeVisible();
  await page.getByRole("button", { name: "Remove AAPL", exact: true }).click();
  await page.getByRole("link", { name: "Research", exact: true }).click();
  await page.getByLabel("Search stocks").fill("Microsoft");
  await page.locator(".search-dropdown").getByRole("button").first().click();
  await expect(
    page.getByRole("heading", { name: "Microsoft", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Annual revenue", exact: true }),
  ).toBeVisible();
  for (const researchTab of ["Earnings", "News", "Analysts", "Dividends"]) {
    await page.getByRole("button", { name: researchTab, exact: true }).click();
    await expect(page.locator("main")).not.toContainText(
      "Something went wrong",
    );
  }
  await page.getByRole("button", { name: "My thesis", exact: true }).click();
  await page
    .getByLabel("Thesis", { exact: true })
    .fill("A durable enterprise software franchise.");
  await page.getByRole("button", { name: "Save thesis", exact: true }).click();
  await page.reload();
  await page.getByRole("button", { name: "My thesis", exact: true }).click();
  await expect(page.getByLabel("Thesis", { exact: true })).toHaveValue(
    "A durable enterprise software franchise.",
  );
  await page.getByRole("link", { name: "Performance", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Performance", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Returns", exact: true }).click();
  await expect(page.locator(".recharts-surface").first()).toBeVisible();
  await page
    .getByRole("button", { name: "Verify a cash-flow interval" })
    .click();
  await page
    .getByLabel("Verified net external flow ($)", { exact: true })
    .fill("0");
  await page
    .getByRole("button", { name: "Save verified flow", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.getByRole("link", { name: "Analytics", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Portfolio analytics" }),
  ).toBeVisible();
  await expect(page.locator(".correlation-table")).toBeVisible();
  await page.getByRole("link", { name: "Calendar", exact: true }).click();
  await page.getByRole("button", { name: "Add event", exact: true }).click();
  await page.getByLabel("Event title").fill("QA portfolio review");
  await page.getByRole("button", { name: "Save event", exact: true }).click();
  await page.getByRole("button", { name: "Agenda", exact: true }).click();
  await expect(
    page.getByText("QA portfolio review", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Delete QA portfolio review", exact: true })
    .click();
  await page.getByRole("link", { name: /^Lab/ }).click();
  await page.getByRole("button", { name: "Run scenario", exact: true }).click();
  await expect(
    page.getByText("ESTIMATED PORTFOLIO VALUE", { exact: true }),
  ).toBeVisible();
  await page
    .getByLabel("Scenario name", { exact: true })
    .fill("QA stress scenario");
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "QA stress scenario", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Delete QA stress scenario", exact: true })
    .click();
  await page.getByRole("button", { name: "Simulator", exact: true }).click();
  await page
    .getByRole("button", { name: "Project growth", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Year by year" }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Journal", exact: true }).click();
  await page.getByRole("button", { name: "New entry", exact: true }).click();
  await page.getByLabel("Title", { exact: true }).fill("QA decision");
  await page
    .getByLabel("Your reasoning")
    .fill("Check the evidence and preserve the record.");
  await page.getByRole("button", { name: "Save entry", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "QA decision" }),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "QA decision" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Delete QA decision", exact: true })
    .click();
  await page.getByRole("link", { name: "Transactions", exact: true }).click();
  await page.getByRole("button", { name: "Add record", exact: true }).click();
  await page.getByLabel("Amount (USD)", { exact: true }).fill("12.34");
  await page.getByLabel("Notes", { exact: true }).fill("QA ledger persistence");
  await page
    .getByRole("button", { name: "Save ledger record", exact: true })
    .click();
  await page.reload();
  await page.getByLabel("Search transactions").fill("QA ledger persistence");
  const record = page
    .locator("tbody tr")
    .filter({ hasText: "QA ledger persistence" });
  await expect(record).toBeVisible();
  await record.getByRole("button").click();
  await expect(record).toHaveCount(0);
  for (const [link, title] of [
    ["Transactions", "Transactions"],
    ["Income", "Income & dividends"],
    ["Replay", "Portfolio replay"],
    ["Settings", "Settings"],
    ["Security", "Security"],
  ]) {
    await page.getByRole("link", { name: link, exact: true }).click();
    await expect(
      page.getByRole("heading", { name: title, exact: true }),
    ).toBeVisible();
  }
  await page.getByRole("link", { name: "Data Sync", exact: true }).click();
  await page.getByRole("button", { name: "Sync now", exact: true }).click();
  await expect(page.getByRole("status")).toContainText("Demo mode");
  await page.keyboard.press("Control+k");
  await expect(page.getByRole("dialog")).toBeVisible();
  await page.getByLabel("Command search").fill("Holdings");
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Holdings", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Holdings", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Welcome back." }),
  ).toBeVisible();
  await login(page);
  expect(errors).toEqual([]);
  expect(failed).toEqual([]);
});
test("390px phone navigation and overflow across every page", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await login(page);
  await page.screenshot({
    path: "../artifacts/overview-mobile.png",
    fullPage: true,
  });
  for (const [link, title] of [
    ["Holdings", "Holdings"],
    ["Watchlist", "Watchlist"],
    ["Performance", "Performance"],
    ["Analytics", "Portfolio analytics"],
    ["Research", "Research"],
    ["Transactions", "Transactions"],
    ["Settings", "Settings"],
    ["Calendar", "Calendar"],
    ["Journal", "Investment journal"],
    ["Income", "Income & dividends"],
    ["Replay", "Portfolio replay"],
    ["Data Sync", "Data sync"],
    ["Security", "Security"],
  ]) {
    await page
      .getByRole("button", { name: "Open navigation", exact: true })
      .click();
    await page.getByRole("link", { name: link, exact: true }).click();
    await expect(
      page.getByRole("heading", { name: title, exact: true }),
    ).toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth + 1,
      ),
      `${link} overflow`,
    ).toBeTruthy();
  }
  await page
    .getByRole("button", { name: "Open navigation", exact: true })
    .click();
  await page.getByRole("link", { name: /^Lab/ }).click();
  await page.getByRole("button", { name: "Run scenario", exact: true }).click();
  await expect(
    page.getByText("ESTIMATED PORTFOLIO VALUE", { exact: true }),
  ).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth + 1,
    ),
  ).toBeTruthy();
});
