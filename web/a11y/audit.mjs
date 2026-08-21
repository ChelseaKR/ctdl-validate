// The accessibility gate for the playground. Merge-blocking; no advisory mode.
//
// Why this exists rather than a one-line `npx pa11y`:
//
// 1. **It audits the page in the state a visitor reaches.** `?a11y-static`
//    renders one finding of each severity through the same code path a real
//    run uses, so the four severity colours and the whole dl/dt/dd report
//    structure are in the DOM. Auditing the empty page passed cleanly and
//    missed a reflow failure that only the rendered report has.
// 2. **It audits both colour schemes.** The page ships a light and a dark
//    palette behind `prefers-color-scheme`. A scanner that only sees one has
//    checked half the contrast decisions.
// 3. **It checks reflow, which no static scanner does.** SC 1.4.10 is a
//    viewport property, not a markup property.
// 4. **It runs current axe.** pa11y 8 bundles axe-core 4.8, which reports a
//    colour-contrast violation on this page's `<textarea>` that axe-core 4.13
//    does not, and that the computed styles disprove outright: the element
//    renders #111827 on #ffffff, about 16:1. Pinning axe here keeps the gate
//    from being trained on a false positive.
//
// Usage: node web/a11y/audit.mjs <url>
// Requires puppeteer-core and axe-core, and a Chrome at $CHROME_PATH.

import puppeteer from "puppeteer-core";
import axeCore from "axe-core";

const URL_UNDER_TEST = process.argv[2];
if (!URL_UNDER_TEST) {
  console.error("usage: node web/a11y/audit.mjs <url>");
  process.exit(2);
}

// ACCESSIBILITY-STANDARD A11Y-01: zero violations of these impacts.
const BLOCKING_IMPACTS = ["critical", "serious", "moderate"];
// The three WCAG tags are the standard's floor. `best-practice` adds the rules
// axe keeps outside WCAG because no success criterion names them outright:
// heading levels that do not skip (`heading-order`), exactly one `<main>` and
// one `<h1>`, every region inside a landmark, no duplicate ids. The page
// cleared all of them when first measured on 2026-08-21 (39 rules passed in
// each colour scheme, up from 25), so they are held rather than watched.
const TAGS = ["wcag2a", "wcag2aa", "wcag22aa", "best-practice"];
// A11Y-09 / SC 1.4.10: no horizontal scroll at 320 CSS px.
const REFLOW_VIEWPORT = { width: 320, height: 256 };
const SCHEMES = ["light", "dark"];

const executablePath =
  process.env.CHROME_PATH ||
  process.env.PUPPETEER_EXECUTABLE_PATH ||
  "/usr/bin/google-chrome";

const browser = await puppeteer.launch({
  executablePath,
  headless: "new",
  args: ["--no-sandbox", "--disable-dev-shm-usage"],
});

let failures = 0;

function fail(message) {
  failures += 1;
  console.log(`::error title=Accessibility::${message}`);
}

// The severities `?a11y-static` is supposed to put on the page. Checked
// before anything is scanned, because this gate's whole reason for existing is
// that auditing the page without its report passes and proves nothing. It was
// worse than that: pointed at a 404 error page, this script reported "5
// passed, 0 violations" and exited 0. The workflow's own serve step catches a
// dead server, but a JS error that stops `?a11y-static` short would leave a
// live page with an empty report and a green gate, which is the exact failure
// this file was written to close.
const EXPECTED_SEVERITIES = ["ERROR", "WARNING", "INFO", "UNVERIFIABLE"];

async function requireTheReportRendered(page, scheme) {
  if (!URL_UNDER_TEST.includes("a11y-static")) return;
  const rendered = await page.evaluate(() =>
    [...document.querySelectorAll(".finding .sev")].map((el) => el.textContent.trim()),
  );
  const missing = EXPECTED_SEVERITIES.filter((s) => !rendered.includes(s));
  if (missing.length) {
    fail(
      `${scheme}: the static report did not render. Expected a finding at each of ` +
        `${EXPECTED_SEVERITIES.join(", ")}; missing ${missing.join(", ")}. ` +
        `Scanning the page without its report is not an audit.`,
    );
  }
}

for (const scheme of SCHEMES) {
  const page = await browser.newPage();
  await page.emulateMediaFeatures([{ name: "prefers-color-scheme", value: scheme }]);
  await page.goto(URL_UNDER_TEST, { waitUntil: "networkidle0" });
  await requireTheReportRendered(page, scheme);
  await page.evaluate(axeCore.source);
  const results = await page.evaluate(
    async (tags) => await window.axe.run(document, { runOnly: { type: "tag", values: tags } }),
    TAGS,
  );

  const blocking = results.violations.filter((v) => BLOCKING_IMPACTS.includes(v.impact));
  console.log(
    `${scheme}: axe-core ${results.testEngine.version}, ` +
      `${results.passes.length} passed, ${results.violations.length} violations ` +
      `(${blocking.length} blocking), ${results.incomplete.length} incomplete`,
  );
  for (const violation of blocking) {
    fail(`${scheme}: ${violation.id} (${violation.impact}) - ${violation.help}`);
    for (const node of violation.nodes.slice(0, 5)) {
      console.log(`    ${node.target.join(" ")}`);
    }
  }
  // Incomplete results are the ones axe could not decide. They are reported
  // and do not block, because a scanner's uncertainty is a prompt for the
  // human review gate, not a defect. Silence would be the defect.
  for (const item of results.incomplete) {
    console.log(`::notice title=axe could not decide::${scheme}: ${item.id} - ${item.help}`);
  }

  await page.setViewport(REFLOW_VIEWPORT);
  const reflow = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
    culprits: [...document.querySelectorAll("*")]
      .filter((el) => el.scrollWidth > document.documentElement.clientWidth + 1)
      .map((el) => `${el.tagName.toLowerCase()}${el.id ? "#" + el.id : ""} (${el.scrollWidth}px)`)
      .slice(0, 10),
  }));
  if (reflow.scrollWidth > reflow.clientWidth) {
    fail(
      `${scheme}: content is ${reflow.scrollWidth} CSS px wide at a ` +
        `${REFLOW_VIEWPORT.width} px viewport (SC 1.4.10 reflow). ` +
        `Overflowing: ${reflow.culprits.join(", ")}`,
    );
  } else {
    console.log(`${scheme}: reflow at ${REFLOW_VIEWPORT.width}px OK`);
  }
  await page.close();
}

await browser.close();

if (failures > 0) {
  console.log(`${failures} accessibility failure(s).`);
  process.exit(1);
}
console.log("Accessibility gate passed.");
