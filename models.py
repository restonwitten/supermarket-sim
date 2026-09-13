"""
Model objects for the supermarket operations simulation.

These mirror the workbook's three record-level sheets (Methodology &
Sources tab, "Workbook structure" note):

  Product Master               -> Product   (item-level record, keyed by UPC —
                                              what a UPC lookup / GS1 data pool
                                              would return)
  SKU Master +
  SKU Merchandising Attributes -> SKU       (the retailer's store-level
                                              inventory record; the two sheets
                                              are aligned 1:1 by row order and
                                              merged into one object here)
  Category Space Allocation    -> Category  (one per Department+Category)

Department Summary and Manufacturer Summary are workbook-level rollups, not
per-record data, so they aren't modeled as objects — they can be recomputed
from the objects below whenever needed.

SKU Master's product-owned columns (Department, Category, Brand, Pack Size,
Retail Price, Case Pack, Private Label, Perishable, Description) are VLOOKUP
formulas against Product Master, not independently authored data. The SKU
object keeps a `product` reference instead of duplicating those fields, so
there's exactly one place each fact lives — matching the workbook's own
source-of-truth design.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass
class Product:
    """One row of Product Master — the item-level source of truth, keyed by UPC."""

    upc: str
    gtin14: str
    sku_ref: str  # SKU this product is currently sold under (Product Master's "SKU (ref)")
    product_name: str
    brand: str
    manufacturer: str
    department: str
    category: str
    net_content: str
    country_of_origin: str
    private_label: bool
    perishable: bool
    units_per_case: int
    suggested_retail_price: float
    item_first_listed: Optional[date]


@dataclass
class SKU:
    """
    One store-level inventory record: SKU Master merged 1:1 with SKU
    Merchandising Attributes (both keyed by SKU id, same row order).
    """

    sku_id: str
    product: Product  # resolved via UPC — see Product Master lookup in the loader

    # --- SKU Master: store/inventory-only literals (not product-owned) ---
    uom: str
    sales_velocity: float  # units/store/week
    reorder_point: int  # units

    # --- SKU Merchandising Attributes ---
    package_width_in: float
    package_height_in: float
    package_depth_in: float
    shelf_orientation: str
    stackable: bool
    unit_cost: float
    gross_margin_pct: float
    current_facings_assigned: int
    current_linear_space_assigned_in: float
    assortment_status: str
    seasonality_window: str
    age_restricted: bool
    allergen_flag: str
    shelf_level_assigned: str
    secondary_display_eligible: bool

    # --- Convenience pass-throughs to the product-owned fields, so callers
    #     don't have to chain through `.product` for the common ones. These
    #     are properties (derived, not stored) to keep Product the single
    #     source of truth. ---
    @property
    def department(self) -> str:
        return self.product.department

    @property
    def category(self) -> str:
        return self.product.category

    @property
    def brand(self) -> str:
        return self.product.brand

    @property
    def description(self) -> str:
        return self.product.product_name

    @property
    def retail_price(self) -> float:
        return self.product.suggested_retail_price

    @property
    def private_label(self) -> bool:
        return self.product.private_label

    @property
    def perishable(self) -> bool:
        return self.product.perishable

    @property
    def case_pack(self) -> int:
        return self.product.units_per_case


@dataclass
class Category:
    """One row of Category Space Allocation — one per Department+Category."""

    department: str
    category: str
    temperature_zone: str
    fixture_type: str
    secured_case_required: bool
    category_role: str
    sku_count: int
    avg_facings_per_sku: float
    min_facings_per_sku: int
    max_facings_per_sku: int
    allocated_linear_space_ft: float
    unallocated_linear_space_ft: float
    total_category_linear_space_ft: float
    space_utilization_pct: float
    sales_per_linear_ft_per_week: float
    space_elasticity_coefficient: float
    category_captain: bool
    private_label_space_target_pct: float
    last_reset_date: Optional[date]
    reset_cycle_months: int

    @property
    def key(self) -> tuple[str, str]:
        return (self.department, self.category)


@dataclass
class SupermarketModel:
    """Top-level container: the fully loaded simulation model."""

    products: dict[str, Product] = field(default_factory=dict)  # keyed by UPC
    skus: dict[str, SKU] = field(default_factory=dict)  # keyed by SKU id
    categories: dict[tuple[str, str], Category] = field(default_factory=dict)  # keyed by (Department, Category)

    def __len__(self) -> int:
        return len(self.skus)
