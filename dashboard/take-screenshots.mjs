import { chromium } from 'playwright';

const CHROME_PATH = '/opt/hermes/.playwright/chromium_headless_shell-1228/chrome-headless-shell-linux64/chrome-headless-shell';
const BASE = 'http://localhost:3000';
const OUT = '/workspace/HunterPie_Analytics/dashboard';

const GROWTH_OVERVIEW_OUT = `${OUT}/growth_updated.png`;
const GROWTH_FILTERED_OUT = `${OUT}/growth_updated_filtered.png`;

(async () => {
  const browser = await chromium.launch({
    executablePath: CHROME_PATH,
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
  });

  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await context.newPage();

  // Load the dashboard (defaults to Progress tab)
  console.log(`Loading ${BASE} ...`);
  await page.goto(BASE, { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(4000);

  // --- Screenshot 1: Growth overview (top hunters list) ---
  console.log('Clicking Growth tab...');
  await page.click('button:has-text("Growth")');
  await page.waitForTimeout(4000);

  console.log('Screenshotting Growth overview (top hunters)...');
  await page.screenshot({ path: GROWTH_OVERVIEW_OUT, fullPage: true });
  console.log(`Saved ${GROWTH_OVERVIEW_OUT}`);

  // --- Screenshot 2: Growth with a specific hunter selected + weapon filter ---
  // Click the first hunter card to drill into their growth detail
  const hunterCards = page.locator('[style*="cursor: pointer"]');
  const count = await hunterCards.count();
  if (count === 0) {
    console.log('No hunter cards found on Growth page — skipping filtered screenshot.');
    await browser.close();
    console.log('Done.');
    return;
  }

  console.log(`Clicking first hunter card (${count} cards found)...`);
  await hunterCards.first().click();
  // Wait for the detail view to fetch and render
  await page.waitForTimeout(4000);

  // Now apply a weapon filter using the GrowthView's SearchSelect ("Weapon" label).
  // The GrowthView filter is inside <main>, the ScopeBar filter is inside .scopebar.
  // Target the one inside main by getting the <label> that contains "Weapon" text inside main.
  const weaponLabel = page.locator('main label:has-text("Weapon")');
  if (await weaponLabel.count() > 0) {
    const weaponInput = weaponLabel.locator('input[role="combobox"]');
    console.log('Opening weapon filter dropdown...');
    await weaponInput.click();
    await page.waitForTimeout(500);

    // Select the first non-"All" weapon option from the dropdown list
    const firstOption = page.locator('main .combo-list li').nth(1);
    if (await firstOption.count() > 0) {
      const optionText = await firstOption.textContent();
      console.log(`Selecting weapon filter: "${optionText}"...`);
      await firstOption.click();
      await page.waitForTimeout(4000);
    }
  }

  console.log('Screenshotting Growth with hunter + weapon filter...');
  await page.screenshot({ path: GROWTH_FILTERED_OUT, fullPage: true });
  console.log(`Saved ${GROWTH_FILTERED_OUT}`);

  await browser.close();
  console.log('Done.');
})();
