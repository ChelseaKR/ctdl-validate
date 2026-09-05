# Playground

`index.html` is a single-page, in-browser build of the validator. It loads
Pyodide from jsDelivr, unpacks a `ctdl-validate` wheel built from the same
commit, and calls `validate_document` on whatever payload you give it.

Nothing is uploaded. The validation runs in the browser's own WebAssembly
sandbox, which is the point: CTDL payloads are usually unpublished when they
most need checking, and a hosted validator would mean sending unreleased
credential and competency data to someone else's server.

The playground is the validator only. `ctdl-validate extract` fetches a page,
which needs a robots.txt check and a rate limit against the site's real
origin, and neither is something a browser tab can honestly promise. It stays
a command line tool; see the README's [Extraction](../README.md#extraction)
section for its network posture.

## What the page does

- **Validates.** A payload box, an optional second box for the documents
  `--resolve` takes on the command line, a file picker, and three samples kept
  verbatim from `tests/fixtures/`.
- **Lists every rule this build can report, without stating anything about
  any of them.** See below; this is the part with a gate behind it.
- **Hands the report back.** Copy it in the layout `ctdl-validate` prints,
  download it as the same JSON `--format json` writes, or copy a link that
  carries the payload in its URL fragment. The first two call the CLI's own
  renderers through Pyodide rather than reformatting anything in JavaScript.
  The link is capped at 8,000 characters and refuses, with the number, above
  that; the copy confirmation says in as many words that the link is a copy of
  the payload.

## How the rule list stays true

The page shows every finding code this build can emit. It does not describe
any of them.

Instead it ships one *document* per code, in a
`<script type="application/json" id="rule-corpus">` block, runs the validator
over each one in the browser, and prints what came back. The severity, the
wording and the citation on every row are that run's output. The list of codes
is not in the page at all: the Python in `#py-bootstrap` walks the AST of the
check modules inside the wheel it just unpacked, which is the same scan
`tests/test_every_rule_fires.py` uses and for the same reason.

`tests/test_playground_catalogue.py` holds it up. It reads those two blocks
out of this file, executes the page's own Python rather than a copy of it, and
fails if a code has no document, if a document is filed under a code the
source no longer emits, if a document stops producing the code it is filed
under, or if the page's scan and the test suite's scan disagree. Each of those
was broken on purpose and watched go red.

## How it is gated

`.github/workflows/accessibility.yml` audits two URLs on every pull request
that touches `web/`, and neither boots Pyodide.

- `index.html?a11y-static` renders the post-run state: one finding of each
  severity through the same `renderFinding()` a real run uses, one catalogue
  row of each severity through the same `renderCatalogueRow()`, and the report
  actions and share field visible.
- `index.html?a11y-static=loading` renders the startup state, with the
  progress element and the status line.

All of that matters. Scanning the page as it first loads audits a textarea and
a few buttons and never sees the report, which is where nearly all of the
markup is and the only place the severity colours appear; that is how a reflow
failure at 320 CSS px survived until 2026-08-15. Auditing only the post-run
state never sees the thirty seconds a visitor spends before it. And not
booting means the audit fetches nothing, so a merge never depends on a CDN.

`audit.mjs` also fails when a control the post-run state adds is missing or
invisible. That is deliberately not an accessibility rule: it is the gate
refusing to grade a page that is missing the parts it was extended to grade,
because UI a gate cannot see is UI a gate does not audit.

Run it locally the way CI does:

```sh
npm install --no-save puppeteer-core@23.11.1 axe-core@4.13.0
python3 -m http.server 8931 --directory web &
CHROME_PATH="$(which google-chrome || echo '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')" \
  node web/a11y/audit.mjs "http://127.0.0.1:8931/index.html?a11y-static"
CHROME_PATH="$(which google-chrome || echo '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')" \
  node web/a11y/audit.mjs "http://127.0.0.1:8931/index.html?a11y-static=loading"
```

## Why the runtime runs on a worker

Pyodide takes about eight seconds to compile its WebAssembly and start
CPython. On the main thread that is eight seconds in which the page cannot
scroll, cannot take a keystroke, and cannot repaint the status line it just
changed; Lighthouse measured 8,020 ms of total blocking time on the published
page and scored performance 0.70. It now boots on a worker: 0 ms blocking,
1.00.

The download still starts on load. Deferring it behind the Validate button
would clear the score too, and would replace a wait you were told about with a
wait you were not; `docs/ROADMAP.md` records that trade as refused.

Subresource Integrity is not defined on a worker's top-level script, so the
page fetches `pyodide.js` itself, hashes it with SubtleCrypto, compares it to
the pinned `sha384-` digest, and builds the worker only if they match. Where
`crypto.subtle` does not exist -- any origin that is not a secure context --
the page falls back to loading the runtime on the main thread with the
`integrity` attribute, and says so in the status line and the footer.

The byte budget is still not met and still declared:
[docs/ROADMAP.md](../docs/ROADMAP.md) carries the numbers, including why the
"script bytes" figure did not really drop just because Lighthouse now files
most of the runtime under a different resource type.

## How it gets published

`.github/workflows/pages.yml` builds the wheel with `uv build --wheel`, copies
it next to `index.html`, and writes `wheel.json` naming the file. The page
fetches the manifest first, so bumping the version in `pyproject.toml` changes
the wheel's filename and the page follows it with no edit here.

`social-card.png` is copied alongside them. It is the 1200x630 image the head's
`og:image` names, and it is served from this origin rather than linked from
somewhere else so that a link preview breaks only when this deploy breaks. The
workflow fails if the head names a card the artifact does not carry, and
`tests/test_playground_catalogue.py` fails, without a runner, if the head and
the file disagree about the address, the dimensions or the alt text. The card
says the title and the description already in the head and nothing more: no
rule count, no conformance claim, nothing about Credential Engine.

Because the wheel is served from the same origin, the page's
Content-Security-Policy allows exactly two network origins: `cdn.jsdelivr.net`
for the Pyodide runtime, and `'self'` for the wheel. There is no PyPI call at
any point, and the validator running in the browser is always the code
published beside it. `tests/test_playground_catalogue.py` asserts that policy
directive by directive, including that `'unsafe-eval'` is absent, and fails if
the page ever mentions `sendBeacon`, `XMLHttpRequest`, `WebSocket`,
`EventSource` or a `<form`.

One-time repository setup: **Settings → Pages → Source: "GitHub Actions"**.

## Running it locally

```sh
uv build --wheel --out-dir dist
mkdir -p site && cp web/index.html web/social-card.png site/ && cp dist/*.whl site/
printf '{"wheel": "%s", "version": "%s"}\n' "$(basename dist/*.whl)" "$(uv version --short)" > site/wheel.json
python -m http.server -d site 8899
```

Then open <http://localhost:8899/>. It must be served over HTTP; opening the
file directly with `file://` fails, because `fetch` cannot read the wheel from
a file URL.

## Updating Pyodide

The `<script>` tag pins a version and a Subresource Integrity hash. When
bumping the version, regenerate the hash so the two agree:

```sh
curl -sSL https://cdn.jsdelivr.net/pyodide/vX.Y.Z/full/pyodide.js \
  | openssl dgst -sha384 -binary | openssl base64 -A
```

Prefix the result with `sha384-`.
