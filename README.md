# elixir.land

landing page for elixir.land. single static `index.html`, hosted on GitHub Pages.

## local preview

```
open index.html
```

## rebuild

`index.html` is generated from `build/build.py`. paths come from a Natural Earth 110m TopoJSON, the face is a base64-embedded crop of josé valim's github avatar.

```
python3 build/build.py
```

writes a fresh `index.html` at the repo root.

## deploy

every push to `main` runs `.github/workflows/deploy.yml`: rebuilds index.html, stages it with `CNAME`, and publishes only those two files to GitHub Pages. the rest of the repo (build scripts, source data) stays out of the deployed site.

requires Pages enabled in repo settings with source set to "GitHub Actions". on private repos this needs a paid plan.
