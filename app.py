import folium
import branca
import pathlib

import streamlit as st
import numpy as np
import pandas as pd
import geopandas as gpd

from datetime import datetime
from streamlit_folium import st_folium, folium_static

# App Settings
st.set_page_config(
    page_title="Customer Growth Dashboard",
    initial_sidebar_state="collapsed"
)

st.html(
    """
    <style>
        .stMainBlockContainer {
            max-width: 95rem;
        }
        .block-container {
            padding-top: 4rem;
            padding-bottom: 4rem;
        }
    </style>
    """
)

# Load Custom CSS
def load_css(file_path):
    with open(file_path) as f:
        st.html(f"<style>{f.read()}</style>")

css_path = pathlib.Path("assets/styles.css")
load_css(css_path)

# Load and Prepare Data
def calculate_growth(df):
    df["CUSTOMER_GROWTH"] = ((df["2024_CUST_NO"] - df["2019_CUST_NO"]) / df["2019_CUST_NO"]) * 100

    business_units = ["NMC", "REFI", "MPF", "MMU", "OTHERS"]
    for unit in business_units:
        df[f"2019_{unit}_TOTAL"] = df[[f"2019_{unit}_N", f"2019_{unit}_Y"]].sum(axis=1)
        df[f"2024_{unit}_TOTAL"] = df[[f"2024_{unit}_N", f"2024_{unit}_Y"]].sum(axis=1)

        df[f"{unit}_BOOKING_GROWTH"] = (
            (df[f"2024_{unit}_TOTAL"] - df[f"2019_{unit}_TOTAL"]) / df[f"2019_{unit}_TOTAL"]
        ) * 100

    df = df.replace([float("inf"), -float("inf")], 0).fillna(0)
    return df

@st.cache_data()
def preparing_data():
    shp_prov = gpd.read_file("Data Fix/LapakGIS_Batas_Provinsi_2024.json")
    shp_prov[["WADMPR"]] = shp_prov[["WADMPR"]].apply(lambda x: x.str.upper())
    shp_prov.set_crs(epsg=4326, inplace=True)

    shp_kab = gpd.read_file("Data Fix/LapakGIS_Batas_Kabupaten_2024.json")
    shp_kab[["WADMKK", "WADMPR"]] = shp_kab[["WADMKK", "WADMPR"]].apply(lambda x: x.str.upper())
    shp_kab.set_crs(epsg=4326, inplace=True)

    shp_kec = gpd.read_file("Data Fix/LapakGIS_Batas_Kecamatan_2024.json")
    shp_kec[["WADMKC", "WADMKK", "WADMPR"]] = shp_kec[["WADMKC", "WADMKK", "WADMPR"]].apply(lambda x: x.str.upper())
    shp_kec.set_crs(epsg=4326, inplace=True)

    df = pd.read_excel("Data Fix/Data Customer AGG.xlsx")
    agg_columns = df.columns[3:]

    df_prov = df.groupby("WADMPR")[agg_columns].sum().reset_index()
    df_prov = calculate_growth(df_prov)
    df_prov = pd.merge(
        left=shp_prov[["WADMPR", "geometry"]],
        right=df_prov,
        on="WADMPR",
        how="left"
    )

    df_kab = df.groupby(["WADMKK", "WADMPR"])[agg_columns].sum().reset_index()
    df_kab = calculate_growth(df_kab)
    df_kab = pd.merge(
        left=shp_kab[["WADMKK", "WADMPR", "geometry"]],
        right=df_kab,
        on=["WADMKK", "WADMPR"],
        how="left"
    )

    df_kec = df.groupby(["WADMKC", "WADMKK", "WADMPR"])[agg_columns].sum().reset_index()
    df_kec = calculate_growth(df_kec)
    df_kec = pd.merge(
        left=shp_kec[["WADMKC", "WADMKK", "WADMPR", "geometry"]],
        right=df_kec,
        on=["WADMKC", "WADMKK", "WADMPR"],
        how="left"
    )

    return df_prov, df_kab, df_kec

df_prov, df_kab, df_kec = preparing_data()

# Session States
bounds_start = df_prov.geometry.total_bounds
min_longitude_start, min_latitude_start, max_longitude_start, max_latitude_start = bounds_start

center_latitude_start = (min_latitude_start + max_latitude_start) / 2
center_longitude_start = (min_longitude_start + max_longitude_start) / 2
center_start = [center_latitude_start, center_longitude_start]

zoom_start = 5

if "clicked_province" not in st.session_state:
    st.session_state.clicked_province = None
if "clicked_city" not in st.session_state:
    st.session_state.clicked_city = None
if "clicked_district" not in st.session_state:
    st.session_state.clicked_district = None
if "center" not in st.session_state:
    st.session_state.center = center_start
if "zoom" not in st.session_state:
    st.session_state.zoom = zoom_start
if "reset_in_progress" not in st.session_state:
    st.session_state.reset_in_progress = False

# Map Stylings
def create_colormap(data, column="CUSTOMER_GROWTH"):
    return branca.colormap.LinearColormap(
        vmin=data[column].quantile(0.0),
        vmax=data[column].quantile(1.0),
        colors=["#ffffd9", "#41b6c4", "#081d58"],
        caption="Customer Growth (%)"
    )

def create_tooltip(level="province"):
    fields = [
        "WADMPR",
        "2019_CUST_NO",
        "2024_CUST_NO",
        "CUSTOMER_GROWTH",
    ]
    aliases = [
        "Province",
        "Total Customer as of 2019",
        "Total Customer as of 2024",
        "Customer Growth (%)"
    ]

    if level == "kabupaten":
        fields.insert(1, "WADMKK")
        aliases.insert(1, "City")
    elif level == "kecamatan":
        fields.insert(1, "WADMKK")
        fields.insert(2, "WADMKC")
        aliases.insert(1, "City")
        aliases.insert(2, "District")

    return folium.GeoJsonTooltip(
        fields=fields,
        aliases=aliases,
        localize=True,
        sticky=False,
        labels=True,
        style="""
            background-color: #F0EFEF;
            border: 2px solid black;
            border-radius: 3px;
            box-shadow: 3px;
        """,
    )

def style_function(feature, colormap):
    return {
        "fillColor": colormap(feature["properties"]["CUSTOMER_GROWTH"])
        if feature["properties"]["CUSTOMER_GROWTH"] is not None else "grey",
        "color": "#000000",
        "fillOpacity": 1,
        "weight": 1
    }

def style_function2(feature):
    return {
        "fillColor": "white",
        "color": "#000000",
        "fillOpacity": 1,
        "weight": 1
    }

def highlight_function(feature):
    return {
        "fillColor": "#000000",
        "color": "#000000",
        "fillOpacity": 0.8,
        "weight": 1
    }

# Map Interactions
def callback():
    if st.session_state.reset_in_progress:
        st.session_state.reset_in_progress = False
        return

    if st.session_state['province_map'].get('last_clicked'):
        last_active_drawing = st.session_state['province_map']['last_active_drawing']

        # Check if a city was clicked
        if 'WADMKK' in last_active_drawing['properties']:
            clicked_city = last_active_drawing['properties']['WADMKK']
            clicked_province = last_active_drawing['properties']['WADMPR']

            if clicked_city != st.session_state.get('clicked_city'):
                st.session_state.clicked_city = clicked_city
                st.session_state.clicked_province = clicked_province
                st.session_state.clicked_district = None

        # Check if a province was clicked
        elif 'WADMPR' in last_active_drawing['properties']:
            clicked_province = last_active_drawing['properties']['WADMPR']

            if clicked_province != st.session_state.get('clicked_province'):
                st.session_state.clicked_province = clicked_province
                st.session_state.clicked_city = None
                st.session_state.clicked_district = None

# Reset Map Views
def reset_to_province_view():
    st.session_state.clicked_province = None
    st.session_state.clicked_city = None
    st.session_state.clicked_district = None
    st.session_state.center = center_start
    st.session_state.zoom = zoom_start
    st.session_state.reset_in_progress = True

def reset_to_city_view():
    st.session_state.clicked_district = None
    st.session_state.clicked_city = None
    st.session_state.reset_in_progress = True

# Calculate Zoom
class FitBounds:
    def __init__(self, bounds, padding_top_left=None, padding_bottom_right=None, padding=None, max_zoom=None):
        self.bounds = bounds
        self.options = {
            'max_zoom': max_zoom,
            'padding_top_left': padding_top_left,
            'padding_bottom_right': padding_bottom_right,
            'padding': padding
        }
    
    def calculate_zoom(self, map_width=1026.67, map_height=450):
        from math import log2, pi, cos, radians
        
        southwest, northeast = self.bounds
        
        EARTH_RADIUS = 6378137
        
        lat_span = abs(northeast[0] - southwest[0])
        lon_span = abs(northeast[1] - southwest[1])
        
        lat_meters = lat_span * (111_000)
        lon_meters = lon_span * (111_000 * abs(cos(radians(southwest[0]))))
        
        resolution_lat = lat_meters / map_height
        resolution_lon = lon_meters / map_width
        resolution = max(resolution_lat, resolution_lon)
        
        zoom = log2(2 * pi * EARTH_RADIUS / (resolution * 256))
        
        if self.options['max_zoom'] is not None:
            zoom = min(zoom, self.options['max_zoom'])
        
        # return int(max(0, min(round(zoom), 18)))
        return zoom - 0.5

# Create Map
def display_map():
    if st.session_state.clicked_city:
        city_data = df_kab[
            (df_kab["WADMKK"] == st.session_state.clicked_city) &
            (df_kab["WADMPR"] == st.session_state.clicked_province)
        ]
        bounds = city_data.geometry.total_bounds

        folium_bounds = [
            [bounds[1], bounds[0]],
            [bounds[3], bounds[2]]
        ]

        center_latitude = (bounds[1] + bounds[3]) / 2
        center_longitude = (bounds[0] + bounds[2]) / 2
        current_center = [center_latitude, center_longitude]

        fit_bounds = FitBounds(folium_bounds)
        current_zoom = fit_bounds.calculate_zoom()
    elif st.session_state.clicked_province:
        province_data = df_prov[df_prov["WADMPR"] == st.session_state.clicked_province]
        bounds = province_data.geometry.total_bounds

        folium_bounds = [
            [bounds[1], bounds[0]],
            [bounds[3], bounds[2]]
        ]

        center_latitude = (bounds[1] + bounds[3]) / 2
        center_longitude = (bounds[0] + bounds[2]) / 2
        current_center = [center_latitude, center_longitude]

        fit_bounds = FitBounds(folium_bounds)
        current_zoom = fit_bounds.calculate_zoom()
    else:
        current_center = center_start
        current_zoom = zoom_start
        folium_bounds = [
            [min_latitude_start, min_longitude_start],
            [max_latitude_start, max_longitude_start]
        ]

    m = folium.Map(location=center_start, zoom_start=zoom_start)
    folium.TileLayer("CartoDB positron", name="Light Map", control=True).add_to(m)

    colormap = create_colormap(df_prov)

    folium.GeoJson(
        df_prov,
        style_function=lambda x: style_function(x, colormap),
        highlight_function=highlight_function,
        tooltip=create_tooltip("province")
    ).add_to(m)

    colormap.add_to(m)

    feature_group_to_add = folium.FeatureGroup(name="Cities")

    if st.session_state.clicked_province:
        city_data = df_kab[df_kab["WADMPR"] == st.session_state.clicked_province]

        feature_group_to_add.add_child(
            folium.GeoJson(
                df_prov,
                style_function=lambda x: style_function2(x),
                highlight_function=highlight_function,
                tooltip=create_tooltip("province")
            )
        )
        
        feature_group_to_add.add_child(
            folium.GeoJson(
                city_data,
                style_function=lambda x: style_function(x, colormap),
                highlight_function=highlight_function,
                tooltip=create_tooltip("kabupaten")
            )
        )

        if st.session_state.clicked_city:
            district_data = df_kec[
                (df_kec["WADMKK"] == st.session_state.clicked_city) &
                (df_kec["WADMPR"] == st.session_state.clicked_province)
            ]

            feature_group_to_add.add_child(
                folium.GeoJson(
                    city_data,
                    style_function=lambda x: style_function2(x),
                    highlight_function=highlight_function,
                    tooltip=create_tooltip("kabupaten")
                )
            )

            feature_group_to_add.add_child(
                folium.GeoJson(
                    district_data,
                    style_function=lambda x: style_function(x, colormap),
                    highlight_function=highlight_function,
                    tooltip=create_tooltip("kecamatan")
                )
            )

    st_folium(
        m,
        use_container_width=True,
        height=450,
        center=current_center,
        zoom=current_zoom,
        feature_group_to_add=feature_group_to_add,
        key='province_map',
        on_change=callback
    )

# Main App Layout
with st.container(key="styled_container"):
    col1 = st.columns(1)

    with col1[0]:
        with st.container():
            display_map()

        col1_map, col2_map, col3_map = st.columns([1, 0.3, 0.3])
        with col2_map:
            st.button(
                "Back to Province View",
                disabled=not st.session_state.clicked_province,
                use_container_width=True,
                on_click=reset_to_province_view,
                type="primary",
                icon="↩"
            )
        with col3_map:
            st.button(
                "Back to City View",
                disabled=not st.session_state.clicked_city,
                use_container_width=True,
                on_click=reset_to_city_view,
                type="primary",
                icon="↩"
            )