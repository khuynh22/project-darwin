# Paper draft folder

Working drafts for the Project Darwin paper. **Markdown is the source of truth**;
Word/PDF are generated outputs, never edited by hand (edits there get overwritten).

## Layout

| path | what it is |
|---|---|
| `OUTLINE.md` | section-by-section plan + target lengths. **Read first.** |
| `CLAIMS.md` | the claim ledger: every claim → evidence → status. **The most important file** — nothing goes in the paper that isn't here with a status. |
| `sections/*.md` | one file per section, written independently, concatenated at build time |
| `figures/` | **frozen** figure copies + `FIGURES.md` (figure → claim mapping). Frozen so re-running analysis can't silently change a paper figure. |
| `refs/refs.bib` | bibliography (the verified prior art) |
| `data/README.md` | provenance: which run backs which number |

## Writing workflow

1. Claim first: add it to `CLAIMS.md` with a status before writing a sentence about it.
2. Draft in the relevant `sections/*.md`. Mark gaps with `TODO(data)` / `TODO(cite)`.
3. Never hand-edit generated `.docx` / `.pdf`.

## Build to Word

Requires pandoc (`winget install --id JohnMacFarlane.Pandoc`):

```bash
cd paper
pandoc sections/*.md -o draft.docx \
  --bibliography=refs/refs.bib --citeproc \
  --resource-path=.:figures --toc
```

Files concatenate in filename order (`00-`, `01-`, …), so the numeric prefixes
set section order. For PDF swap `-o draft.pdf`. Without pandoc, paste the
rendered markdown into Word — but keep editing the markdown.

## Status

Pre-first-draft. Instrument + method are done and validated; results are
partly collected. `CLAIMS.md` is the honest ledger of what is actually
supported today vs. what still needs data.
