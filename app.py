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

col1, col2, col3 = st.columns(3)
col1.metric("Products", len(model.products))
col2.metric("SKUs", len(model.skus))
col3.metric("Categories", len(model.categories))

st.divider()

tab_skus, tab_categories, tab_products = st.tabs(["SKUs", "Categories", "Products"])

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
