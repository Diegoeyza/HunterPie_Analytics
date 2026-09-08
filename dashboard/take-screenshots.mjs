import { chromium } from 'playwright';

const CHROME_PATH = '/opt/hermes/.playwright/chromium_headless_shell-1228/chrome-headless-shell-linux64/chrome-headless-shell';
const BASE = 'http://localhost:3000';
const OUT = '/workspace/HunterPie_Analytics/dashboard';

const tabs = [
  { tab: 'Progress', out: `${OUT}/progress.png` },
  { tab: 'Growth',   out: `${OUT}/growth.png` },
];

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
  // Wait for initial render and API data
  await page.waitForTimeout(4000);

  // Screenshot Progress (the default tab)
  console.log('Screenshotting Progress tab...');
  await page.screenshot({ path: tabs[0].out, fullPage: true });
  console.log(`Saved ${tabs[0].out}`);

  // Click Growth tab
  console.log('Clicking Growth tab...');
  await page.click('button:has-text("Growth")');
  // Wait for Growth data to fetch and charts to render
  await page.waitForTimeout(4000);

  // Screenshot Growth
  console.log('Screenshotting Growth tab...');
  await page.screenshot({ path: tabs[1].out, fullPage: true });
  console.log(`Saved ${tabs[1].out}`);

  await browser.close();
  console.log('Done.');
})();
