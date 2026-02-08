# Phase 3: Auto-Reindexing & Live Updates

## Overview

Add automatic reindexing capabilities to keep header index synchronized with file changes during active development sessions.

---

## Problem Statement

**Phase 2 limitation:**
- Index is static snapshot at time of `md-ledger index` call
- File edits invalidate line numbers in header_index
- User must manually reindex after changes
- Stale index leads to incorrect line ranges → wrong Read offsets

**Phase 3 solution:**
- Detect when indexed files have changed
- Automatically reindex on tool calls (lazy update)
- Optional: Watch mode for live file monitoring
- Maintain index freshness without manual intervention

---

## Core Features

### 1. Change Detection

**Mechanism: Timestamp + Checksum**

**Enhanced schema:**
```sql
ALTER TABLE header_index ADD COLUMN file_mtime TEXT;  -- File modification time
ALTER TABLE header_index ADD COLUMN file_hash TEXT;   -- Content hash (optional)
```

**Detection logic:**
```python
def is_stale(db, file_path: str) -> bool:
    """
    Check if indexed file has been modified.
    Compare file mtime against stored indexed_ts.
    """
    indexed_mtime = query_file_mtime(db, file_path)
    current_mtime = os.path.getmtime(file_path)
    return current_mtime > indexed_mtime
```

### 2. Lazy Reindexing

**Trigger: On any query command**

**Workflow:**
```bash
# User queries headers
md-ledger headers README.md

# Internal behavior:
1. Check if README.md is stale
2. If stale: silently reindex before returning results
3. Return fresh data
4. Log: "Reindexed README.md (modified since last index)"
```

**Implementation:**
```python
def headers_command(file: str):
    db = init_db()

    if is_stale(db, file):
        print(f"File modified, reindexing {file}...")
        reindex_file(db, file)

    tree = query_headers(db, file)
    print_tree(tree)
```

**Benefits:**
- Zero user intervention
- Index always fresh when accessed
- No wasted reindexing (only on actual query)

### 3. Watch Mode (Optional)

**Command:**
```bash
md-ledger watch <path>
md-ledger watch .  # Watch current directory
```

**Behavior:**
- Uses `watchdog` library (new dependency)
- Monitors `*.md` files for changes
- Auto-reindexes on file save
- Runs in background (daemon or foreground process)

**Use case:**
- Long dev sessions with frequent md edits
- CI/CD environments where index must stay current
- Multi-agent systems with shared index

**Implementation sketch:**
```python
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class MarkdownWatcher(FileSystemEventHandler):
    def on_modified(self, event):
        if event.src_path.endswith('.md'):
            reindex_file(db, event.src_path)
            print(f"Reindexed {event.src_path}")

# Start observer
observer = Observer()
observer.schedule(MarkdownWatcher(), path='.', recursive=True)
observer.start()
```

**Trade-offs:**
- **Pro**: Instant index updates, no staleness ever
- **Con**: Adds dependency (`watchdog`), background process overhead
- **Decision**: Make optional, lazy reindex is sufficient for most use cases

### 4. Diff-Based Incremental Reindex (Advanced)

**Problem with full reindex:**
- Large files (1000+ lines) take time to reparse
- Wastes compute if only one section changed

**Solution: Parse only changed regions**

**Algorithm:**
```python
def incremental_reindex(db, file_path: str):
    """
    1. Diff old vs new file content
    2. Identify changed line ranges
    3. Parse only headers in/near changed ranges
    4. Update affected rows in header_index
    5. Leave unchanged sections untouched
    """
    old_content = get_indexed_content(db, file_path)  # Cache or reconstruct
    new_content = read_file(file_path)

    diff = compute_diff(old_content, new_content)
    changed_ranges = extract_changed_ranges(diff)

    for range in changed_ranges:
        reparse_headers_in_range(db, file_path, range)
```

**Complexity:**
- Requires caching original file content or line hashes
- Diff computation overhead
- Boundary detection complexity (when to reparse parent sections)

**Decision: Phase 3 stretch goal, not MVP**
- Lazy reindex is sufficient for most files
- Only pursue if profiling shows reindex is bottleneck

---

## Implementation Plan

### Milestone 1: Change Detection (Core)

**Tasks:**
1. Add `file_mtime` column to `header_index` schema
2. Implement `is_stale()` function
3. Store file mtime during indexing
4. Unit tests for staleness detection

**Success criteria:**
- Correctly identifies modified files
- Handles missing files (deleted after index)
- Edge case: File modified, then reverted (same content, different mtime)

### Milestone 2: Lazy Reindex (Core)

**Tasks:**
1. Wrap all query commands with staleness check
2. Auto-reindex if stale, then proceed with query
3. Log reindex events (optional `--verbose` flag)
4. Integration tests for automatic reindexing

**Success criteria:**
- User queries always return fresh data
- No manual reindex needed after file edits
- Minimal performance overhead (< 100ms for typical files)

### Milestone 3: Watch Mode (Optional)

**Tasks:**
1. Add `watchdog` as optional dependency (`pip install md-ledger-tool[watch]`)
2. Implement file watcher with `watchdog.Observer`
3. Add `md-ledger watch` CLI command
4. Handle edge cases (rapid successive edits, deletions)

**Success criteria:**
- Watch mode runs without errors for 1-hour session
- Reindexes within 1 second of file save
- Graceful shutdown on Ctrl+C

### Milestone 4: Diff-Based Reindex (Stretch)

**Tasks:**
1. Profile reindex performance on large files (1000+ lines)
2. If bottleneck found, implement incremental reparse
3. Benchmark: Compare full vs incremental reindex times

**Success criteria:**
- 50%+ speedup on large file reindex
- Correctness: Incremental produces same result as full reindex

---

## Testing Strategy

**Staleness detection:**
- Test: Modify file, verify `is_stale()` returns True
- Test: Indexed file unchanged, `is_stale()` returns False
- Test: File deleted after index, handle gracefully

**Lazy reindex:**
- Test: Query stale file, verify auto-reindex triggered
- Test: Query fresh file, verify no reindex (performance)
- Test: Concurrent queries on stale file (race conditions)

**Watch mode:**
- Test: Save file, verify reindex triggered
- Test: Rapid edits (debouncing)
- Test: File deletion (remove from index)

---

## Configuration

**New config file: `.md-ledger.conf` (optional)**

```ini
[reindex]
enabled = true              # Enable lazy reindex (default: true)
log_events = false          # Log reindex actions (default: false)

[watch]
enabled = false             # Enable watch mode (default: false)
debounce_ms = 500           # Delay before reindex after edit
ignore_patterns = node_modules/*,*.tmp
```

---

## Performance Considerations

**Reindex cost:**
- Small files (< 100 lines): ~10ms
- Medium files (100-500 lines): ~50ms
- Large files (500-1000 lines): ~200ms

**Optimization strategies:**
1. **Cache parsed headers in memory** (session-level cache)
2. **Batch reindex** multiple files if many are stale
3. **Parallel processing** for independent files (multiprocessing)

**Acceptable overhead:**
- Lazy reindex adds < 200ms to query latency (imperceptible to user)
- Watch mode: < 1s from file save to reindex complete

---

## Migration Path

**For Phase 2 users:**
1. Pull Phase 3 update
2. Schema auto-migrates (adds `file_mtime` column)
3. Next `md-ledger index` populates mtime
4. Lazy reindex works automatically (no config needed)

**Opt-in watch mode:**
```bash
pip install md-ledger-tool[watch]
md-ledger watch .
```

**No breaking changes.**

---

## Success Metrics

**Correctness:**
- Zero stale data served to queries (100% fresh)
- No false positives (unnecessary reindexing)

**Performance:**
- Lazy reindex overhead < 200ms (95th percentile)
- Watch mode < 1s latency (file save → index updated)

**Usability:**
- Zero manual reindex commands in typical dev session
- Silent operation (no noise unless `--verbose`)

---

## Risks & Mitigations

**Risk: File thrashing (rapid edits)**
- **Mitigation**: Debounce watch mode (500ms delay)
- **Mitigation**: Lazy reindex only triggers on query (not every edit)

**Risk: Large file reindex slow**
- **Mitigation**: Profile and optimize parser if needed
- **Mitigation**: Incremental reindex (stretch goal)

**Risk: Concurrent access (race conditions)**
- **Mitigation**: SQLite handles concurrent reads/writes
- **Mitigation**: Add file locks if needed

**Risk: Dependency bloat (watchdog)**
- **Mitigation**: Make optional with `[watch]` extra
- **Mitigation**: Document that lazy reindex is sufficient for most users

---

## Open Questions

1. **Should we cache file content for diff-based reindex?**
   - Pro: Enables incremental updates
   - Con: Disk/memory overhead, staleness risk
   - **Decision**: Defer to stretch goal, measure need first

2. **How to handle file deletions?**
   - Option A: Remove from index immediately
   - Option B: Mark as "missing", keep metadata
   - **Decision**: Remove from index, user can re-add if file returns

3. **Should index include content hash for deduplication?**
   - Use case: Detect when file is edited then reverted (same content)
   - **Decision**: No, mtime-based is sufficient and simpler

---

## Timeline Estimate

**Milestone 1 (Change Detection)**: 2-3 days
**Milestone 2 (Lazy Reindex)**: 3-4 days
**Milestone 3 (Watch Mode)**: 4-5 days
**Milestone 4 (Incremental)**: TBD (stretch goal)

**Total Phase 3 Core (M1+M2)**: ~1 week
**Total with Watch Mode (M1+M2+M3)**: ~2 weeks

---

## Dependencies

**New (optional):**
- `watchdog>=2.0.0` for watch mode

**Existing:**
- All Phase 2 dependencies (stdlib only)

---

## Documentation Updates

**Files to update:**
1. **README.md**: Add auto-reindex and watch mode sections
2. **CLAUDE.md**: Update integration patterns
3. **CLAUDE_INTEGRATION.md**: Mention automatic freshness guarantee
4. **docs/ARCHITECTURE.md** (new): Explain reindex strategies

---

## Summary

Phase 3 transforms md-ledger from a **static snapshot tool** to a **live, self-maintaining index** that stays synchronized with file changes. Lazy reindex provides 90% of the value with minimal complexity; watch mode and incremental reindex are available for power users.

**Core principle:** Index should "just work" without user thinking about freshness.
