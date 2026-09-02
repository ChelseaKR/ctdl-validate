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
// It also checks the document head, which is not an accessibility question.
// That is deliberate rather than sloppy. This script is the only merge-blocking
// gate this repository points at web/index.html, it already has the page open
// in a browser, and the head's failure modes are the same kind as the ones
// above: invisible to anyone looking at the page, because the browser has
// already been handed the page it is going to render. A second workflow to
// read six meta tags would be a parallel gate over one file, which is how a
// repository ends up with two checks that each assume the other is doing it.
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

// The page has two static states, and this script audits whichever one the URL
// asks for. `?a11y-static` is the post-run state: the report and the rule
// catalogue, which between them hold nearly all of this page's markup and all
// four severity colours. `?a11y-static=loading` is the startup state, which
// docs/RESPONSIBLE-TECH-AUDITS.md section H recorded as unscanned: a progress
// element, a status line, and a Validate button that is not yet a Validate
// button. Neither state boots Pyodide, so neither fetches anything.
const MODE = new URL(URL_UNDER_TEST).searchParams.get("a11y-static");
const IS_STATIC = new URL(URL_UNDER_TEST).searchParams.has("a11y-static");
const IS_LOADING = MODE === "loading";

// Every id this script reaches for, in one place, so that renaming one in the
// page fails here loudly instead of turning a check into a no-op that passes.
const REQUIRED_IN_REPORT_STATE = [
  "report-actions",
  "copy-text",
  "download-json",
  "copy-link",
  "share-row",
  "share-link",
];
const REQUIRED_IN_LOADING_STATE = ["boot-progress", "status", "run"];

// ---------------------------------------------------------------------------
// The head
// ---------------------------------------------------------------------------

// Written out rather than derived from the page, which is the whole point: an
// expectation read out of the thing under test moves with the mistake and
// stays green.
const PUBLISHED_AT = "https://chelseakr.github.io/ctdl-validate/";
const CARD_AT = "https://chelseakr.github.io/ctdl-validate/social-card.png";

// Words that would make the description claim something the page does not.
// This is a validator for a published specification it does not speak for, so
// two kinds of sentence are out: one that implies Credential Engine has
// endorsed, approved or published it, and one that quotes a rule count or a
// conformance level. The README carries the affiliation disclaimer in full;
// the description's job is not to repeat it but not to contradict it.
const FORBIDDEN_IN_DESCRIPTION = [
  "official",
  "endorsed",
  "approved",
  "certified",
  "conformant",
  "conformance",
  "compliant",
  "authoritative",
  "complete coverage",
  "full coverage",
];

async function requireTheHeadNamesThisPage(page) {
  const head = await page.evaluate(() => {
    const meta = (selector) =>
      document.head.querySelector(selector)?.getAttribute("content") ?? null;
    return {
      title: document.title,
      description: meta('meta[name="description"]'),
      canonical: document.head.querySelector('link[rel="canonical"]')?.getAttribute("href") ?? null,
      ogUrl: meta('meta[property="og:url"]'),
      ogTitle: meta('meta[property="og:title"]'),
      ogDescription: meta('meta[property="og:description"]'),
      ogType: meta('meta[property="og:type"]'),
      ogSiteName: meta('meta[property="og:site_name"]'),
      twitterCard: meta('meta[name="twitter:card"]'),
      ogImage: meta('meta[property="og:image"]'),
      ogImageAlt: meta('meta[property="og:image:alt"]'),
      ogImageWidth: meta('meta[property="og:image:width"]'),
      ogImageHeight: meta('meta[property="og:image:height"]'),
      twitterImage: meta('meta[name="twitter:image"]'),
      // Root-relative only. A protocol-relative //host/x is a different thing
      // and is not this mistake.
      rooted: [...document.querySelectorAll("[href], [src]")]
        .map((el) => el.getAttribute("href") ?? el.getAttribute("src"))
        .filter((value) => value && value.startsWith("/") && !value.startsWith("//")),
    };
  });

  if (!head.title || !head.title.trim()) fail("the page has no title");
  if (!head.description || !head.description.trim()) {
    fail("the page has no meta description, so anything that reads a head reads only a title");
  }
  for (const [name, value] of [
    ["canonical", head.canonical],
    ["og:url", head.ogUrl],
  ]) {
    if (value !== PUBLISHED_AT) {
      fail(
        `${name} is ${value === null ? "absent" : JSON.stringify(value)}; expected ` +
          `${JSON.stringify(PUBLISHED_AT)}. This page is served at a path on an origin five ` +
          `sibling projects share, and the bare origin is a 404, so an address without ` +
          `/ctdl-validate/ names another project or nothing.`,
      );
    }
  }
  if (head.rooted.length) {
    fail(
      `root-relative references escape /ctdl-validate/: ${head.rooted.join(", ")}. ` +
        `They resolve against chelseakr.github.io, not against this page.`,
    );
  }
  if (head.ogType !== "website") fail(`og:type is ${JSON.stringify(head.ogType)}, expected "website"`);
  if (!head.ogSiteName) fail("og:site_name is absent");
  if (head.twitterCard !== "summary_large_image") {
    fail(`twitter:card is ${JSON.stringify(head.twitterCard)}, expected "summary_large_image"`);
  }
  // A card declared large with no image is worse than no card: the platform
  // renders a blank rectangle where the page's own words would have been.
  for (const [name, value] of [
    ["og:image", head.ogImage],
    ["twitter:image", head.twitterImage],
  ]) {
    if (value !== CARD_AT) {
      fail(
        `${name} is ${value === null ? "absent" : JSON.stringify(value)}; expected ` +
          `${JSON.stringify(CARD_AT)}. The card is published beside this page by ` +
          `pages.yml, and an address without /ctdl-validate/ names another project ` +
          `or nothing.`,
      );
    }
  }
  if (!head.ogImageAlt || !head.ogImageAlt.trim()) {
    fail("og:image:alt is absent: the card carries the page's only words in a preview, and a reader who cannot see it gets none of them");
  }
  if (head.ogImageWidth !== "1200" || head.ogImageHeight !== "630") {
    fail(
      `og:image:width/height are ${JSON.stringify(head.ogImageWidth)}x` +
        `${JSON.stringify(head.ogImageHeight)}, expected 1200x630. They are what lets a ` +
        `crawler lay the card out before it has fetched it.`,
    );
  }
  // The card and the page are two statements about one thing, so they are held
  // equal rather than each checked for being non-empty.
  if (head.ogTitle !== head.title) {
    fail(`og:title and <title> disagree: ${JSON.stringify(head.ogTitle)} vs ${JSON.stringify(head.title)}`);
  }
  if (head.ogDescription !== head.description) {
    fail("og:description and the meta description disagree");
  }

  const description = (head.description ?? "").toLowerCase();
  for (const word of FORBIDDEN_IN_DESCRIPTION) {
    if (description.includes(word)) {
      fail(
        `the description contains ${JSON.stringify(word)}. This tool does not speak for ` +
          `the specification it validates, and it states no coverage it has not measured.`,
      );
    }
  }
  if (/\b[0-9]+\b/.test(head.description ?? "")) {
    fail(
      `the description states a figure: ${JSON.stringify(head.description)}. A rule count ` +
        `here would be a copy nothing derives and nothing checks.`,
    );
  }
}

async function requireTheStaticStateRendered(page, scheme) {
  if (!IS_STATIC) return;
  if (IS_LOADING) return requireTheStartupRendered(page, scheme);
  return requireTheReportRendered(page, scheme);
}

async function requireTheReportRendered(page, scheme) {
  const state = await page.evaluate((ids) => {
    const severities = (selector) =>
      [...document.querySelectorAll(selector)].map((el) => el.textContent.trim());
    const shown = (id) => {
      const el = document.getElementById(id);
      if (!el) return null;
      // offsetParent is null for a hidden element and for a positioned one;
      // nothing on this page is positioned, so it reads as "on the page".
      return el.offsetParent !== null || el === document.body;
    };
    return {
      findings: severities(".finding .sev"),
      catalogue: severities(".rulecard .sev"),
      present: Object.fromEntries(ids.map((id) => [id, shown(id)])),
    };
  }, REQUIRED_IN_REPORT_STATE);

  for (const [what, rendered] of [
    ["report", state.findings],
    ["rule catalogue", state.catalogue],
  ]) {
    const missing = EXPECTED_SEVERITIES.filter((s) => !rendered.includes(s));
    if (missing.length) {
      fail(
        `${scheme}: the static ${what} did not render. Expected an entry at each of ` +
          `${EXPECTED_SEVERITIES.join(", ")}; missing ${missing.join(", ")}. ` +
          `Scanning the page without it is not an audit.`,
      );
    }
  }
  for (const [id, present] of Object.entries(state.present)) {
    if (present !== true) {
      fail(
        `${scheme}: #${id} is ${present === null ? "not in the page" : "not visible"} in the ` +
          `static report state. UI the gate cannot see is UI the gate does not audit.`,
      );
    }
  }
}

async function requireTheStartupRendered(page, scheme) {
  const state = await page.evaluate((ids) => {
    const el = (id) => document.getElementById(id);
    return {
      present: Object.fromEntries(ids.map((id) => [id, Boolean(el(id))])),
      progressVisible: Boolean(el("boot-progress") && el("boot-progress").offsetParent !== null),
      progressValue: el("boot-progress") ? el("boot-progress").value : null,
      progressName: el("boot-progress") ? el("boot-progress").getAttribute("aria-label") : null,
      status: el("status") ? el("status").textContent.trim() : "",
      runDisabled: el("run") ? el("run").getAttribute("aria-disabled") : null,
      findings: document.querySelectorAll(".finding").length,
    };
  }, REQUIRED_IN_LOADING_STATE);

  for (const [id, present] of Object.entries(state.present)) {
    if (!present) fail(`${scheme}: #${id} is not in the page in the static startup state`);
  }
  if (!state.progressVisible) {
    fail(
      `${scheme}: the startup progress element is not visible, so the state this mode ` +
        `exists to audit is not on the page`,
    );
  }
  if (!state.progressName) fail(`${scheme}: the startup progress element has no accessible name`);
  if (!(state.progressValue > 0)) {
    fail(`${scheme}: the startup progress element reads ${state.progressValue}, not a step underway`);
  }
  if (!state.status) fail(`${scheme}: the startup status line is empty, so the wait is unannounced`);
  if (state.runDisabled !== "true") {
    fail(
      `${scheme}: the Validate button reads aria-disabled=${JSON.stringify(state.runDisabled)} ` +
        `during startup. It stays focusable on purpose, so a keyboard user meets it during the ` +
        `wait; it has to say it is not ready yet.`,
    );
  }
  if (state.findings) {
    fail(`${scheme}: the startup state rendered ${state.findings} findings; it is meant to be pre-run`);
  }
}

for (const scheme of SCHEMES) {
  const page = await browser.newPage();
  await page.emulateMediaFeatures([{ name: "prefers-color-scheme", value: scheme }]);
  await page.goto(URL_UNDER_TEST, { waitUntil: "networkidle0" });
  await requireTheStaticStateRendered(page, scheme);
  if (scheme === SCHEMES[0]) await requireTheHeadNamesThisPage(page);
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
