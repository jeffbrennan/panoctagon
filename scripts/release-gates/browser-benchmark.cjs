const { chromium } = require("../../frontend/node_modules/playwright");
const fs = require("fs");
const samples = Number(process.env.GATE_SAMPLES || 20);
const output = process.env.GATE_OUTPUT || ".scratch/release-gates/bench.json";
(async () => {
  const b = await chromium.launch({ headless: true });
  let results = [];
  for (const [app, url] of [
    ["dash", "http://127.0.0.1:18750"],
    ["svelte", "http://127.0.0.1:18751"],
  ])
    for (let n = 0; n < samples; n++) {
      let context = await b.newContext({
        viewport: { width: 1440, height: 900 },
      });
      let page = await context.newPage();
      let errors = [];
      let bytes = 0;
      let requests = [];
      page.on("requestfinished", (r) => {
        requests.push(
          r
            .sizes()
            .then((s) => (bytes += s.responseBodySize))
            .catch(() => {}),
        );
      });
      page.on("pageerror", (e) => errors.push(e.message));
      let t = performance.now();
      await page.goto(url, { waitUntil: "domcontentloaded", timeout: 120000 });
      if (app === "dash")
        await page
          .getByText("No upcoming fights found.")
          .waitFor({ timeout: 120000 });
      else
        await page
          .getByRole("heading", { name: "No upcoming events" })
          .waitFor({ timeout: 120000 });
      let upcoming = performance.now() - t;
      t = performance.now();
      await (
        app === "dash"
          ? page.getByRole("tab", { name: "Fighters", exact: true })
          : page.getByRole("link", { name: "Fighters", exact: true })
      ).click();
      if (app === "dash")
        await page
          .locator(".js-plotly-plot:visible")
          .first()
          .waitFor({ timeout: 120000 });
      else {
        await page
          .getByRole("heading", { name: "Max Holloway" })
          .waitFor({ timeout: 120000 });
        await page.locator(".chart").first().scrollIntoViewIfNeeded();
        await page
          .locator("canvas:visible")
          .first()
          .waitFor({ timeout: 120000 });
      }
      let fighter = performance.now() - t;
      t = performance.now();
      await (
        app === "dash"
          ? page.getByRole("tab", { name: "Roster", exact: true })
          : page.getByRole("link", { name: "Roster", exact: true })
      ).click();
      if (app === "dash")
        await page
          .locator("#fighter-clustering .point")
          .first()
          .waitFor({ timeout: 120000 });
      else {
        await page
          .getByText("171 fighters", { exact: true })
          .waitFor({ timeout: 120000 });
        await page.locator(".chart:visible").first().scrollIntoViewIfNeeded();
        await page
          .locator("canvas:visible")
          .first()
          .waitFor({ timeout: 120000 });
      }
      let roster = performance.now() - t;
      await Promise.all(requests);
      results.push({ app, n, upcoming, fighter, roster, bytes, errors });
      console.log(JSON.stringify(results.at(-1)));
      await context.close();
    }
  fs.writeFileSync(output, JSON.stringify(results, null, 2));
  await b.close();
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
