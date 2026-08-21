---
name: latex-build-workflow
description: "Compile LaTeX documents and write complete academic papers. Covers tectonic installation, missing .sty resolution, common compilation errors, academic paper structure (NeurIPS/arXiv), writing TikZ figures, algorithm blocks, pgfplots charts, formal definitions, negative controls methodology, comparison tables, implementation stack tables, qualitative recall traces, and gathering data from live Mazemaker MCP before writing. Also covers updating .tex source with live data and recompiling."
trigger: "user asks to compile a .tex file, update a LaTeX paper, fix a LaTeX compilation error, or install a LaTeX toolchain"
tags: [latex, tectonic, paper, compilation, pdf, academic, tex]
category: software-development
---

# LaTeX Build Workflow

Compile LaTeX documents when full texlive is not installed. Uses tectonic as the lightweight build engine.

## 1. Install tectonic

```bash
# Arch Linux — single package, ~15 MB installed
sudo pacman -S tectonic

# Check version
tectonic --version
```

Tectonic auto-downloads packages from its bundle on first use. First run downloads ~60 MB of TeXLive packages but caches them for all future builds.

### Alternative: Full texlive + pdflatex

When the user already has full texlive installed (Arch: `texlive-core`, `texlive-latexextra`, `texlive-science`, `texlive-publishers`), use pdflatex instead of tectonic. This is sometimes necessary when:
- Conference `.sty` files (NeurIPS, CVPR, ICML) need local packages not in tectonic's bundle
- The user prefers the standard toolchain
- BibTeX produces empty `.bbl` in tectonic (rare but happens with complex bibliographies)

```bash
# Arch Linux — full texlive for conference paper compilation
sudo pacman -S texlive-latexextra texlive-science texlive-publishers

# Install missing .sty packages on demand (keep trying until it compiles)
for pkg in texlive-latexextra texlive-science texlive-publishers texlive-bibtexextra; do
  sudo pacman -S --noconfirm "$pkg" 2>/dev/null
done
```

Common missing packages for NeurIPS papers:
- `microtype.sty` → install `texlive-latexextra`
- `algorithm.sty` → install `texlive-science`
- `algpseudocode.sty` → install `texlive-science`

## 2. Handle missing .sty files

Tectonic's bundle covers ~90% of standard packages. Missing styles are common for conference-specific styles (arXiv, NeurIPS, CVPR, etc.).

### Download from source

```bash
# arxiv.sty — from the arxiv-style GitHub repo
curl -sL "https://raw.githubusercontent.com/kourgeorge/arxiv-style/master/arxiv.sty" -o arxiv.sty

# From any public GitHub repo that includes the .sty file
curl -sL "<raw-github-url>" -o <package>.sty
```

### Create a minimal stub (last resort)

When the official style file is unavailable (e.g. NeurIPS removed their style pages), create a minimal `.sty` that accepts the options your paper uses and provides the basic formatting:

```latex
% Minimal <package>.sty stub for compilation purposes
\ProvidesPackage{<package>}[2024/01/01 Minimal stub]

% Accept options the paper passes
\newif\if@optiona
\newif\if@optionb
\DeclareOption{optiona}{\@optionatrue}
\DeclareOption{optionb}{\@optionbtrue}
\DeclareOption*{}
\ProcessOptions\relax

% Required packages
\RequirePackage{geometry}
\RequirePackage{fancyhdr}

% Provide \maketitle, abstract, etc.
% ...
\endinput
```

### Alternative: Install texlive-publishers

For conference/publisher styles that may not be in tectonic's bundle:

```bash
sudo pacman -S texlive-publishers
```

Note: Even with this installed, some conference-specific `.sty` files (like NeurIPS) may not be included due to licensing. See "create minimal stub" approach above.

## 3. Compile

```bash
cd /path/to/paper/dir
tectonic main.tex -p
```

### Key flags
- `-p` : print engine chatter (useful for seeing which packages are being downloaded and spotting warnings)
- `--keep-intermediates` : keep `.aux`, `.log`, `.bbl` files (useful for debugging)
- `--outdir <dir>` : output directory (default: same as input)
- `-r 3` : force 3 reruns (useful when cross-references aren't resolving)

### Catching compilation errors
Tectonic prints errors to stderr. To check for success:

```bash
# Quick exit code check
tectonic main.tex -p 2>&1 && echo "OK" || echo "FAILED"

# Extract specific signals from output
tectonic main.tex -p 2>&1 | grep -E 'error:|Output written|note: Writing'
```

### Recompile after changes (bibtex loop)
Tectonic auto-runs bibtex when needed. It does NOT figure out how many passes are needed — it reruns TeX after bibtex completes. If citations are still unresolved after the first compile:

```bash
tectonic main.tex -p -r 2
```

### Alternative: pdflatex + bibtex workflow

When using full texlive instead of tectonic, the compilation sequence is:

```bash
cd /path/to/paper/dir

# Step 1: First pdflatex pass (generates .aux for bibtex)
pdflatex -interaction=nonstopmode main.tex

# Step 2: Bibtex (resolves citations)
bibtex main

# Step 3-4: Two more pdflatex passes (resolves cross-references)
pdflatex -interaction=nonstopmode main.tex
pdflatex -interaction=nonstopmode main.tex

# Verify: no "undefined" warnings
grep -E "Warning.*undefined|Error" main.log || echo "Clean build"

# Check page count
grep "Output written" main.log
```

Use `-interaction=nonstopmode` so pdflatex doesn't stop on errors. Missing packages still cause fatal errors — install them and re-run from step 1.

### Troubleshooting undefined references after bibtex

If `pdflatex` + `bibtex` completes but you still get "Reference `...' undefined on input line":
1. The `.aux` file was generated before bibtex ran → need a `pdflatex` → `bibtex` → `pdflatex` → `pdflatex` sequence (not just pdflatex twice)
2. **Duplicate `\appendix`** — having `\appendix\n\appendix` (two copies in a row) causes LaTeX to lose track of appendix section labels. All references to `sec:audit`, `sec:appendix`, or any label inside the appendix become "undefined." Fix by removing the duplicate line. Verify with `grep -n "appendix" main.tex` — should show exactly one `\appendix` line.
3. A `.bbl` file with correct entries but no `.aux` pointers → run `rm main.aux main.bbl` and redo the full sequence.

## 4. Packages for complete academic papers

A complete paper (NeurIPS, ICML, arXiv) needs more than `article.cls`. Add these to the preamble:

```latex
\usepackage{algorithm}
\usepackage{algpseudocode}      % Algorithm blocks with pseudocode
\usepackage{pgfplots}
\pgfplotsset{compat=1.18}       % Bar charts and line charts
\usepackage{multirow}           % Multi-row table cells
\usepackage{colortbl}           % Colored table cells
\usepackage{booktabs}           % Professional tables (toprule, midrule, bottomrule)
\usepackage{amsmath, amssymb, mathtools}  % Math
\usepackage{tikz}
\usetikzlibrary{arrows.meta, positioning, shapes.geometric, calc, backgrounds, fit}
\usepackage{hyperref, cleveref} % Cross-references
```

## 5. Writing TikZ figures without stacking errors

### The `fit` + `minimum width/height` conflict

When using `\node[layer, fit={(node1) (node2) (node3)}]` to draw a bounding box around nodes, the `layer` style must NOT have `minimum width` or `minimum height` set. If it does, the fit box is oversized and all inner nodes appear stacked on top of each other.

```latex
% WRONG — nodes will appear stacked:
layer/.style={rectangle, fill=gray!8, minimum width=14cm,
             minimum height=3.2cm, rounded corners=6, draw=gray!30, dashed},

% RIGHT — fit auto-computes the bounding box:
layer/.style={rectangle, fill=gray!8,
             rounded corners=6, draw=gray!30, dashed},
```

The `minimum width/height` override the fit-computed dimensions. Remove them and let `fit` calculate the exact bounding box from the referenced nodes.

## 6. Writing algorithm blocks

For NeurIPS/ICML papers, algorithm pseudocode is expected:

```latex
\begin{algorithm}[t]
\caption{Dream Engine Cycle}
\label{alg:dreame}
\small
\begin{algorithmic}[1]
\Require{Graph $\mathcal{G}=(\mathcal{M},\mathcal{E},w)$, threshold $\tau=0.35$}
\State $\mathcal{S} \gets \text{sample}(50\%\text{ recent} \cup 30\%\text{ old} \cup 20\%\text{ low-salience})$
\For{each $m_i \in \mathcal{S}$}
  \State $\mathbf{p} \gets \text{PPR}_{\text{GPU}}(m_i, \mathcal{G})$
  \State strengthen edges where $p_j > \tau$; prune where $w < 0.05$
\EndFor
\State detect and resolve memory conflicts via cosine $>0.85$
\State bridge orphaned clusters via batched REM search
\State run Louvain community detection; create cluster summaries
\State \Return{$\mathcal{G}$}
\end{algorithmic}
\end{algorithm}
```

Key patterns:
- `\Require` / `\Ensure` for pre/post conditions
- `\State` for each line of pseudocode
- `\For{...}` / `\EndFor`, `\If{...}` / `\EndIf`, `\While{...}` / `\EndWhile`
- `\Comment{...}` for inline comments
- `\Return{...}` for return statements
- `$\sim$6.6\,ms` for approximate values with units (use `\,` for thin space before units)

## 7. Writing figures with pgfplots

### Bar chart for comparison data

```latex
\begin{figure}[t]
\centering
\begin{tikzpicture}[scale=0.85]
\begin{axis}[
  ybar, bar width=10pt,
  width=0.95\textwidth, height=6cm,
  symbolic x coords={Hop-2,Shuffled,Dream,Super.,Cross-sess.},
  xtick=data,
  ylabel={Recall},
  ymin=0, ymax=1.1,
  legend style={at={(0.5,-0.2)}, anchor=north, legend columns=2},
  enlarge x limits=0.25,
  nodes near coords, every node near coord/.style={font=\tiny},
]
\addplot[fill=gray!40] coordinates {(Hop-2,0.00) (Shuffled,0.27) (Dream,0.00) (Super.,0.03) (Cross-sess.,0.06)};
\addplot[fill=purple!60] coordinates {(Hop-2,1.00) (Shuffled,0.27) (Dream,0.43) (Super.,0.33) (Cross-sess.,0.62)};
\legend{Control, Mazemaker}
\end{axis}
\end{tikzpicture}
\caption{Caption here.}
\label{fig:controls}
\end{figure}
```

### Line chart for progression data

```latex
\begin{figure}[t]
\centering
\begin{tikzpicture}[scale=0.9]
\begin{axis}[
  width=0.95\textwidth, height=6cm,
  xlabel={Iteration}, ylabel={R@5},
  xmin=0, xmax=100, ymin=0.3, ymax=1.0,
  xtick={0,20,40,60,72,80,95,100},
  grid=both, grid style={gray!20},
  legend style={at={(0.02,0.02)}, anchor=south west},
]
\addplot[thick, blue!70, mark=*] coordinates {
  (0,0.36) (20,0.48) (40,0.61) (60,0.71) (72,0.7404)
  (74,0.51) (80,0.70) (90,0.79) (95,0.835) (100,0.8426)
};
\addplot[dashed, red!70] coordinates {(0,0.7404) (72,0.7404)}
  node[pos=0.5, above, font=\footnotesize] {retrieval ceiling};
\end{axis}
\end{tikzpicture}
\caption{Caption here.}
\label{fig:progression}
\end{figure}
```

## 8. Writing formal definitions with equations

Academic papers expect formal definitions of core concepts:

```latex
\noindent\textbf{Memory.} A memory is a tuple $m = (d, e, s, t, c, l)$ where
$d$ is raw text, $e \in \mathbb{R}^{1024}$ is the embedding vector,
$s \in [0,1]$ is salience, $t$ is timestamp, $c$ is session id,
$l$ is label.

\noindent\textbf{Knowledge Graph.} $\mathcal{G} = (\mathcal{M}, \mathcal{E}, w)$
where $|\mathcal{E}| = N$ edges and $w: \mathcal{E} \to [0,1]$ is edge weight.

\noindent\textbf{RRF.} $\text{RRF}(m) = \sum_{c \in C} \frac{1}{k + r_c(m)}$

\noindent\textbf{DAE.} $e'_i = \alpha e_i + (1-\alpha)\sum_{j \in \mathcal{N}(i)} \beta_{ij}e_j$

\noindent\textbf{PPR.} $\mathbf{p}_q = (1-\alpha)\mathbf{A}\mathbf{p}_q + \alpha\mathbf{e}_q$
```

## 9. Writing implementation stack tables

```latex
\section{Complete Implementation Stack}

\begin{tabular}{ll}
\toprule
Component & Technology \\
\midrule
Graph engine & C++ CUDA (cuSPARSE PPR), Cython bindings \\
Embedding & BGE-M3 via ONNX Runtime, batched 32/inference \\
Reranker & ColBERT@1.5 via PyTorch CUDA graphs \\
Storage engine & SQLite (public), PostgreSQL + pgvector (scale) \\
Dream daemon & Python 3.11, standalone, Unix socket IPC \\
Federation & JRWL over X3DH (libsignal-protocol-c) \\
\bottomrule
\end{tabular}
```

## 10. Common compilation errors and fixes

### `tikz` fit box errors
```
! Package pgfkeys Error: I do not know the key '/tikz/fit'
```
**Fix:** Add `\usetikzlibrary{fit}` to the preamble. Missing when using `\node[layer, fit={(a) (b)}]`.

### `\[` instead of `$$` in tikz node text
TikZ node text in `\node[...] {text}` must be plain — use `$...$` for inline math, not `\[...\]`. If the node text contains `\\` for line breaks, the math mode must be local to each line.

### `axis` environment undefined
```
! LaTeX Error: Environment axis undefined.
```
**Fix:** Add `\usepackage{pgfplots}` and `\pgfplotsset{compat=1.18}` to the preamble.

### `algorithm` environment undefined
```
! LaTeX Error: Environment algorithm undefined.
```
**Fix:** Add `\usepackage{algorithm}` and `\usepackage{algpseudocode}` to the preamble.

### Missing .sty file
```
```
! LaTeX Error: File `xxx.sty' not found.
```
**Fix:** See step 2 above.

### Table column count mismatch
```
Extra alignment tab has been changed to \cr.
```
**Fix:** The `\begin{tabular}` column spec has fewer columns than a row. Count the `&` separators in each row and match the spec (`{lcc}` = 3 columns, `{lccc}` = 4 columns, etc.).

```bash
# Count columns in a tabular block
grep -n '\\\\' main.tex | head -5
# The number of & plus 1 per row should match the {l..} spec
```

### Undefined citations
```
Package natbib Warning: Citation `xxx' on page Y undefined.
```
**Fix:** Ensure `\bibliography{references}` matches the `.bib` filename (no extension). Run tectonic twice (it auto-runs bibtex on the second pass). Empty `.bbl` means no citations were matched.

### Overfull \\hbox
```
Overfull \\hbox (X.XXpt too wide) in paragraph at lines Y--Z
```
Cosmetic warning in most cases. Only fix if text runs off the page edge. Common causes: long URLs in monospace, long unbreakable words.

**Fix with \\sloppy.** Add `\\sloppy` right after the environment (abstract, itemize) to allow looser line breaking. The badness will be ~2000-3000, well under the 10000 TeX allows:

```latex
\\begin{abstract}
\\sloppy
% text here...
\\end{abstract}

\\begin{itemize}\\sloppy
  \\item \\textbf{Long bullet text.} The sloppy flag allows line breaks...
\\end{itemize}
```

Only use `\\sloppy` scoped to the specific problematic paragraph/environment — never globally, or the whole paper's typography suffers.

### Headers clip body text at page boundaries (neurips.sty + fancyhdr)

```
Package fancyhdr Warning: \\headheight is too small (12.0pt):
(fancyhdr)                \\setlength{\\headheight}{20.55003pt}.
```

**Fix:** Add these two lines immediately after loading neurips.sty in the preamble:

```latex
\\usepackage[nonatbib, final]{neurips}
\\setlength{\\headheight}{20.55003pt}
\\addtolength{\\topmargin}{-8.55003pt}
```

The NeurIPS style sets `\\headheight=12.0pt` which is too small for fancyhdr's running header (author name + page number). Without the fix, the running header overlaps with body text at page boundaries — readers see "missing text" when a new page begins. The `\\addtolength{\\topmargin}` compensates so the text block stays vertically centered.

### Font shape undefined
```
LaTeX Font Warning: Font shape `TU/xxx/m/n' undefined
(Font)              using `TU/lmr/m/n' instead
```
Cosmetic — defaults to Computer Modern. No action needed for a working PDF.

## 11. Academic Paper Structure

Research papers (NeurIPS, arXiv, ICML, etc.) follow a specific structure that differs from technical documentation or RFCs.

### Standard section layout

For conference papers (NeurIPS format):
1. **Abstract** — 5-sentence formula: (1) what you built, (2) how it differs, (3) key evidence (negative controls), (4) headline numbers, (5) reproducibility claim
2. **Introduction** — the wound it closes (e.g. "context windows are coffins"), what prior work misses, your three contributions
3. **Architecture** — system pipeline with figure (TikZ), each component explained
4. **Negative Controls / Experiments** — the CENTRAL evidence section. Prove each mechanism is load-bearing by disabling it and showing the collapse. If you can't make the number drop on demand, it's a coincidence, not evidence.
5. **Benchmark Results** — multiple benchmarks, not just one. Include ablation studies and progression curves.
6. **Production Evidence** — live stats, latency, throughput
7. **Adversarial Audit** — third-party red-teaming of your methodology
8. **Related Work** — formal, 10+ citations, organized by school (external memory, RAG, LLM memory, CLS, spreading activation, federation)
9. **Limitations** — honest, specific, including licensing/storage tier constraints
10. **Conclusion** — restate the thesis, link to code
11. **Appendix** — hyperparameters, reproduction commands

For arXiv preprints (simpler format):
- Abstract → Rhythm Principle → Architecture → Negative Controls → Evaluation → Benchmark Progression → What Did NOT Work → Reproduction
- More concise, fewer tables, same evidence density

### Evidence methodology: Negative controls

This is the most important section in the paper. The principle: every claimed mechanism must have a quantifiable ablation that *necessarily* collapses the result.

| Capability | Control | Mazemaker | Δ |
|---|---|---|---|
| Hop-2 graph reasoning | 0.00 | 1.00 | +1.00 |
| Shuffled edges | — | 1.00→0.27 | collapse |
| Post-dream synthesis | 0.00 | 0.43 | +0.43 |
| Conflict supersession | 0.03 | 0.33 | +0.30 |
| Cross-session continuity | 0.06 | 0.62 | +0.56 |
| Lean vs skynet | 0.42 | 0.60 | +0.18 |

Testing motto: *"If you can't make the number drop on demand, you don't have evidence — you have a coincidence."*

### Storage tier language

When describing storage backends, use the product's licensing model language:
- SQLite → "Free for Lifetime under dual license" or "SQLite (public engine)"
- PostgreSQL + pgvector → "Pro/Team/Enterprise scale deployments"
- Never write "SQLite (production), Postgres (scale)" — that reads like a limitation, not a tiered offering

## 12. Gathering data from live systems before writing

Before writing or updating an academic paper, gather ALL canonical data from the live system first. This prevents stale numbers.

For Mazemaker papers (this user's canonical pattern):

```bash
# 1. Health + Stats
mazemaker_stats
mazemaker_health

# 2. Canonical benchmark facts
mazemaker_recall(query="canonical benchmark LongMemEval inception bench hindsight")
mazemaker_recall(query="mazemaker positioning what it is operating system")

# 3. Architecture facts
mazemaker_recall(query="mazemaker architecture seven phase dream engine sponge AFE")

# 4. Related work / comparison facts
mazemaker_recall(query="mazemaker related work comparison neural memory RAG MemGPT")

# 5. Think-traversals on key facts to find connected evidence
mazemaker_think(memory_id=<fact-id>)

# 6. Graph stats for production evidence
mazemaker_graph()
```

Compile the gathered data into a canonical reference before writing. Store updated stats as fact memories.

## 13. Updating papers with live data

When a LaTeX paper references system stats that have changed:

1. Gather current live numbers from system tools (e.g. mazemaker MCP for memory stats) — see Step 6
2. Use `patch` tool to update specific numbers in the .tex file — find-and-replace exact lines
3. Recompile with tectonic
4. Verify the PDF rendered correctly (check page count, key lines, grep for error signals)

### Stats update checklist
- Memory count
- Connection/edge count
- Dream cycle stats (strengthened, pruned, bridges)
- GPU cycles/hour
- DAE coverage %
- Benchmark results (R@5, R@10, MRR, etc.)
- Dataset sizes
- Dream sessions count
- AFE atomic facts count
- Adversarial audit status

## 14. Pitfalls

**Don't use pdflatex/xelatex/lualatex without verifying they exist.** Tectonic is the self-contained option. If you're on a system without any LaTeX, install tectonic — it's one package with no dependency chain.

**Verify hardware specs BEFORE writing them in the paper.** Do not guess or hallucinate GPU models. Run `nvidia-smi --query-gpu=name,memory.total --format=csv,noheader` or equivalent before including hardware details. Getting the GPU wrong (e.g. writing "RTX 3090" when the system has an RTX 4060 Ti) undermines all other hardware claims in the paper.

**.sty file downloaded as HTML.** Some URLs redirect to a webpage instead of serving the raw file. Always verify with `head -5 <file>.sty` — if it starts with `<!DOCTYPE html>` or `<html>`, it's not the actual style file. Find a different source URL.

**Download from GitHub raw URLs, not from conference websites.** Conference style file download pages often redirect to login or expired landing pages. Raw GitHub URLs (raw.githubusercontent.com/...) for known repos are more reliable.

**Tectonic can't use locally-installed texlive packages.** Even if you install `texlive-publishers` via pacman, tectonic uses its own bundle. Copied .sty files in the same directory as main.tex work fine.

**BibTeX auto-run may produce empty .bbl.** If references.bib exists but the generated .bbl is empty, the citation keys in the .tex don't match any entry in the .bib file. Check for case mismatches and typographic differences.

**Missing BibTeX entry from `\cite{xxx}` in .tex.** BibTeX output shows `Warning--I didn't find a database entry for "xxx"`. Add the missing entry to references.bib. For external papers (Generative Agents, etc.), add a `@misc` entry with the arXiv preprint. For internal/bookkeeping citations (e.g. `invariant:mazemaker-benchmark-invariants`), add a `@misc` entry with a `howpublished = {\url{...}}` pointing to the repo or docs.

**Duplicate `\appendix` causes undefined references.** Two consecutive `\appendix` lines in the .tex confuse LaTeX's section counter. All `\ref{sec:xxx}` inside the appendix resolve as "undefined" even though the label exists and the section compiles. Fix: remove the duplicate `\appendix` line. Verify with `grep -n "appendix" main.tex` — should show exactly one `\appendix` line.

.**rm -f main.* destroys main.tex too.** The glob `main.*` matches `main.tex` not just build artifacts. Use explicit filenames: `rm -f main.pdf main.aux main.log main.bbl main.blg main.out`.

.**patch tool escapes backslashes in .tex files.** The Hermes `patch` tool doubles backslashes in replacement strings. Use `execute_code` with Python for .tex edits instead, or `sed -i` in terminal with single-char delimiters.
