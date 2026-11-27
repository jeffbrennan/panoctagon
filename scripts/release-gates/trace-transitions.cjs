const { chromium } = require("../../frontend/node_modules/playwright");
(async () => {
  let b = await chromium.launch();
  let p = await b.newPage({ viewport: { width: 1440, height: 900 } });
  let t = 0;
  let rows = [];
  p.on("requestfinished", (r) => {
    if (t)
      rows.push([Math.round(performance.now() - t), new URL(r.url()).pathname]);
  });
  await p.goto("http://127.0.0.1:18751");
  await p.getByRole("heading", { name: "No upcoming events" }).waitFor();
  t = performance.now();
  await p.getByRole("link", { name: "Fighters", exact: true }).click();
  await p.getByRole("heading", { name: "Max Holloway" }).waitFor();
  console.log("profile", Math.round(performance.now() - t));
  await p.locator(".view:visible .chart").first().scrollIntoViewIfNeeded();
  await p.locator(".view:visible canvas").first().waitFor();
  console.log("canvas", Math.round(performance.now() - t), "requests", rows);
  rows = [];
  t = performance.now();
  await p.getByRole("link", { name: "Roster", exact: true }).click();
  await p.getByText("171 fighters", { exact: true }).waitFor();
  console.log("roster data", Math.round(performance.now() - t));
  await p.locator(".view:visible .chart").first().scrollIntoViewIfNeeded();
  await p.locator(".view:visible canvas").first().waitFor();
  console.log("canvas", Math.round(performance.now() - t), "requests", rows);
  await b.close();
})().catch(console.error);
