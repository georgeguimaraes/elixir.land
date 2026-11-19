# elixir.land

Elixir Land: a directory of companies with Elixir teams of 2 or more people, by country, sector and team size. The site is one static `index.html` on GitHub Pages.

## Local preview

```
elixir build/build.exs
elixir build/serve.exs
```

Then open http://127.0.0.1:8000/. Run the build again after each change to `build/`. The server uses the web server that comes with Erlang. To use a different port, give it as an argument: `elixir build/serve.exs 4000`.

The page has no external files except the fonts, so `open index.html` also works without a server.

## Build

```
elixir build/build.exs
```

The script does these steps:

1. It downloads the pinned Tailwind CLI to `build/bin` on the first run and checks its SHA-256. Git ignores `build/bin`.
2. It compiles `build/app.css` with Tailwind and daisyUI. The daisyUI plugin files are in `build/vendor`.
3. It puts the CSS and `build/data.js` into `build/atlas.src.html` and writes `index.html` at the repo root.

The build needs Elixir and curl. It does not need Node, npm or Python.

## Styles

- The page uses Tailwind utility classes in `build/atlas.src.html`, also in the class strings of the page script.
- The colors are CSS variables in `build/app.css`, with one block for light and one block for dark. Tailwind colors such as `bg-paper` and `text-muted` read these variables.
- The daisyUI theme also reads these variables, so `btn`, `input`, `select` and `card` follow the light and dark themes.
- `build/app.css` turns on only the daisyUI parts that the page uses, in the `include` list. Add a component to that list before you use it.
- To update Tailwind, change `@tailwind` and the two `@sha256` values in `build/build.exs`. Take the values from `sha256sums.txt` in the Tailwind release.
- To update daisyUI, replace `daisyui.mjs` and `daisyui-theme.mjs` in `build/vendor` with the files from a daisyUI release.

## Refresh the data

The data comes from a private dataset that is not in this repo. The export script lives with that dataset, so the raw data and the individual profiles never come into this repo.

1. Run the private export script. It writes `build/data.js`.
2. Run `elixir build/build.exs`.

`data.js` contains only company-level data. Team sizes are ranges. The site never lists people.

## Analytics

The page loads GoatCounter (`count.v4.js`) from `gc.zgo.at`, with an SRI hash. The dashboard is at https://georgeguimaraes.goatcounter.com.

- GoatCounter sets no cookies and does not count visits from localhost or `file://`.
- The page sends events for filters, searches, opened companies, link clicks with a `data-track` attribute and agent tool calls. Event names hold company names and filter values, never visitor data.
- To move to a new GoatCounter script version, change the `src` and the `integrity` hash in `build/atlas.src.html` together.

## Deploy

Every push to `main` runs `.github/workflows/deploy.yml`. The workflow runs `build/build.exs`, then publishes only `index.html` and `CNAME` to GitHub Pages.
