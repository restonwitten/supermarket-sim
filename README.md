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

- `models.py` — dataclasses: `Product`, `SKU`, `Category`, `SupermarketModel`.
  Mirrors the workbook's record-level sheets; `SKU.product` references
  `Product` rather than duplicating product-owned fields (matches the
  workbook's own VLOOKUP source-of-truth design).
- `data_loader.py` — reads `data/supermarket_operations_data.xlsx` and
  builds the model objects. Run directly (`python data_loader.py`) to
  sanity-check counts without starting the app.
- `app.py` — Streamlit entry point. Currently iteration 1: loads the model
  and displays it (metrics + browsable tables per object type). No
  simulation logic (events, ticking) yet.
- `data/supermarket_operations_data.xlsx` — working copy of the canonical
  workbook (source: the project's `Supermarket_operations_data.xlsx`).
  **Re-copy this file here whenever the canonical workbook changes** —
  it's not auto-synced.

## Running

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Not yet modeled

`Department Summary` and `Manufacturer Summary` sheets are workbook-level
rollups, not per-record data — no object type for them; recompute from
`SupermarketModel` if/when needed. `Methodology & Sources` is documentation,
not simulation data.

## Next steps

Scope the event model: what state changes, what triggers a tick vs. a user
action, what the UI needs to display — then build simulation logic on top
of these model objects.
