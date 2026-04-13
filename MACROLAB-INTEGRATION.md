# MacroLab Integration Plan

This document describes the changes required for `autoresearch-macro` to appear inside MacroLab without moving this project's modelling code, data pipeline, or webapp source into the MacroLab repository.

The target architecture is:

- `autoresearch-macro` remains the source of truth for research code, data preparation, results, and the Quarto webapp
- MacroLab remains the catalog and presentation layer
- `autoresearch-macro` publishes a static artifact bundle plus a small manifest that MacroLab can consume

## Why this approach

MacroLab should not own:

- training or search code
- raw experiment outputs
- figure generation logic
- Quarto page source

Those concerns belong in this repo. MacroLab should only expose a published snapshot of this project's outputs.

This keeps the integration modular:

- the project can evolve independently
- MacroLab can add or remove the project without repo surgery
- updates become a publish step, not a code migration

## Target integration model

`autoresearch-macro` should be integrated into MacroLab as an external artifact project:

- MacroLab project kind: `artifact`
- MacroLab source adapter key: `artifact`
- Lifecycle status: initially `preview`
- Published app URL: `/published/autoresearch-macro/index.html`

MacroLab will show:

- the project card on the landing page
- a project shell page with metadata, summary stats, and a button to open the artifact
- optionally an embedded iframe later, but that is not required for the first pass

## Required changes in this repo

### 1. Add a publish script

Add a script such as:

- `scripts/publish_to_macrolab.sh`

Its responsibilities should be:

1. regenerate the webapp data JSON
2. render the Quarto site
3. create a release directory on the VPS
4. copy the rendered `_site/` output into that release directory
5. write a `macrolab-manifest.json`
6. atomically repoint the public artifact path
7. call MacroLab's sync script

Expected pipeline:

```bash
uv run python webapp/_data/prepare_results.py
cd webapp && quarto render
rsync webapp/_site/ -> /opt/macrolab/project-artifacts/releases/autoresearch-macro/<timestamp>/
write macrolab-manifest.json
ln -sfn <release> /opt/macrolab/project-artifacts/public/autoresearch-macro
python /home/vegard/MacroLab/scripts/sync_project_publication.py --manifest ...
```

### 2. Add a manifest builder

Either:

- generate the manifest inline in the publish shell script, or
- add a Python helper such as `scripts/build_macrolab_manifest.py`

The second option is cleaner if summary stats should be computed from current results.

Recommended manifest shape:

```json
{
  "integration_mode": "artifact_site",
  "entrypoint": "/published/autoresearch-macro/index.html",
  "headline": "Agentic search over macro forecasting pipelines across Norway, Canada, and Sweden",
  "published_at": "2026-04-13T12:00:00Z",
  "source_revision": "git-sha",
  "summary_stats": [
    { "label": "Countries", "value": "3" },
    { "label": "Validation era", "value": "2006-2015" },
    { "label": "Site type", "value": "Quarto" }
  ],
  "links": [
    { "label": "Repository", "href": "autoresearch-macro" }
  ],
  "embed": false
}
```

Notes:

- `entrypoint` must stay under `/published/...`
- `published_at` should be generated at publish time, not hard-coded
- `source_revision` should come from `git rev-parse HEAD`
- `summary_stats` should be short and stable

### 3. Decide how to populate summary stats

The summary stats shown in MacroLab should come from current project outputs, not from hand-edited text.

Good candidates:

- number of countries in the current dashboard
- validation era window
- test era window
- number of methods compared
- latest best validation score for a headline comparator

Avoid stats that are too volatile or too hard to validate automatically.

### 4. Keep the webapp output self-contained

The rendered Quarto site should be publishable as a static directory only.

That means:

- no dependency on local absolute paths
- no dependency on notebooks or source files being present on the serving side
- no dependency on unpublished `results/` files after render

The current Quarto output already appears compatible with this because it uses relative asset paths such as:

- `./index.html`
- `site_libs/...`
- `_data/...`

That is the right shape for MacroLab artifact hosting.

### 5. Treat `_site/` as a publish artifact, not as the integration contract

The integration contract is:

- static site directory
- manifest JSON

Do not make MacroLab inspect:

- raw `results/`
- `forecast_errors.parquet`
- Quarto source `.qmd` files
- project-specific Python internals

Those are implementation details of this repo.

### 6. Add a documented publish procedure

Update `README.md` or a deployment-oriented note to document:

- prerequisites for publishing to MacroLab
- where the artifact is copied on the VPS
- how to roll back to an older release
- how to refresh MacroLab after a new publication

If this becomes a recurring workflow, add a short section called `Publishing to MacroLab`.

## Recommended file additions

Recommended new files in this repo:

- `scripts/publish_to_macrolab.sh`
- optionally `scripts/build_macrolab_manifest.py`

Optional documentation additions:

- add a `Publishing to MacroLab` section to `README.md`

## Example publish layout on the VPS

```text
/opt/macrolab/project-artifacts/
├── public/
│   └── autoresearch-macro -> ../releases/autoresearch-macro/20260413T120000Z
└── releases/
    └── autoresearch-macro/
        ├── 20260413T120000Z/
        │   ├── index.html
        │   ├── results.html
        │   ├── search.html
        │   ├── styles.css
        │   ├── site_libs/
        │   ├── _data/
        │   └── macrolab-manifest.json
        └── 20260420T090000Z/
```

This layout gives:

- atomic deploys
- simple rollbacks
- a stable public path for MacroLab

## Recommended first implementation scope

For the first pass, keep this repo-side work small:

1. create the publish script
2. create the manifest generation step
3. publish the current Quarto site as a static artifact
4. sync the manifest into MacroLab

Do not add:

- bidirectional communication with MacroLab
- project-specific API endpoints just for MacroLab
- direct reads by MacroLab into this repo's raw results
- a custom frontend rewrite of the Quarto site inside MacroLab

## Open decisions

These decisions should be made when implementing the publisher:

- whether `summary_stats` are computed by shell or Python
- whether the publish script runs directly on the VPS or from a CI job with access to the VPS
- whether the MacroLab project shell should link out only or eventually embed the app
- whether a preview image should also be published for the MacroLab landing page

## Bottom line

The required change is not to move this project into MacroLab.

The required change is to make this repo publish a clean, versioned, static bundle with a small manifest. MacroLab can then expose that bundle as a modular external project with minimal coupling.
