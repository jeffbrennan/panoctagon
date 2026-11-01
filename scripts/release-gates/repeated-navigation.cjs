const { chromium } = require("../../frontend/node_modules/playwright");
const fs = require("fs");
(async () => {
  const b = await chromium.launch({ headless: true });
  const p = await b.newPage({ viewport: { width: 1440, height: 900 } });
  let errors = [];
  let failed = [];
  p.on("pageerror", (e) => errors.push(e.message));
  p.on("response", (r) => {
    if (r.status() >= 400) failed.push([r.status(), r.url()]);
  });
  await p.goto("http://127.0.0.1:18751");
  let times = [],
    counts = [];
  for (let n = 0; n < 20; n++) {
    let t = performance.now();
    for (const name of ["Fighters", "Network", "Roster", "Upcoming"]) {
      await p.getByRole("link", { name, exact: true }).click();
      if (name === "Fighters" || name === "Network" || name === "Roster") {
        const chart = p.locator(".view:visible .chart").first();
        await chart.scrollIntoViewIfNeeded();
        await chart.locator("canvas").first().waitFor();
      }
    }
    times.push(performance.now() - t);
    counts.push(await p.locator("canvas").count());
  }
  let result = { times, counts, errors, failed };
  fs.writeFileSync(
    ".scratch/release-gates/revisit.json",
    JSON.stringify(result, null, 2),
  );
  console.log(JSON.stringify(result));
  await b.close();
})().catch((e) => {
  console.error(e);
  process.exit(1);
});
