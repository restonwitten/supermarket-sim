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

- `models.py` — dataclasses: `Product`, `SKU`, `SKU_Merchandising`, `Category`,
  `Placement`, `SupermarketModel`. Mirrors the workbook's record-level sheets; `SKU.product`
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
- `data_loader.py` — reads the workbook and builds the model objects.
  `resolve_default_data_path()` locates the workbook with no manual copy or
  sync step (see "Installation" below). Run directly (`python data_loader.py`)
  to sanity-check counts without starting the app.
- `app.py` — Streamlit entry point. Currently iteration 1: loads the model
  and displays it (metrics + browsable tables per object type, including a
  Placements tab). No simulation logic (events, ticking) yet.
- `config.example.json` — template for `config.json` (gitignored, install-
  specific). See "Installation" below.

## Installation

The app needs to find `supermarket_operations_data.xlsx` — the project's
authoritative workbook. There is no copy of it checked into or synced into
this repo. Path resolution (`data_loader.resolve_default_data_path()`)
checks two places, in order, every time the workbook is loaded:

1. **The Claude project mount** — `/mnt/project/supermarket_operations_data.xlsx`.
   Present automatically inside a Claude conversation with this project
   open; nothing to set up. If you're developing or running the app from
   inside such a conversation, you're done — skip step 2.
2. **`config.json`** — for any other environment (local dev machine, a
   deployed server). This is a one-time setup step, not something that
   runs on every launch:

   ```bash
   cp config.example.json config.json
   ```

   Then edit `config.json` and set `"data_path"` to the absolute path of
   your copy of `supermarket_operations_data.xlsx`:

   ```json
   {
     "data_path": "/absolute/path/to/supermarket_operations_data.xlsx"
   }
   ```

   `config.json` is gitignored — it's local to each install, not shared
   through the repo.

If neither the mount nor a valid `config.json` resolves to a real file,
`resolve_default_data_path()` raises `FileNotFoundError` with guidance
pointing back here.

## Running

```bash
pip install -r requirements.txt
streamlit run app.py
```

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

## SKU Merchandising (standalone entity)

The workbook's `SKU Merchandising Attributes` sheet was renamed to
`SKU Merchandising` (the `Attributes` was superfluous). It's loaded as its
own standalone object, `SKU_Merchandising` (field-for-field mirror of the
sheet, keyed by SKU id on `SupermarketModel.sku_merchandising`) — package
dimensions, unit cost, gross margin, assortment status, seasonality window,
age-restricted, allergen flag, and secondary-display eligibility all live
there now, and nowhere else. `SKU` (from `SKU Master` alone) no longer
carries any of these; `load_skus()` in `data_loader.py` doesn't read the
`SKU Merchandising` sheet at all — `load_sku_merchandising()` is the sole
loader for it.

An earlier revision merged this sheet onto `SKU` as well as loading it
standalone, as a deliberate first pass to see the entity on its own before
deciding what to prune. That decision has been made, in favor of keeping
`SKU` lean: look up merchandising attributes via
`model.sku_merchandising[sku_id]`, not on the `SKU` object.

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

A separate, tracked item: whether `SKU_Merchandising` as loaded (a direct
mirror of the `SKU Merchandising` sheet) is actually the right shape for
mutable simulation state, or just a staging point — e.g. a `Category`/
`Placement`-style split between what's static policy versus what an event
actually mutates at runtime. `SKU` no longer duplicates these fields (see
"SKU Merchandising" above), so that part is settled; what's still open is
`SKU_Merchandising`'s own shape, and that's a question for once the event
model makes clear what's actually mutable — hold off until then.
