"""
Loads supermarket_operations_data.xlsx into the model objects declared in
models.py.

Uses pandas for bulk read (per the xlsx skill's guidance: bulk data in/out ->
pandas). pandas/openpyxl reads formula cells' cached values by default, so
SKU Master's VLOOKUP-derived columns (Department, Category, Brand, etc.)
come through as plain resolved values — no formula evaluation needed here.
The workbook must have been through recalc.py at least once for those cached
values to be present; if every SKU's product-owned field reads as NaN, that's
the symptom and re-running recalc.py on the source file is the fix.

As of this revision, SKU Merchandising (renamed from "SKU Merchandising
Attributes" — the "Attributes" was superfluous) no longer carries Current
Facings Assigned / Current Linear Space Assigned (in) / Shelf Level Assigned
— that assignment data lives once, on each SKU's Primary Shelf row in SKU
Placements (Facings / Linear Space Assigned (in) / the new Shelf Level
column). load_placements() reads the new Shelf Level column into
Placement.shelf_level.

load_skus() reads SKU Master only — it does NOT read SKU Merchandising.
Package dimensions, unit cost, gross margin, assortment status, and the
rest of that sheet's columns are loaded exclusively by
load_sku_merchandising(), into standalone SKU_Merchandising objects (dict
keyed by SKU id, on SupermarketModel.sku_merchandising). An earlier
revision merged this sheet onto SKU as well; that duplication has been
removed — SKU_Merchandising is now the sole source for these attributes.

--- Workbook path resolution ---

There is no local copy of the workbook checked into or synced into this
repo anymore (see README's "Installation" section for the history — this
replaces the old data/ directory + sync_data.py approach). resolve_
default_data_path() finds the workbook via two tiers, in order:

  1. The Claude project mount (/mnt/project/supermarket_operations_data.xlsx)
     — present only inside a Claude conversation with this project open.
     Read directly; nothing is copied.
  2. config.json's "data_path" key — for any other environment (local dev,
     a deployed server). Set once at install time; see README.

Resolution is deferred to call time (load_model()'s path=None default),
not baked into a module-level constant, so importing this module never
requires the workbook to be resolvable — only actually loading one does.
"""

from __future__ import annotations
import json
import os
from pathlib import Path
from datetime import date, datetime
from typing import Optional

import pandas as pd

from models import Product, SKU, Category, Placement, SKU_Merchandising, SupermarketModel

PROJECT_MOUNT_PATH = Path("/mnt/project/supermarket_operations_data.xlsx")
CONFIG_PATH = Path(__file__).parent / "config.json"


def resolve_default_data_path() -> Path:
    """
    Resolves the workbook path with no manual sync step required. See the
    module docstring for the two-tier order. Raises FileNotFoundError with
    actionable guidance if neither tier resolves to an existing file.
    """
    if PROJECT_MOUNT_PATH.exists():
        return PROJECT_MOUNT_PATH

    if CONFIG_PATH.exists():
        try:
            config = json.loads(CONFIG_PATH.read_text())
        except json.JSONDecodeError as e:
            raise FileNotFoundError(
                f"{CONFIG_PATH} exists but isn't valid JSON: {e}"
            ) from e
        data_path = config.get("data_path")
        if data_path:
            path = Path(data_path).expanduser()
            if path.exists():
                return path
            raise FileNotFoundError(
                f"config.json's \"data_path\" is set to '{data_path}', but no file "
                f"exists there. Update that value in {CONFIG_PATH}."
            )

    raise FileNotFoundError(
        "Could not locate the simulation workbook. Neither the Claude project "
        f"mount ({PROJECT_MOUNT_PATH}) nor {CONFIG_PATH} (\"data_path\" key) "
        "resolved to a file. See the README's 'Installation' section."
    )


def _yn_to_bool(val) -> bool:
    if isinstance(val, bool):
        return val
    return str(val).strip().upper() == "Y"


def _to_date(val) -> Optional[date]:
    if pd.isna(val) or val in (None, ""):
        return None
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    return pd.to_datetime(val).date()


def _clean_str(val) -> str:
    return "" if pd.isna(val) else str(val)


def _clean_str_or_none(val) -> Optional[str]:
    return None if pd.isna(val) else str(val)


def load_products(path: Path) -> dict[str, Product]:
    df = pd.read_excel(path, sheet_name="Product Master", dtype={"UPC (fictional)": str})
    products: dict[str, Product] = {}
    for d in df.to_dict(orient="records"):
        upc = str(d["UPC (fictional)"])
        products[upc] = Product(
            upc=upc,
            gtin14=str(d["GTIN-14 (fictional)"]),
            sku_ref=str(d["SKU (ref)"]),
            product_name=_clean_str(d["Product Name"]),
            brand=_clean_str(d["Brand"]),
            manufacturer=_clean_str(d["Manufacturer"]),
            department=_clean_str(d["Department"]),
            category=_clean_str(d["Category"]),
            net_content=_clean_str(d["Net Content"]),
            country_of_origin=_clean_str(d["Country of Origin"]),
            private_label=_yn_to_bool(d["Private Label"]),
            perishable=_yn_to_bool(d["Perishable"]),
            units_per_case=int(d["Units per Case"]),
            suggested_retail_price=float(d["Suggested Retail Price"]),
            item_first_listed=_to_date(d["Item First Listed"]),
        )
    return products


def load_skus(path: Path, products: dict[str, Product]) -> dict[str, SKU]:
    """
    Builds SKU from SKU Master alone. Does NOT read the SKU Merchandising
    sheet — those attributes (package dimensions, cost, margin, assortment
    status, etc.) live solely on SKU_Merchandising now; see
    load_sku_merchandising() and models.py's SKU / SKU_Merchandising
    docstrings for why.
    """
    master = pd.read_excel(path, sheet_name="SKU Master", dtype={"UPC (fictional)": str})

    skus: dict[str, SKU] = {}
    for m in master.to_dict(orient="records"):
        sku_id = str(m["SKU"])
        upc = str(m["UPC (fictional)"])
        product = products.get(upc)
        if product is None:
            raise KeyError(f"SKU {sku_id} references UPC {upc}, which is not in Product Master.")

        skus[sku_id] = SKU(
            sku_id=sku_id,
            product=product,
            uom=_clean_str(m["UOM"]),
            sales_velocity=float(m["Sales Velocity (units/store/wk)"]),
            reorder_point=int(m["Reorder Point (units)"]),
        )
    return skus


def load_sku_merchandising(path: Path, sku_master_order: list[str]) -> dict[str, SKU_Merchandising]:
    """
    Loads the SKU Merchandising sheet as its own standalone object per row,
    keyed by SKU id. This is now the sole loader for these attributes —
    load_skus() no longer reads this sheet at all (see its docstring).

    sku_master_order is SKU Master's SKU column, in its own row order (pass
    list(skus.keys()) from load_skus() — dict insertion order preserves it).
    The sheet is documented as row-order-aligned 1:1 to SKU Master (see
    README's per-SKU-sheet convention); that's verified here even though
    records are keyed by the sheet's own SKU column values (a lookup formula
    back to SKU Master) rather than by position, so a violation wouldn't
    silently corrupt this function's output — it would just mean the
    workbook invariant other per-SKU sheets rely on is broken.

    SKU and Description are themselves lookup formulas on this sheet (back
    to SKU Master), so they're read here the same as any other column —
    not re-derived — keeping this loader a direct, literal mirror of the
    sheet as it exists in the workbook.
    """
    df = pd.read_excel(path, sheet_name="SKU Merchandising")

    if len(df) != len(sku_master_order):
        raise ValueError(
            f"SKU Merchandising ({len(df)} rows) and SKU Master ({len(sku_master_order)} rows) "
            "are no longer aligned 1:1 — row-order alignment is broken."
        )
    sheet_order = df["SKU"].astype(str).tolist()
    mismatched = [i for i, (a, b) in enumerate(zip(sheet_order, sku_master_order)) if a != b]
    if mismatched:
        raise ValueError(
            f"SKU id mismatch between SKU Merchandising and SKU Master at row(s) {mismatched[:5]} "
            "— row-order alignment is broken."
        )

    records: dict[str, SKU_Merchandising] = {}
    for d in df.to_dict(orient="records"):
        sku_id = str(d["SKU"])
        records[sku_id] = SKU_Merchandising(
            sku_id=sku_id,
            description=_clean_str(d["Description"]),
            package_width_in=float(d["Package Width (in)"]),
            package_height_in=float(d["Package Height (in)"]),
            package_depth_in=float(d["Package Depth (in)"]),
            shelf_orientation=_clean_str(d["Shelf Orientation"]),
            stackable=_yn_to_bool(d["Stackable (Y/N)"]),
            unit_cost=float(d["Unit Cost ($)"]),
            gross_margin_pct=float(d["Gross Margin (%)"]),
            assortment_status=_clean_str(d["Assortment Status"]),
            seasonality_window=_clean_str(d["Seasonality Window"]),
            age_restricted=_yn_to_bool(d["Age-Restricted (Y/N)"]),
            allergen_flag=_clean_str(d["Allergen Flag"]),
            secondary_display_eligible=_yn_to_bool(d["Secondary/Impulse Display Eligible (Y/N)"]),
        )
    return records


def load_categories(path: Path) -> dict[tuple[str, str], Category]:
    df = pd.read_excel(path, sheet_name="Category Space Allocation")
    categories: dict[tuple[str, str], Category] = {}
    for d in df.to_dict(orient="records"):
        key = (_clean_str(d["Department"]), _clean_str(d["Category"]))
        categories[key] = Category(
            department=key[0],
            category=key[1],
            temperature_zone=_clean_str(d["Temperature Zone"]),
            fixture_type=_clean_str(d["Fixture Type"]),
            secured_case_required=_yn_to_bool(d["Secured/Locked Case Required (Y/N)"]),
            category_role=_clean_str(d["Category Role"]),
            sku_count=int(d["SKU Count"]),
            avg_facings_per_sku=float(d["Avg Facings per SKU"]),
            min_facings_per_sku=int(d["Min Facings per SKU"]),
            max_facings_per_sku=int(d["Max Facings per SKU"]),
            allocated_linear_space_ft=float(d["Allocated Linear Space (ft)"]),
            unallocated_linear_space_ft=float(d["Unallocated Linear Space (ft)"]),
            total_category_linear_space_ft=float(d["Total Category Linear Space (ft)"]),
            space_utilization_pct=float(d["Space Utilization (%)"]),
            sales_per_linear_ft_per_week=float(d["Sales per Linear Ft per Week ($)"]),
            space_elasticity_coefficient=float(d["Space Elasticity Coefficient"]),
            category_captain=_yn_to_bool(d["Category Captain (Y/N)"]),
            private_label_space_target_pct=float(d["Private Label Space Target (%)"]),
            last_reset_date=_to_date(d["Last Reset Date"]),
            reset_cycle_months=int(d["Reset Cycle (months)"]),
        )
    return categories


def load_placements(path: Path, skus: dict[str, SKU]) -> dict[str, Placement]:
    """
    Loads SKU Placements — a genuine one-to-many child table keyed by SKU
    (ref) as a foreign key, NOT row-order-aligned to SKU Master. Current-
    state-only: every row is an active placement. After loading, each
    Placement is appended to its parent SKU's `.placements` list.

    Shelf Level is a new column (as of this revision): Top/Middle/Bottom/
    Eye-Level for Primary Shelf and Cross-Merchandised rows, "Floor" for
    Secondary/Impulse Display rows (Floor Display fixture has no shelf-level
    position).
    """
    df = pd.read_excel(path, sheet_name="SKU Placements")
    placements: dict[str, Placement] = {}
    for d in df.to_dict(orient="records"):
        placement_id = str(d["Placement ID"])
        sku_id = str(d["SKU (ref)"])
        sku = skus.get(sku_id)
        if sku is None:
            raise KeyError(f"Placement {placement_id} references SKU {sku_id}, which is not in SKU Master.")

        placement = Placement(
            placement_id=placement_id,
            sku_id=sku_id,
            placement_type=_clean_str(d["Placement Type"]),
            location_description=_clean_str(d["Location Description"]),
            fixture_type=_clean_str(d["Fixture Type"]),
            facings=int(d["Facings"]),
            linear_space_assigned_in=float(d["Linear Space Assigned (in)"]),
            vendor_funded=_yn_to_bool(d["Vendor Funded (Y/N)"]),
            start_date=_to_date(d["Start Date"]),
            end_date=_to_date(d["End Date"]),
            shelf_level=_clean_str_or_none(d["Shelf Level"]),
        )
        placements[placement_id] = placement
        sku.placements.append(placement)
    return placements


def load_model(path: Optional[Path] = None) -> SupermarketModel:
    if path is None:
        path = resolve_default_data_path()
    products = load_products(path)
    skus = load_skus(path, products)
    sku_merchandising = load_sku_merchandising(path, list(skus.keys()))
    categories = load_categories(path)
    placements = load_placements(path, skus)
    return SupermarketModel(
        products=products,
        skus=skus,
        sku_merchandising=sku_merchandising,
        categories=categories,
        placements=placements,
    )


if __name__ == "__main__":
    model = load_model()
    print(f"Products:          {len(model.products)}")
    print(f"SKUs:              {len(model.skus)}")
    print(f"SKU Merchandising: {len(model.sku_merchandising)}")
    print(f"Categories:        {len(model.categories)}")
    print(f"Placements:        {len(model.placements)}")
    sample = next(iter(model.skus.values()))
    sample_merch = model.sku_merchandising[sample.sku_id]
    print(f"\nSample SKU: {sample.sku_id} — {sample.description} ({sample.brand}, {sample.department}/{sample.category})")
    print(f"  retail_price=${sample.retail_price}  margin={sample_merch.gross_margin_pct:.1%}  shelf={sample.shelf_level_assigned}")
    print(f"  placements: {len(sample.placements)}")

    multi = [s for s in model.skus.values() if len(s.placements) > 1]
    print(f"\nSKUs with more than one active placement: {len(multi)}")
    if multi:
        s = multi[0]
        print(f"  Example: {s.sku_id} — {s.description}")
        for p in s.placements:
            print(f"    {p.placement_type}: {p.location_description} ({p.facings} facings, shelf={p.shelf_level})")
