# Engineering Scripts

Internal, ad hoc engineering tools — not shipped with the product, not part
of the automated test suite, not manual-QA assets for the user.

## m12_4_performance_gate.py

The M12.4 Performance Decision Gate benchmark referenced in
`HARDENING_BACKLOG.md` (finding #17 and #18). Generates fully synthetic data
(no real user data, no privacy concern) at two personal-use scale tiers in a
temporary on-disk SQLite database, times Learning History's "All Materials"
view and the related Export query path, and independently re-verifies 7
Overview metrics against ground truth computed directly from the persisted
rows.

Run it with:

```bash
.venv/Scripts/python.exe scripts/m12_4_performance_gate.py
```

Re-run this whenever:
- a real user reports Learning History or Export feeling slow;
- personal usage data volumes are expected to grow well past the STRESS
  tier's assumptions (see the script's `SCALES` dict);
- a future change touches `history_repository.py`'s `_ACTIVITY_UNION_SQL`
  or `export_service.build_export`'s per-material loop, to confirm the
  decision in `HARDENING_BACKLOG.md` still holds.

Nothing here modifies product code, the real application database, or any
committed data file — every run creates and deletes its own temporary
database.
