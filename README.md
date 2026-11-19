# elixir.land

Elixir Land: a directory of companies with Elixir teams of 2 or more people, by country, sector and team size. The site is one static `index.html` on GitHub Pages.

## Local preview

```
python3 build/build.py
python3 -m http.server 8000
```

Then open http://localhost:8000/. Run the build again after each change to `build/`.

## Build

```
python3 build/build.py
```

The script does these steps:

1. It downloads the pinned Tailwind CLI to `build/bin` on the first run and checks its SHA-256. Git ignores `build/bin`.
2. It compiles `build/app.css` with Tailwind and daisyUI. The daisyUI plugin files are in `build/vendor`.
3. It puts the CSS and `build/data.js` into `build/atlas.src.html` and writes `index.html` at the repo root.

The build needs Python 3 and curl. It does not need Node or npm.

## Styles

- The page uses Tailwind utility classes in `build/atlas.src.html`, also in the class strings of the page script.
- The colors are CSS variables in `build/app.css`, with one block for light and one block for dark. Tailwind colors such as `bg-paper` and `text-muted` read these variables.
- The daisyUI theme also reads these variables, so `btn`, `input`, `select` and `card` follow the light and dark themes.
- `build/app.css` turns on only the daisyUI parts that the page uses, in the `include` list. Add a component to that list before you use it.
- To update Tailwind, change `TAILWIND` and the two `SHA256` values in `build/build.py`. Take the values from `sha256sums.txt` in the Tailwind release.
- To update daisyUI, replace `daisyui.mjs` and `daisyui-theme.mjs` in `build/vendor` with the files from a daisyUI release.

## Refresh the data

The data comes from a private dataset that is not in this repo. The export script lives with that dataset, so the raw data and the individual profiles never come into this repo.

1. Run the private export script. It writes `build/data.js`.
2. Run `python3 build/build.py`.

`data.js` contains only company-level data. Team sizes are ranges. The site never lists people.

## Deploy

Every push to `main` runs `.github/workflows/deploy.yml`. The workflow runs `build/build.py`, then publishes only `index.html` and `CNAME` to GitHub Pages.
