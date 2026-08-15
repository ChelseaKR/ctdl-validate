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

## How it is gated

`.github/workflows/accessibility.yml` audits `index.html?a11y-static` on every
pull request that touches `web/`. That query parameter renders the page in its
post-run state, with one finding of each severity laid out through the same
`renderFinding()` a real run uses, and without booting Pyodide.

Both halves of that matter. Scanning the page as it first loads audits a
textarea and four buttons and never sees the report, which is where nearly all
of the markup is and the only place the severity colours appear; that is how a
reflow failure at 320 CSS px survived until 2026-08-15. And not booting means
the audit fetches nothing, so a merge never depends on a CDN.

Run it locally the way CI does:

```sh
npm install --no-save puppeteer-core@23.11.1 axe-core@4.13.0
python3 -m http.server 8931 --directory web &
CHROME_PATH="$(which google-chrome || echo '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')" \
  node web/a11y/audit.mjs "http://127.0.0.1:8931/index.html?a11y-static"
```

The performance side is measured and declared rather than gated: the page
cannot meet the portfolio's script-size budget while shipping a 5.6 MB Python
runtime, and [docs/ROADMAP.md](../docs/ROADMAP.md) says so with the numbers.

## How it gets published

`.github/workflows/pages.yml` builds the wheel with `uv build --wheel`, copies
it next to `index.html`, and writes `wheel.json` naming the file. The page
fetches the manifest first, so bumping the version in `pyproject.toml` changes
the wheel's filename and the page follows it with no edit here.

Because the wheel is served from the same origin, the page's
Content-Security-Policy allows exactly two network origins: `cdn.jsdelivr.net`
for the Pyodide runtime, and `'self'` for the wheel. There is no PyPI call at
any point, and the validator running in the browser is always the code
published beside it.

One-time repository setup: **Settings → Pages → Source: "GitHub Actions"**.

## Running it locally

```sh
uv build --wheel --out-dir dist
mkdir -p site && cp web/index.html site/ && cp dist/*.whl site/
printf '{"wheel": "%s", "version": "0.1.0"}\n' "$(basename dist/*.whl)" > site/wheel.json
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
