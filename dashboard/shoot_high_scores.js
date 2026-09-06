const { chromium } = require("playwright-core");

const EXECUTABLE = "/opt/hermes/.playwright/chromium_headless_shell-1228/chrome-headless-shell-linux64/chrome-headless-shell";
const OUT = "/workspace/HunterPie_Analytics/dashboard/high_scores.png";
const URL = "http://localhost:3000";

(async () => {
  const browser = await chromium.launch({ executablePath: EXECUTABLE });
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } });
  await page.goto(URL, { waitUntil: "networkidle", timeout: 60000 });

  // Click High Scores tab
  const tabHandle = page.locator('nav.tabs button:has-text("High Scores")').first();
  await tabHandle.waitFor({ state: "visible", timeout: 15000 });
  await tabHandle.click();

  // Wait for table rows to appear in High Scores view
  try {
    await page.waitForSelector("table.grid tbody tr", { timeout: 10000 });
  } catch (e) {
    console.warn("Timeout waiting for table.grid tbody tr:", e.message);
  }

  await page.waitForTimeout(2000);

  const rowCount = await page.evaluate(() =>
    document.querySelectorAll("table.grid tbody tr").length
  );
  console.log("Rendered table rows:", rowCount);

  await page.screenshot({ path: OUT, fullPage: true });
  console.log("Saved:", OUT);
  await browser.close();
})().catch((e) => {
  console.error("ERROR:", e);
  process.exit(1);
});
