"""
Loads the simulation model and prints a summary of what was loaded.

Usage:
    python summarize_model.py [path/to/workbook.xlsx]

Defaults to data_loader.resolve_default_data_path() (Claude project mount,
then config.json) if no path is given.
"""

from __future__ import annotations
import sys
from collections import Counter
from pathlib import Path

from data_loader import load_model, resolve_default_data_path
from models import SupermarketModel


def summarize(model: SupermarketModel) -> str:
    lines: list[str] = []

    def add(line: str = "") -> None:
        lines.append(line)

    # --- Top-line counts ---
    add("=" * 60)
    add("SUPERMARKET SIMULATION MODEL — LOAD SUMMARY")
    add("=" * 60)
    add(f"Products:   {len(model.products):,}")
    add(f"SKUs:       {len(model.skus):,}")
    add(f"Categories: {len(model.categories):,}")
    add(f"Placements: {len(model.placements):,}")

    # --- Referential integrity ---
    skus_missing_product = [s.sku_id for s in model.skus.values() if s.product is None]
    sku_category_keys = {(s.department, s.category) for s in model.skus.values()}
    categories_with_no_sku = [
        f"{d}/{c}" for (d, c) in model.categories.keys() if (d, c) not in sku_category_keys
    ]
    sku_categories_not_in_alloc = sorted(sku_category_keys - set(model.categories.keys()))
    placements_missing_sku = [p.placement_id for p in model.placements.values() if p.sku_id not in model.skus]
    skus_missing_primary = [
        s.sku_id for s in model.skus.values()
        if not any(p.placement_type == "Primary Shelf" for p in s.placements)
    ]

    add()
    add("-" * 60)
    add("REFERENTIAL INTEGRITY")
    add("-" * 60)
    add(f"SKUs with unresolved product reference: {len(skus_missing_product)}")
    add(f"Categories in Space Allocation with 0 matching SKUs: {len(categories_with_no_sku)}")
    if categories_with_no_sku:
        for c in categories_with_no_sku[:10]:
            add(f"  - {c}")
        if len(categories_with_no_sku) > 10:
            add(f"  ... and {len(categories_with_no_sku) - 10} more")
    add(f"Department/Category pairs on SKUs missing from Space Allocation: {len(sku_categories_not_in_alloc)}")
    if sku_categories_not_in_alloc:
        for d, c in sku_categories_not_in_alloc[:10]:
            add(f"  - {d}/{c}")
        if len(sku_categories_not_in_alloc) > 10:
            add(f"  ... and {len(sku_categories_not_in_alloc) - 10} more")
    add(f"Placements with unresolved SKU reference: {len(placements_missing_sku)}")
    add(f"SKUs with no Primary Shelf placement: {len(skus_missing_primary)}")

    # --- SKUs by department ---
    dept_counts = Counter(s.department for s in model.skus.values())
    add()
    add("-" * 60)
    add("SKUs BY DEPARTMENT")
    add("-" * 60)
    for dept, count in dept_counts.most_common():
        pct = count / len(model.skus) * 100
        add(f"  {dept:<28} {count:>6,}  ({pct:5.1f}%)")

    # --- Private label / perishable / age-restricted flags ---
    n = len(model.skus)
    private_label = sum(1 for s in model.skus.values() if s.private_label)
    perishable = sum(1 for s in model.skus.values() if s.perishable)
    age_restricted = sum(1 for s in model.skus.values() if s.age_restricted)
    secondary_eligible = sum(1 for s in model.skus.values() if s.secondary_display_eligible)
    add()
    add("-" * 60)
    add("SKU FLAGS")
    add("-" * 60)
    add(f"  Private label:              {private_label:>6,}  ({private_label / n * 100:5.1f}%)")
    add(f"  Perishable:                 {perishable:>6,}  ({perishable / n * 100:5.1f}%)")
    add(f"  Age-restricted:             {age_restricted:>6,}  ({age_restricted / n * 100:5.1f}%)")
    add(f"  Secondary/impulse eligible: {secondary_eligible:>6,}  ({secondary_eligible / n * 100:5.1f}%)")

    # --- Assortment status breakdown ---
    status_counts = Counter(s.assortment_status for s in model.skus.values())
    add()
    add("-" * 60)
    add("ASSORTMENT STATUS")
    add("-" * 60)
    for status, count in status_counts.most_common():
        add(f"  {status:<28} {count:>6,}  ({count / n * 100:5.1f}%)")

    # --- Price / margin stats ---
    prices = [s.retail_price for s in model.skus.values()]
    margins = [s.gross_margin_pct for s in model.skus.values()]
    add()
    add("-" * 60)
    add("PRICE / MARGIN")
    add("-" * 60)
    add(f"  Retail price:  min ${min(prices):.2f}   max ${max(prices):.2f}   avg ${sum(prices) / n:.2f}")
    add(f"  Gross margin:  min {min(margins):.1%}   max {max(margins):.1%}   avg {sum(margins) / n:.1%}")

    # --- Categories ---
    role_counts = Counter(c.category_role for c in model.categories.values())
    total_allocated_ft = sum(c.allocated_linear_space_ft for c in model.categories.values())
    total_unallocated_ft = sum(c.unallocated_linear_space_ft for c in model.categories.values())
    add()
    add("-" * 60)
    add("CATEGORIES")
    add("-" * 60)
    add(f"  By role: " + ", ".join(f"{role}={count}" for role, count in role_counts.most_common()))
    add(f"  Total allocated linear space:   {total_allocated_ft:,.1f} ft")
    add(f"  Total unallocated linear space: {total_unallocated_ft:,.1f} ft")

    # --- Placements ---
    placement_type_counts = Counter(p.placement_type for p in model.placements.values())
    vendor_funded = sum(1 for p in model.placements.values() if p.vendor_funded)
    multi_placement_skus = [s for s in model.skus.values() if len(s.placements) > 1]
    add()
    add("-" * 60)
    add("PLACEMENTS")
    add("-" * 60)
    add(f"  By type: " + ", ".join(f"{t}={count}" for t, count in placement_type_counts.most_common()))
    add(f"  Vendor-funded:                 {vendor_funded:>6,}  ({vendor_funded / len(model.placements) * 100:5.1f}%)")
    add(f"  SKUs with >1 active placement: {len(multi_placement_skus):>6,}  ({len(multi_placement_skus) / n * 100:5.1f}%)")

    # --- Manufacturers (derived from products, no dedicated object type) ---
    manufacturers = Counter(p.manufacturer for p in model.products.values())
    add()
    add("-" * 60)
    add(f"MANUFACTURERS ({len(manufacturers)} distinct)")
    add("-" * 60)
    add("  Top 5 by product count:")
    for mfr, count in manufacturers.most_common(5):
        add(f"    {mfr:<45} {count:>5,}")

    add()
    add("=" * 60)
    return "\n".join(lines)


if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else resolve_default_data_path()
    model = load_model(path)
    print(summarize(model))
