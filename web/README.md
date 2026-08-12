# Playground

`index.html` is a single-page, in-browser build of the validator. It loads
Pyodide from jsDelivr, unpacks a `ctdl-validate` wheel built from the same
commit, and calls `validate_document` on whatever payload you give it.

Nothing is uploaded. The validation runs in the browser's own WebAssembly
sandbox, which is the point: CTDL payloads are usually unpublished when they
most need checking, and a hosted validator would mean sending unreleased
credential and competency data to someone else's server.

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
