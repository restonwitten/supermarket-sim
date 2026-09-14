# Supermarket Operations Simulation

Interactive Streamlit app simulating supermarket operations: displays the
state of the simulation's model and lets the user select aspects to view.
Will generate and respond to events (simulation-driven and user-driven).

## Stack

Python + Streamlit, browser-based, single-user/session state (see
conversation history for the tradeoffs against a FastAPI+WebSocket
alternative — revisit if the simulation ends up needing sub-second ticking
or multi-client sync).

## Structure

- `models.py` — dataclasses: `Product`, `SKU`, `Category`, `Placement`,
  `SupermarketModel`. Mirrors the workbook's record-level sheets; `SKU.product`
  references `Product` rather than duplicating product-owned fields (matches
  the workbook's own VLOOKUP source-of-truth design). `Placement` is the one
  exception to the workbook's row-order-alignment convention: it's a genuine
  one-to-many child of `SKU` (a SKU can have a Primary Shelf placement plus
  zero or more Secondary/Impulse Display or Cross-Merchandised placements
  active at once), keyed by a `SKU (ref)` foreign key rather than row
  position. `SKU.placements` is a back-reference list populated by the loader.
  `SKU.current_facings_assigned`, `.current_linear_space_assigned_in`, and
  `.shelf_level_assigned` are derived properties that read through to the
  SKU's Primary Shelf placement — see "SKU Placements" below for why that
  data lives there and not on `SKU` itself. `SupermarketModel.clear_placements()`
  clears all active placements model-wide (in-memory only); it's called
  internally as the first step of a placement-generation operation, not
  exposed as a standalone user action.
- `data_loader.py` — reads `data/supermarket_operations_data.xlsx` and
  builds the model objects. Run directly (`python data_loader.py`) to
  sanity-check counts without starting the app.
- `app.py` — Streamlit entry point. Currently iteration 1: loads the model
  and displays it (metrics + browsable tables per object type, including a
  Placements tab). No simulation logic (events, ticking) yet.
- `data/supermarket_operations_data.xlsx` — working copy of the canonical
  workbook (source: the project's `Supermarket_operations_data.xlsx`).
- `sync_data.py` — refreshes `data/` from the authoritative source and logs
  an md5 comparison either way. **Run this before every rebuild, review, or
  commit** — see "Keeping the data copy in sync" below. Don't assume the
  copy in `data/` is current just because it's present.

## Running

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Keeping the data copy in sync

`data/supermarket_operations_data.xlsx` is a **copy**, not a live link, of
the project's authoritative workbook. In a Claude conversation with this
project open, that source is mounted at
`/mnt/project/Supermarket_operations_data.xlsx` — a snapshot for that
conversation, not something Claude can detect changing mid-conversation.

Run this before touching the repo (rebuilding it, reviewing it, or
committing to it):

```bash
python sync_data.py            # compares md5 against the source; copies if stale
python sync_data.py --check    # report only, exit 1 if stale, don't copy
```

It always prints both md5 hashes, so "in sync" vs. "just copied over a
stale file" is visible in the output rather than assumed. If
`/mnt/project/...` isn't present (e.g. running outside that conversation
context), pass `--source /path/to/Supermarket_operations_data.xlsx`
explicitly.

## SKU Placements (many-to-one placement model)

A single SKU can be merchandised in more than one place at once — e.g., a
coffee bag on its regular shelf, on a manufacturer-funded floor display, and
in the store's in-store coffee shop, simultaneously. The workbook's `SKU
Placements` sheet models this as a proper one-to-many child table (FK on
`SKU (ref)`, not row-order-aligned to `SKU Master`) — the only sheet in the
workbook that breaks the row-order-alignment convention, since it's a real
one-to-many rather than a 1:1 sheet.

It's **current-state-only**: a row represents a placement that's active
right now. There's no historical log and no `Active (Y/N)` flag — a
placement's row existing *is* its active status. `Start Date`/`End Date`
exist to know *when* to remove a placement (a future simulation
event/tick action), not to retain history after removal; once a placement
ends, its row is deleted rather than flagged inactive.

Every SKU has exactly one `Primary Shelf` placement row. `Facings`, `Linear
Space Assigned (in)`, and `Shelf Level` are **assignment data that lives
only here**, on the placement — `SKU Merchandising Attributes` does not
duplicate them. (Earlier versions of this workbook did duplicate this data
as `Current Facings Assigned` / `Current Linear Space Assigned (in)` /
`Shelf Level Assigned` columns on `SKU Merchandising Attributes`; those
columns were removed once the object model moved to deriving them from the
SKU's Primary Shelf placement instead — see `models.py`'s `SKU` properties.)
`Shelf Level` is `Top`/`Middle`/`Bottom`/`Eye-Level` for `Primary Shelf` and
`Cross-Merchandised` (Wall Shelf) rows, and `Floor` for `Secondary/Impulse
Display` rows (Floor Display fixture has no shelf-level position). See the
workbook's `Methodology & Sources` sheet for the full write-up, including
the fictional generation assumptions (~35% of Secondary/Impulse-eligible
SKUs currently have an active display; ~18% of Coffee category SKUs are
cross-merchandised into an in-store coffee shop).

## Not yet modeled

`Department Summary` and `Manufacturer Summary` sheets are workbook-level
rollups, not per-record data — no object type for them; recompute from
`SupermarketModel` if/when needed. `Methodology & Sources` is documentation,
not simulation data.

## Next steps

Scope the event model: what state changes, what triggers a tick vs. a user
action, what the UI needs to display — then build simulation logic on top
of these model objects. A global placement-regeneration operation is the
next concrete candidate: it should call `SupermarketModel.clear_placements()`
as its first step, then generate new `Placement` rows (at minimum a new
Primary Shelf row per SKU) reading category-level policy from `Category`
(min/max/avg facings, space elasticity) as its input. Placement removal (an
expired `End Date`) is another concrete candidate once that logic exists.
