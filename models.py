"""
Model objects for the supermarket operations simulation.

These mirror the workbook's four record-level sheets (Methodology &
Sources tab, "Workbook structure" note):

  Product Master               -> Product    (item-level record, keyed by UPC —
                                               what a UPC lookup / GS1 data pool
                                               would return)
  SKU Master                   -> SKU        (the retailer's store-level
                                               inventory record — inventory-
                                               only literals: UOM, sales
                                               velocity, reorder point)
  SKU Merchandising            -> SKU_Merchandising (per-SKU merchandising
                                               attributes: physical footprint,
                                               cost/margin, assortment status —
                                               a standalone object, not merged
                                               onto SKU; see its docstring)
  Category Space Allocation    -> Category   (one per Department+Category)
  SKU Placements                -> Placement (many-to-one child of SKU — a SKU
                                               can have a Primary Shelf
                                               placement plus zero or more
                                               Secondary/Impulse Display or
                                               Cross-Merchandised placements
                                               active at once)

Department Summary and Manufacturer Summary are workbook-level rollups, not
per-record data, so they aren't modeled as objects — they can be recomputed
from the objects below whenever needed.

SKU Master's product-owned columns (Department, Category, Brand, Pack Size,
Retail Price, Case Pack, Private Label, Perishable, Description) are VLOOKUP
formulas against Product Master, not independently authored data. The SKU
object keeps a `product` reference instead of duplicating those fields, so
there's exactly one place each fact lives — matching the workbook's own
source-of-truth design.

SKU Placements is a genuine one-to-many child table, keyed by SKU (ref) as a
foreign key — NOT row-order-aligned to SKU Master the way SKU Merchandising
is. It's current-state-only (no historical log): a row's presence
IS its active status.

As of this revision, assigned facings, linear space, and shelf level are
NOT duplicated onto SKU Merchandising. They live once, on each
SKU's Primary Shelf placement row (SKU Placements columns Facings, Linear
Space Assigned (in), and the new Shelf Level column). SKU exposes them as
derived properties that read through to that row — see
SKU._primary_shelf_placement and the properties built on it below. This
replaces the prior design where SKU Merchandising Attributes carried
Current Facings Assigned / Current Linear Space Assigned (in) / Shelf Level
Assigned as separately-authored, duplicated values.
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
    One store-level inventory record, built from SKU Master alone.

    Package dimensions, unit cost, gross margin, assortment status, and the
    other merchandising attributes formerly duplicated here from the SKU
    Merchandising sheet now live solely on SKU_Merchandising (see below,
    and data_loader.load_sku_merchandising()) — look them up there via
    SupermarketModel.sku_merchandising[sku_id], not on SKU.
    """

    sku_id: str
    product: Product  # resolved via UPC — see Product Master lookup in the loader

    # --- SKU Master: store/inventory-only literals (not product-owned) ---
    uom: str
    sales_velocity: float  # units/store/week
    reorder_point: int  # units

    # --- Back-reference: all current placements of this SKU (Primary Shelf
    #     plus any Secondary/Impulse Display or Cross-Merchandised rows).
    #     Populated by the loader after SKU Placements is read — see
    #     data_loader.load_placements(). ---
    placements: list["Placement"] = field(default_factory=list)

    # --- Assigned facings / linear space / shelf level are derived from the
    #     SKU's Primary Shelf placement, not stored here — see module
    #     docstring. All three return None when the SKU currently has zero
    #     Primary Shelf placements (e.g. mid-regeneration, right after
    #     SupermarketModel.clear_placements() and before new placements are
    #     generated). More than one Primary Shelf placement on the same SKU
    #     is a genuine data-integrity violation, so that case raises rather
    #     than silently picking one. ---
    @property
    def _primary_shelf_placement(self) -> Optional["Placement"]:
        primaries = [p for p in self.placements if p.placement_type == "Primary Shelf"]
        if len(primaries) > 1:
            raise ValueError(
                f"SKU {self.sku_id} has {len(primaries)} Primary Shelf placements — expected at most 1."
            )
        return primaries[0] if primaries else None

    @property
    def current_facings_assigned(self) -> Optional[int]:
        p = self._primary_shelf_placement
        return p.facings if p else None

    @property
    def current_linear_space_assigned_in(self) -> Optional[float]:
        p = self._primary_shelf_placement
        return p.linear_space_assigned_in if p else None

    @property
    def shelf_level_assigned(self) -> Optional[str]:
        p = self._primary_shelf_placement
        return p.shelf_level if p else None

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
class SKU_Merchandising:
    """
    One row of SKU Merchandising (renamed from "SKU Merchandising
    Attributes" — the "Attributes" was superfluous), loaded as its own
    standalone object rather than merged into SKU.

    This is the sole home of these fields — SKU no longer carries package
    dimensions, unit cost, gross margin, assortment status, or the other
    merchandising attributes below; load_skus() in data_loader.py doesn't
    read this sheet at all. (An earlier revision loaded this sheet twice —
    once merged onto SKU, once standalone here — as a deliberate first
    pass to see the entity on its own before deciding what to prune; that
    decision is made now, in SKU's favor of staying lean.)
    """

    sku_id: str  # "SKU" column — a lookup formula back to SKU Master, read here as a literal
    description: str  # lookup formula back to SKU Master

    package_width_in: float
    package_height_in: float
    package_depth_in: float
    shelf_orientation: str
    stackable: bool
    unit_cost: float
    gross_margin_pct: float  # formula: (Retail Price - Unit Cost) / Retail Price
    assortment_status: str
    seasonality_window: str
    age_restricted: bool
    allergen_flag: str
    secondary_display_eligible: bool


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
class Placement:
    """
    One row of SKU Placements — a single, currently-active merchandising
    instance of a SKU (Primary Shelf, Secondary/Impulse Display, or
    Cross-Merchandised). Current-state-only: this row's existence IS its
    active status. There is no historical log and no Active flag — when a
    placement ends, its row is removed rather than flagged inactive.

    start_date/end_date drive *when* to remove a placement (an app-level
    tick/event action), not a retained history: end_date is typically null
    for Primary Shelf (no natural end) and set for time-boxed promotional
    placements (Secondary/Impulse Display).

    shelf_level is the assignment's vertical shelf position: "Top",
    "Middle", "Bottom", or "Eye-Level" for Primary Shelf and Cross-
    Merchandised (Wall Shelf) placements; "Floor" for Secondary/Impulse
    Display placements (Floor Display fixture), which have no shelf-level
    position to speak of. This is the sole home of that data — see module
    docstring.
    """

    placement_id: str
    sku_id: str  # FK to SKU.sku_id — resolved via loader, not row order
    placement_type: str  # "Primary Shelf" | "Secondary/Impulse Display" | "Cross-Merchandised"
    location_description: str
    fixture_type: str
    facings: int
    linear_space_assigned_in: float
    vendor_funded: bool
    start_date: Optional[date]
    end_date: Optional[date]
    shelf_level: Optional[str]


@dataclass
class SupermarketModel:
    """Top-level container: the fully loaded simulation model."""

    products: dict[str, Product] = field(default_factory=dict)  # keyed by UPC
    skus: dict[str, SKU] = field(default_factory=dict)  # keyed by SKU id
    sku_merchandising: dict[str, SKU_Merchandising] = field(default_factory=dict)  # keyed by SKU id
    categories: dict[tuple[str, str], Category] = field(default_factory=dict)  # keyed by (Department, Category)
    placements: dict[str, Placement] = field(default_factory=dict)  # keyed by Placement ID

    def __len__(self) -> int:
        return len(self.skus)

    def clear_placements(self) -> int:
        """
        Clears all placement ASSIGNMENT data: every active Placement row,
        model-wide. Since facings, linear space, and shelf level are no
        longer duplicated onto SKU (they're derived from the SKU's Primary
        Shelf placement — see SKU._primary_shelf_placement), clearing the
        placement collections is sufficient; SKU.current_facings_assigned /
        current_linear_space_assigned_in / shelf_level_assigned
        automatically read back as None once their SKU has zero placements.

        Does NOT touch standing placement policy/advice — Category
        min/max/avg facings, space elasticity, private-label space target —
        which is what a subsequent generation step reads from, not what it
        clears.

        In-memory only; the source workbook is never touched.

        Not exposed as a standalone user action in the app. Call only as
        the first internal step of a placement-generation operation, so the
        model is never left in a "cleared but not yet regenerated" state
        visible to a user mid-session.

        Returns the number of placements cleared.
        """
        count = len(self.placements)
        self.placements.clear()
        for sku in self.skus.values():
            sku.placements.clear()
        return count
