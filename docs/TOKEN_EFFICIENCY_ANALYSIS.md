# Token Efficiency Analysis

Token consumption comparison across three approaches for common dev tasks on nlp-for-llm-corpus (47 files, 388KB total).

---

## Baseline Data

**Corpus stats:**
- Total files: 47 markdown files
- Total size: 388KB (~97,000 tokens at 4 bytes/token)
- Largest file: CHANGELOG.md (21KB, ~5,250 tokens)
- Average file: ~8KB (~2,000 tokens)

**Token estimation formula:**
- 1 token ≈ 4 bytes (conservative for markdown)
- Line ≈ 50 bytes ≈ 12-13 tokens

---

## Task 1: Update CHANGELOG.md (Add New Entry)

**Goal:** Add entry under latest version heading

### Approach 1: Blind Read All
```bash
Read(CHANGELOG.md)  # Full file
```
**Token cost:**
- Read entire file: 5,250 tokens
- **Total: 5,250 tokens**

### Approach 2: Smart Claude (Built-in Tools)
```bash
Grep(pattern="## \[", file="CHANGELOG.md", output_mode="content", -n=True)
# Returns: Line numbers of all version headers
Read(CHANGELOG.md, offset=1, limit=50)  # Read top section
```
**Token cost:**
- Grep results: ~500 tokens (all version headers with line numbers)
- Targeted Read: ~600 tokens (50 lines)
- **Total: ~1,100 tokens**
- **Savings: 79% vs blind**

### Approach 3: md-ledger
```bash
md-ledger headers CHANGELOG.md
# Shows: All 45 headers with line ranges
md-ledger find-section "unreleased"
# Returns: CHANGELOG.md:5-15 (H2 "[Unreleased]")
Read(CHANGELOG.md, offset=5, limit=10)
```
**Token cost:**
- Header tree: ~400 tokens (45 headers, structured)
- find-section result: ~50 tokens (single line)
- Targeted Read: ~120 tokens (10 lines)
- **Total: ~570 tokens**
- **Savings: 89% vs blind, 48% vs smart**

---

## Task 2: Find All "Directive Coding" Analysis

**Goal:** Locate all sections discussing directive coding methodology

### Approach 1: Blind Read All
```bash
# Read all 47 files to find relevant sections
Read(file1.md) + Read(file2.md) + ... + Read(file47.md)
```
**Token cost:**
- All files: 97,000 tokens
- **Total: 97,000 tokens**

### Approach 2: Smart Claude (Built-in Tools)
```bash
Grep(pattern="directive coding", path=".", output_mode="content", -C=5)
# Returns: All matches with 5 lines context
```
**Token cost:**
- Assume 10 matches across corpus
- Each match: ~15 lines (5 before + line + 5 after) = ~190 tokens
- Match metadata (file, line numbers): ~50 tokens per match
- **Total: ~2,400 tokens (10 matches × 240 tokens)**
- **Savings: 98% vs blind**

### Approach 3: md-ledger
```bash
md-ledger find-section "directive"
# Returns: directive_coding_sheet.md:2-589 (H1 "Directive Mode Validation - Human Coding Sheet")
#          M3_specification.md:22-33 (H3 "1. Directive Density & Complexity")
#          M3_specification.md:64-78 (H3 "M3.2: Directive & Request Analysis")

# Then targeted reads:
Read(directive_coding_sheet.md, offset=2, limit=50)  # First 50 lines for overview
Read(M3_specification.md, offset=22, limit=11)       # Section 1
Read(M3_specification.md, offset=64, limit=14)       # Section 2
```
**Token cost:**
- find-section results: ~200 tokens (3 results with metadata)
- Read 1: ~600 tokens (50 lines overview)
- Read 2: ~140 tokens (11 lines)
- Read 3: ~170 tokens (14 lines)
- **Total: ~1,110 tokens**
- **Savings: 99% vs blind, 54% vs smart**

---

## Task 3: Update decisions.md (Add Architecture Decision)

**Goal:** Add new decision to appropriate section

### Approach 1: Blind Read All
```bash
Read(docs/development/decisions.md)
```
**Token cost:**
- Full file: 5,457 tokens
- **Total: 5,457 tokens**

### Approach 2: Smart Claude (Built-in Tools)
```bash
Grep(pattern="^## ", file="docs/development/decisions.md", output_mode="content", -n=True)
# Find section headers
Read(docs/development/decisions.md, offset=1, limit=100)  # Read beginning
```
**Token cost:**
- Grep results: ~300 tokens (section headers)
- Targeted Read: ~1,200 tokens (100 lines)
- **Total: ~1,500 tokens**
- **Savings: 72% vs blind**

### Approach 3: md-ledger
```bash
md-ledger headers docs/development/decisions.md
# Shows all decision sections with line ranges
md-ledger find-section "architecture"
# Returns: decisions.md:150-200 (H2 "Architecture Decisions")
Read(docs/development/decisions.md, offset=150, limit=50)
```
**Token cost:**
- Header tree: ~250 tokens (21 headers)
- find-section result: ~50 tokens
- Targeted Read: ~600 tokens (50 lines)
- **Total: ~900 tokens**
- **Savings: 84% vs blind, 40% vs smart**

---

## Task 4: Multi-File Context (Understand Pipeline Architecture)

**Goal:** Understand how pipelines work across multiple architecture docs

### Approach 1: Blind Read All
```bash
Read(docs/reference/pipelines.md)
Read(docs/reference/cli_pipeline.md)
Read(docs/reference/architecture.md)
# ... read all docs that might be relevant
```
**Token cost:**
- Assume need to read 10 files to find relevant content
- Average file: 2,000 tokens
- **Total: ~20,000 tokens**

### Approach 2: Smart Claude (Built-in Tools)
```bash
Grep(pattern="pipeline", path="docs/reference", output_mode="files_with_matches")
# Returns: List of files containing "pipeline"
# Then read each:
Read(pipelines.md, offset=0, limit=100)
Read(cli_pipeline.md, offset=0, limit=100)
Read(architecture.md, offset=0, limit=100)
```
**Token cost:**
- Grep results: ~100 tokens (file list)
- Targeted reads: 3 files × 1,200 tokens = 3,600 tokens
- **Total: ~3,700 tokens**
- **Savings: 82% vs blind**

### Approach 3: md-ledger
```bash
md-ledger find-section "pipeline"
# Returns:
#   pipelines.md:10-25 (H2 "Pipeline Architecture")
#   cli_pipeline.md:15-40 (H2 "CLI Pipeline Design")
#   architecture.md:80-95 (H3 "Pipeline Execution")

# Targeted reads with context:
md-ledger headers pipelines.md  # Get full structure
Read(pipelines.md, offset=10, limit=15)
Read(cli_pipeline.md, offset=15, limit=25)
Read(architecture.md, offset=80, limit=15)
```
**Token cost:**
- find-section results: ~150 tokens
- Header tree (1 file): ~200 tokens
- Targeted reads: (15 + 25 + 15) lines × 13 tokens/line = ~715 tokens
- **Total: ~1,065 tokens**
- **Savings: 95% vs blind, 71% vs smart**

---

## Summary Table

| Task | Blind Read | Smart Claude | md-ledger | md-ledger Savings |
|------|-----------|--------------|-----------|-------------------|
| Update changelog | 5,250 | 1,100 | 570 | 89% vs blind, 48% vs smart |
| Find directive analysis | 97,000 | 2,400 | 1,110 | 99% vs blind, 54% vs smart |
| Update decisions | 5,457 | 1,500 | 900 | 84% vs blind, 40% vs smart |
| Multi-file pipeline context | 20,000 | 3,700 | 1,065 | 95% vs blind, 71% vs smart |

**Average savings:**
- md-ledger vs blind: **92% token reduction**
- md-ledger vs smart Claude: **53% token reduction**

---

## Why md-ledger Wins

### 1. Structural Awareness
- **Smart Claude:** Knows file content, must grep/parse structure
- **md-ledger:** Knows document structure upfront (header tree)

### 2. Provenance Context
- **Smart Claude:** Line numbers only
- **md-ledger:** Section boundaries + hierarchy ("H3 under H2 'Architecture'")

### 3. Multi-File Operations
- **Smart Claude:** Must grep each file, concatenate results
- **md-ledger:** Single find-section across all indexed files

### 4. Reduced Round-Trips
- **Smart Claude:** Often needs 2-3 tool calls (grep → inspect results → read)
- **md-ledger:** Often 1-2 tool calls (find-section → read)

---

## Real-World Session Simulation

**Scenario:** Developer needs to update milestone documentation

**Steps:**
1. Find current milestone status
2. Read relevant section
3. Update with new completion info
4. Cross-reference with roadmap
5. Update changelog

### Token Cost Breakdown

**Smart Claude approach:**
```
1. Grep("milestone", files_with_matches)               → 150 tokens
2. Read(milestone_1.md, offset=0, limit=200)           → 2,400 tokens
3. Edit + Write                                         → 0 tokens (output only)
4. Grep("roadmap", output_mode="content", -C=10)       → 800 tokens
5. Read(ROADMAP.md, offset=50, limit=100)              → 1,200 tokens
6. Read(CHANGELOG.md, offset=0, limit=50)              → 600 tokens
Total: ~5,150 tokens
```

**md-ledger approach:**
```
1. find-section("milestone 1")                          → 100 tokens
   Returns: milestone_1.md:50-120 (H2 "Milestone 1 Progress")
2. Read(milestone_1.md, offset=50, limit=70)            → 840 tokens
3. Edit + Write                                         → 0 tokens
4. find-section("roadmap")                              → 80 tokens
   Returns: ROADMAP.md:30-60 (H2 "2026 Roadmap")
5. Read(ROADMAP.md, offset=30, limit=30)                → 360 tokens
6. find-section("unreleased")                           → 50 tokens
   Returns: CHANGELOG.md:5-15 (H2 "[Unreleased]")
7. Read(CHANGELOG.md, offset=5, limit=10)               → 120 tokens
Total: ~1,550 tokens
```

**Session savings: 70% (3,600 tokens saved)**

Over a typical 10-task dev session: **36,000 tokens saved**

---

## Cost Implications

At Claude API pricing (as of 2026):
- Sonnet 4: ~$3 per million input tokens

**Per dev session (10 tasks):**
- Smart Claude: ~51,500 tokens → $0.15
- md-ledger: ~15,500 tokens → $0.05
- **Savings: $0.10 per session**

**Per month (20 sessions):**
- **Savings: $2.00**

**Per year (240 sessions):**
- **Savings: $24.00**

Not dramatic cost savings, but **significant quality-of-life improvement:**
- Faster responses (less data to process)
- Lower context window pressure
- Cleaner, more focused conversations
- Reduced API rate limiting risk

---

## Limitations

**md-ledger doesn't help when:**
1. Need to read full file anyway (reviewing entire doc)
2. Content spans multiple sections (narrative flow)
3. Section boundaries don't align with logical boundaries
4. First-time exploration (don't know what sections exist)

**Smart Claude still wins for:**
- Full-text content search (md-ledger only searches headers)
- Regex pattern matching within content
- Cross-section analysis (themes across document)

---

## Recommendation

**Best practice: Hybrid approach**

1. **Start with md-ledger** for structural navigation:
   ```bash
   md-ledger headers file.md  # Understand structure
   md-ledger find-section "target"  # Locate section
   ```

2. **Fall back to Grep** for content search:
   ```bash
   Grep("specific phrase", output_mode="content", -C=5)
   ```

3. **Use targeted Read** with offsets from either tool:
   ```bash
   Read(file.md, offset=X, limit=Y)
   ```

This combines structural awareness (md-ledger) with content search (Grep) for optimal token efficiency.
