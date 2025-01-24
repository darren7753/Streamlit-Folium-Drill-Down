import folium    
import branca
import pathlib

import streamlit as st    
import numpy as np    
import pandas as pd    
import geopandas as gpd    

from datetime import datetime    
from streamlit_folium import st_folium    

# App Settings    
st.set_page_config(    
    page_title="Dashboard Pertumbuhan Customer",    
    page_icon="Logo/FIFGROUP_KOTAK.png",
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

def load_css(file_path):
    with open(file_path) as f:
        st.html(f"<style>{f.read()}</style>")

css_path = pathlib.Path("assets/styles.css")
load_css(css_path)

# Data    
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
    # Map Data    
    shp_prov = gpd.read_file("Data Fix/LapakGIS_Batas_Provinsi_2024.json")    
    shp_prov[["WADMPR"]] = shp_prov[["WADMPR"]].apply(lambda x: x.str.upper())    
    shp_prov.set_crs(epsg=4326, inplace=True)    

    shp_kab = gpd.read_file("Data Fix/LapakGIS_Batas_Kabupaten_2024.json")    
    shp_kab[["WADMKK", "WADMPR"]] = shp_kab[["WADMKK", "WADMPR"]].apply(lambda x: x.str.upper())    
    shp_kab.set_crs(epsg=4326, inplace=True)    

    shp_kec = gpd.read_file("Data Fix/LapakGIS_Batas_Kecamatan_2024.json")    
    shp_kec[["WADMKC", "WADMKK", "WADMPR"]] = shp_kec[["WADMKC", "WADMKK", "WADMPR"]].apply(lambda x: x.str.upper())    
    shp_kec.set_crs(epsg=4326, inplace=True)    

    # Data    
    df = pd.read_excel("Data Fix/Data Customer AGG.xlsx")    
    agg_columns = df.columns[3:]    
        
    # Merging Data    
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

# Create colormaps    
def create_colormap(data, column="CUSTOMER_GROWTH"):    
    return branca.colormap.LinearColormap(    
        vmin=data[column].quantile(0.0),    
        vmax=data[column].quantile(1.0),    
        colors=["#ffffd9", "#41b6c4", "#081d58"],    
        caption="Customer Growth (%)"    
    )    

# Create tooltips    
def create_tooltip(level="province"):    
    fields = [
        "WADMPR",
        "2019_CUST_NO",
        "2024_CUST_NO",
        "CUSTOMER_GROWTH",
    ]    
    aliases = [
        "Province",
        "Total Customer As of 2019",
        "Total Customer As of 2024",
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

# Style function    
def style_function(feature, colormap):    
    return {    
        "fillColor": colormap(feature["properties"]["CUSTOMER_GROWTH"])     
            if feature["properties"]["CUSTOMER_GROWTH"] is not None else "lightgrey",    
        "color": "#000000",    
        "fillOpacity": 0.7,    
        "weight": 1    
    }    

# Highlight function    
def highlight_function(feature):    
    return {    
        "fillColor": "#000000",    
        "color": "#000000",    
        "fillOpacity": 0.5,    
        "weight": 1    
    }    

# Store the clicked state    
if "clicked_province" not in st.session_state:    
    st.session_state.clicked_province = None    
if "clicked_city" not in st.session_state:    
    st.session_state.clicked_city = None    
if "clicked_district" not in st.session_state:    
    st.session_state.clicked_district = None    

def update_titles_and_agg_vals():    
    global cust_title, agg_vals    
    if st.session_state.clicked_district:    
        cust_title = f"Customer Growth in {st.session_state.clicked_district}, {st.session_state.clicked_city}, {st.session_state.clicked_province}"     
        district_data = df_kec[    
            (df_kec["WADMPR"] == st.session_state.clicked_province) &     
            (df_kec["WADMKK"] == st.session_state.clicked_city) &    
            (df_kec["WADMKC"] == st.session_state.clicked_district)    
        ]    
        agg_vals = district_data.select_dtypes(include=np.number).sum(axis=0) if not district_data.empty else pd.Series({"2019_CUST_NO": 0, "2024_CUST_NO": 0})    
    elif st.session_state.clicked_city:    
        cust_title = f"Customer Growth in {st.session_state.clicked_city}, {st.session_state.clicked_province}"     
        city_data = df_kab[    
            (df_kab["WADMPR"] == st.session_state.clicked_province) &     
            (df_kab["WADMKK"] == st.session_state.clicked_city)    
        ]    
        agg_vals = city_data.select_dtypes(include=np.number).sum(axis=0) if not city_data.empty else pd.Series({"2019_CUST_NO": 0, "2024_CUST_NO": 0})    
    elif st.session_state.clicked_province:    
        cust_title = f"Customer Growth in {st.session_state.clicked_province}"      
        province_data = df_prov[df_prov["WADMPR"] == st.session_state.clicked_province]    
        agg_vals = province_data.select_dtypes(include=np.number).sum(axis=0) if not province_data.empty else pd.Series({"2019_CUST_NO": 0, "2024_CUST_NO": 0})    
    else:    
        # Default title and values when no province, city, or district is clicked    
        cust_title = "Customer Growth"     
        agg_vals = df_prov.select_dtypes(include=np.number).sum(axis=0)    

@st.fragment
def display_map():  
    # Initialize titles and growth    
    update_titles_and_agg_vals()  # Update titles and aggregated values based on current state    

    # Determine which data to display based on clicked states      
    if st.session_state.clicked_city:      
        # Kecamatan view      
        filtered_df_kec = df_kec[      
            (df_kec["WADMPR"] == st.session_state.clicked_province) &       
            (df_kec["WADMKK"] == st.session_state.clicked_city)      
        ]      
        data = filtered_df_kec      
        tooltip = create_tooltip("kecamatan")      
    elif st.session_state.clicked_province:      
        # Kabupaten view      
        filtered_df_kab = df_kab[df_kab["WADMPR"] == st.session_state.clicked_province]      
        data = filtered_df_kab      
        tooltip = create_tooltip("kabupaten")      
    else:      
        # Province view      
        data = df_prov      
        tooltip = create_tooltip("province")      

    # Calculate bounds from the GeoDataFrame      
    bounds = data.geometry.total_bounds      
    min_longitude, min_latitude, max_longitude, max_latitude = bounds      

    # Calculate center      
    center_latitude = (min_latitude + max_latitude) / 2      
    center_longitude = (min_longitude + max_longitude) / 2      
    center = [center_latitude, center_longitude]      

    # Create the map with center but without initial zoom      
    m = folium.Map(location=center)      
    folium.TileLayer("CartoDB positron", name="Light Map", control=False).add_to(m)      

    # Fit bounds to the data      
    m.fit_bounds(      
        [[min_latitude, min_longitude], [max_latitude, max_longitude]],      
        padding=[0, 0]      
    )      

    # Create colormap for current view      
    colormap = create_colormap(data)      

    # Add GeoJson layer      
    folium.GeoJson(      
        data,      
        style_function=lambda x: style_function(x, colormap),      
        highlight_function=highlight_function,      
        tooltip=tooltip      
    ).add_to(m)      

    # Add colormap to the map      
    colormap.add_to(m)      

    # Display the map      
    output = st_folium(m, use_container_width=True, height=450)      

    # Handle clicks and calculate titles
    if output["last_clicked"]:
        rerun_needed = False  # Flag to control rerun

        # District-level click handling
        if st.session_state.clicked_city:
            clicked_district = output["last_active_drawing"]["properties"]["WADMKC"]

            # Change district only if the new click differs
            if clicked_district != st.session_state.clicked_district:
                st.session_state.clicked_district = clicked_district
                rerun_needed = True
            else:
                # If clicking the same district, reset to city level
                # st.session_state.clicked_city = None
                # st.session_state.clicked_district = None
                rerun_needed = False

        # City-level click handling
        elif st.session_state.clicked_province:
            clicked_city = output["last_active_drawing"]["properties"]["WADMKK"]

            # Change city only if the new click differs
            if clicked_city != st.session_state.clicked_city:
                st.session_state.clicked_city = clicked_city
                st.session_state.clicked_district = None  # Reset district
                rerun_needed = True
            else:
                # If clicking the same city, reset to province level
                st.session_state.clicked_province = None
                st.session_state.clicked_city = None
                rerun_needed = True

        # Province-level click handling
        else:
            clicked_province = output["last_active_drawing"]["properties"]["WADMPR"]

            # Change province only if the new click differs
            if clicked_province != st.session_state.clicked_province:
                st.session_state.clicked_province = clicked_province
                st.session_state.clicked_city = None  # Reset city and district
                st.session_state.clicked_district = None
                rerun_needed = True

        # Only rerun if a state change occurred
        if rerun_needed:
            st.rerun()

    # Update titles and aggregated values based on current state    
    update_titles_and_agg_vals()    

    return cust_title, agg_vals       

# Display the Customer Growth Map Section  
with st.container(key="styled_container1"):
    col1 = st.columns(1)

    # Initialize agg_vals before using it  
    update_titles_and_agg_vals()
    total_cust_2019 = agg_vals["2019_CUST_NO"]  
    total_cust_2024 = agg_vals["2024_CUST_NO"]  
    cust_growth = ((total_cust_2024 - total_cust_2019) / total_cust_2019 * 100) if total_cust_2019 != 0 else 0  

    growth_color = '#0458af' if cust_growth > 0 else '#ff0000' if cust_growth < 0 else '#31333F'  
    growth_symbol = "▲" if cust_growth > 0 else "▼" if cust_growth < 0 else ""  

    with col1[0]:
        st.html(f'''  
            <div style="display: flex; justify-content: space-between; align-items: center;">  
                <div style="font-size: 18px; font-weight: bold; color: #0458af;">{cust_title}</div>  
                <div style="text-align: right; display: flex; align-items: center;">  
                    <div style="font-size: 16px; margin-right: 10px;">  
                        <strong>As of 2019</strong>: {int(total_cust_2019):,} | <strong>As of 2024</strong>: {int(total_cust_2024):,}  
                    </div>  
                    <div style="font-size: 18px; font-weight: bold; color: {growth_color};">  
                        {growth_symbol} {cust_growth:.2f}%  
                    </div>  
                </div>  
            </div>  
        ''')  

with st.container(key="styled_container2"):
    col1 = st.columns(1)

    with col1[0]:
        with st.container(key="map_container"):
            cust_title, agg_vals = display_map()  

    # Add navigation buttons  
    col1_map, col2_map, col3_map = st.columns([1, 0.25, 0.25])     
    with col2_map:      
        st.button(      
            "Back to Province View",      
            disabled=not st.session_state.clicked_province,      
            use_container_width=True,      
            on_click=(lambda: [      
                setattr(st.session_state, "clicked_province", None),       
                setattr(st.session_state, "clicked_city", None),    
                setattr(st.session_state, "clicked_district", None)
            ]) if st.session_state.clicked_province else None,      
            type="primary",
            icon="↩" 
        )     
    with col3_map:      
        st.button(      
            "Back to City View",      
            disabled=not st.session_state.clicked_city,      
            use_container_width=True,      
            on_click=(lambda: [      
                setattr(st.session_state, "clicked_city", None),    
                setattr(st.session_state, "clicked_district", None)
            ]) if st.session_state.clicked_city else None,      
            type="primary",
            icon="↩"
        )    