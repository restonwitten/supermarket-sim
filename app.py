"""
Supermarket Operations Simulation — Streamlit app.

Initial iteration: load the simulation data into model object instances
(models.py / data_loader.py) and confirm the load, with a simple browsing
view. No simulation logic (events, ticking, state changes) yet — that's
the next iteration, once the event model is scoped.
"""

import pandas as pd
import streamlit as st

from data_loader import load_model

st.set_page_config(page_title="Supermarket Operations Simulation", layout="wide")


@st.cache_resource
def get_model():
    return load_model()


model = get_model()

st.title("Supermarket Operations Simulation")
st.caption("Iteration 1: model objects loaded from the simulation data workbook.")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Products", len(model.products))
col2.metric("SKUs", len(model.skus))
col3.metric("Categories", len(model.categories))
col4.metric("Placements", len(model.placements))

st.divider()

tab_skus, tab_categories, tab_products, tab_placements = st.tabs(
    ["SKUs", "Categories", "Products", "Placements"]
)

with tab_skus:
    departments = sorted({sku.department for sku in model.skus.values()})
    dept_filter = st.selectbox("Department", ["All"] + departments)
    rows = [
        {
            "SKU": s.sku_id,
            "Description": s.description,
            "Brand": s.brand,
            "Department": s.department,
            "Category": s.category,
            "Retail Price": s.retail_price,
            "Sales Velocity (u/wk)": s.sales_velocity,
            "Shelf Level": s.shelf_level_assigned,
            "Facings": s.current_facings_assigned,
            "Assortment Status": s.assortment_status,
            "Active Placements": len(s.placements),
        }
        for s in model.skus.values()
        if dept_filter == "All" or s.department == dept_filter
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, height=500)

with tab_categories:
    rows = [
        {
            "Department": c.department,
            "Category": c.category,
            "Role": c.category_role,
            "Temp Zone": c.temperature_zone,
            "SKU Count": c.sku_count,
            "Allocated Space (ft)": c.allocated_linear_space_ft,
            "Space Utilization": c.space_utilization_pct,
            "Sales/Linear Ft/Wk": c.sales_per_linear_ft_per_week,
        }
        for c in model.categories.values()
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, height=500)

with tab_products:
    rows = [
        {
            "UPC": p.upc,
            "Product Name": p.product_name,
            "Brand": p.brand,
            "Manufacturer": p.manufacturer,
            "Department": p.department,
            "Category": p.category,
            "Private Label": p.private_label,
            "Suggested Retail Price": p.suggested_retail_price,
        }
        for p in model.products.values()
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, height=500)

with tab_placements:
    placement_types = sorted({p.placement_type for p in model.placements.values()})
    type_filter = st.selectbox("Placement Type", ["All"] + placement_types)
    rows = [
        {
            "Placement ID": p.placement_id,
            "SKU": p.sku_id,
            "Description": model.skus[p.sku_id].description,
            "Placement Type": p.placement_type,
            "Location": p.location_description,
            "Fixture Type": p.fixture_type,
            "Facings": p.facings,
            "Linear Space (in)": p.linear_space_assigned_in,
            "Vendor Funded": p.vendor_funded,
            "Start Date": p.start_date,
            "End Date": p.end_date,
        }
        for p in model.placements.values()
        if type_filter == "All" or p.placement_type == type_filter
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, height=500)
