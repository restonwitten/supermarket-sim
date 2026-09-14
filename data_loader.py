"""
Loads Supermarket_operations_data.xlsx into the model objects declared in
models.py.

Uses pandas for bulk read (per the xlsx skill's guidance: bulk data in/out ->
pandas). pandas/openpyxl reads formula cells' cached values by default, so
SKU Master's VLOOKUP-derived columns (Department, Category, Brand, etc.)
come through as plain resolved values — no formula evaluation needed here.
The workbook must have been through recalc.py at least once for those cached
values to be present; if every SKU's product-owned field reads as NaN, that's
the symptom and re-running recalc.py on the source file is the fix.
"""

from __future__ import annotations
from pathlib import Path
from datetime import date, datetime
from typing import Optional

import pandas as pd

from models import Product, SKU, Category, Placement, SupermarketModel

DEFAULT_DATA_PATH = Path(__file__).parent / "data" / "supermarket_operations_data.xlsx"


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
    master = pd.read_excel(path, sheet_name="SKU Master", dtype={"UPC (fictional)": str})
    attrs = pd.read_excel(path, sheet_name="SKU Merchandising Attributes")

    # Both sheets are documented as aligned 1:1 by row order (see project
    # instructions). Verify before trusting positional merge.
    if len(master) != len(attrs):
        raise ValueError(
            f"SKU Master ({len(master)} rows) and SKU Merchandising Attributes "
            f"({len(attrs)} rows) are no longer aligned 1:1 — cannot merge by row order."
        )
    mismatched = (master["SKU"].reset_index(drop=True) != attrs["SKU"].reset_index(drop=True))
    if mismatched.any():
        bad_rows = mismatched[mismatched].index.tolist()[:5]
        raise ValueError(f"SKU id mismatch between sheets at row(s) {bad_rows} — row-order alignment is broken.")

    skus: dict[str, SKU] = {}
    for m, a in zip(master.to_dict(orient="records"), attrs.to_dict(orient="records")):
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
            package_width_in=float(a["Package Width (in)"]),
            package_height_in=float(a["Package Height (in)"]),
            package_depth_in=float(a["Package Depth (in)"]),
            shelf_orientation=_clean_str(a["Shelf Orientation"]),
            stackable=_yn_to_bool(a["Stackable (Y/N)"]),
            unit_cost=float(a["Unit Cost ($)"]),
            gross_margin_pct=float(a["Gross Margin (%)"]),
            current_facings_assigned=int(a["Current Facings Assigned"]),
            current_linear_space_assigned_in=float(a["Current Linear Space Assigned (in)"]),
            assortment_status=_clean_str(a["Assortment Status"]),
            seasonality_window=_clean_str(a["Seasonality Window"]),
            age_restricted=_yn_to_bool(a["Age-Restricted (Y/N)"]),
            allergen_flag=_clean_str(a["Allergen Flag"]),
            shelf_level_assigned=_clean_str(a["Shelf Level Assigned"]),
            secondary_display_eligible=_yn_to_bool(a["Secondary/Impulse Display Eligible (Y/N)"]),
        )
    return skus


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
        )
        placements[placement_id] = placement
        sku.placements.append(placement)
    return placements


def load_model(path: Path = DEFAULT_DATA_PATH) -> SupermarketModel:
    products = load_products(path)
    skus = load_skus(path, products)
    categories = load_categories(path)
    placements = load_placements(path, skus)
    return SupermarketModel(products=products, skus=skus, categories=categories, placements=placements)


if __name__ == "__main__":
    model = load_model()
    print(f"Products:   {len(model.products)}")
    print(f"SKUs:       {len(model.skus)}")
    print(f"Categories: {len(model.categories)}")
    print(f"Placements: {len(model.placements)}")
    sample = next(iter(model.skus.values()))
    print(f"\nSample SKU: {sample.sku_id} — {sample.description} ({sample.brand}, {sample.department}/{sample.category})")
    print(f"  retail_price=${sample.retail_price}  margin={sample.gross_margin_pct:.1%}  shelf={sample.shelf_level_assigned}")
    print(f"  placements: {len(sample.placements)}")

    multi = [s for s in model.skus.values() if len(s.placements) > 1]
    print(f"\nSKUs with more than one active placement: {len(multi)}")
    if multi:
        s = multi[0]
        print(f"  Example: {s.sku_id} — {s.description}")
        for p in s.placements:
            print(f"    {p.placement_type}: {p.location_description} ({p.facings} facings)")
