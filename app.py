# ── Imports & Setup (same as before) ─────────────────────────────────────────
import datetime
import math
import sqlite3
import uuid
from pathlib import Path

import folium
import numpy as np
import pandas as pd
import streamlit as st
from geopy.exc import GeocoderUnavailable, GeopyError
from geopy.geocoders import Nominatim
from PIL import Image
from streamlit_folium import st_folium

import db
from face_utils import cosine, get_embedding

st.set_page_config(page_title="Missing Person Finder", page_icon="🔍", layout="wide")

# Force dark mode (same CSS)...

# ── Constants & Session State ───────────────────────────────────────────────
ALLOWED_CODES = {"admin123", "rescue007", "verified2025"}
PHOTOS_DIR = Path("photos"); PHOTOS_DIR.mkdir(exist_ok=True)

if "user_id" not in st.session_state:
    st.session_state.update(user_id=None, username="", access_granted=False)

@st.cache_resource(show_spinner=False)
def get_geocoder():
    return Nominatim(user_agent="missing_person_finder")

geolocator = get_geocoder()

# ── Helper function for Folium maps ─────────────────────────────────────────
def show_map(m: folium.Map, *, h: int = 400, w: int = 700, key: str):
    """Safely render a Folium map inside Streamlit with a unique key."""
    st_folium(m, height=h, width=w, use_container_width=False, key=key)

# ── Login/Register Screen ────────────────────────────────────────────────────
def login_register_screen():
    st.subheader("🔐 Secure Access")
    access_code = st.text_input("Access Code", type="password")
    if not access_code:
        st.info("Provide the supervisor's access code to continue.")
        st.stop()
    if access_code not in ALLOWED_CODES:
        st.error("Invalid access code. Contact administrator.")
        st.stop()

    mode = st.radio("Select mode", ["Login", "Register"], horizontal=True)
    if mode == "Login":
        st.markdown("#### Log in to your account")
        u_login = st.text_input("Username", key="login_user")
        p_login = st.text_input("Password", type="password", key="login_pw")
        if st.button("🚪 Log in"):
            user_id = db.verify_user(u_login, p_login)
            if user_id:
                st.session_state.user_id = user_id
                st.session_state.username = u_login
                st.success("Welcome back 👋")
                st.rerun()
            else:
                st.error("Incorrect username or password.")
    else:
        st.markdown("#### Create a new account")
        u_reg = st.text_input("New username", key="reg_user")
        p_reg = st.text_input("New password", type="password", key="reg_pw")
        if st.button("📝 Register"):
            if db.create_user(u_reg, p_reg):
                st.success("Account created! You can now log in.")
            else:
                st.error("Username already exists. Try another one.")

if not st.session_state.get("user_id"):
    login_register_screen()
    st.stop()

# ── Main Tabs ────────────────────────────────────────────────────────────────
tabs = st.tabs(["📝 Register", "🔎 Search", "📂 My Cases", "🟢 Found Cases"])
user_id = st.session_state.user_id
username = st.session_state.username

# ── 1) REGISTER MISSING PERSON ──────────────────────────────────────────────
with tabs[0]:
    st.markdown("### 📝 Register Missing Person")
    st.info(f"Logged in as **{username}**")
    with st.form("register_form", clear_on_submit=True):
        col_pic, col_meta = st.columns([1, 2])
        with col_pic:
            img_file = st.file_uploader("Reference photo (frontal)", type=["jpg", "png"], key="register_pic")
        with col_meta:
            name = st.text_input("Full name*")
            age = st.number_input("Age*", 0, 120, step=1)
            gender = st.selectbox("Gender*", ["Male", "Female", "Other"])
            loc = st.text_input("Last seen location* (address / city)")
            date = st.date_input("Last seen date*", value=datetime.date.today())
            notes = st.text_area("Additional notes")

        st.markdown("#### Contact & Address")
        contact_name = st.text_input("Contact person name*")
        contact_number = st.text_input("Contact phone number*")
        relation = st.text_input("Relation to missing person")
        address = st.text_area("Full address", height=70)
        aadhaar = st.text_input("Aadhaar number (optional)")

        submitted = st.form_submit_button("💾 Save Record")

    if submitted:
        required = [img_file, name, age, gender, loc, contact_name, contact_number]
        if not all(required):
            st.error("Please fill all required fields (marked with *).")
            st.stop()

        gps_lat = gps_lon = None
        try:
            geo = geolocator.geocode(loc.strip())
            if geo:
                gps_lat, gps_lon = geo.latitude, geo.longitude
        except (GeocoderUnavailable, GeopyError):
            st.warning("⚠️ Geocoding unavailable – coordinates not saved")

        if not (gps_lat and gps_lon):
            st.warning("Couldn’t geocode the address – map preview skipped.")

        try:
            emb = get_embedding(img_file.read())
            photo_path = PHOTOS_DIR / f"{uuid.uuid4()}.jpg"
            photo_path.write_bytes(img_file.getbuffer())
            db.add_person({
                "name": name, "age": age, "gender": gender,
                "loc": loc, "gps_lat": gps_lat, "gps_lon": gps_lon,
                "date": str(date), "notes": notes,
                "photo_path": str(photo_path), "address": address,
                "contact_name": contact_name, "contact_number": contact_number,
                "aadhaar_number": aadhaar, "relation": relation,
            }, emb, user_id)
            st.success("✅ Record saved!")
            if gps_lat and gps_lon:
                st.markdown("#### 📍 Last Seen Location Map")
                m = folium.Map(location=[gps_lat, gps_lon], zoom_start=14)
                folium.Marker([gps_lat, gps_lon], tooltip=name).add_to(m)
                show_map(m, key="register_preview", h=400, w=700)

        except ValueError as e:
            st.error(str(e))

# ── 2) SEARCH BY PHOTO ───────────────────────────────────────────────────────
with tabs[1]:
    st.markdown("### 🔎 Search by Photo")
    q_file = st.file_uploader("Upload photo to search", type=["jpg", "png"], key="search_query_pic")
    strict = st.slider("Match strictness (HIGH = fewer matches)", 0.20, 0.60, 0.33, 0.01)

    if q_file:
        try:
            q_emb = get_embedding(q_file.read())
            matches = []
            for pid, nm, ag, gen, path, loc, gps_lat, gps_lon, emb_blob in db.all_persons():
                if cosine(q_emb, np.frombuffer(emb_blob, dtype=np.float32)) >= strict:
                    matches.append((pid, nm, ag, gen, path, loc, gps_lat, gps_lon))

            if matches:
                st.success(f"Found {len(matches)} potential match(es)")
                overview_coords = []

                for pid, nm, ag, gen, path, loc, gps_lat, gps_lon in matches:
                    with sqlite3.connect(db.DB_PATH) as conn:
                        rel, c_name, c_num, addr, aad = conn.execute(
                            "SELECT relation, contact_name, contact_number, address, aadhaar_number FROM persons WHERE id = ?",
                            (pid,)
                        ).fetchone()

                    masked_aad = f"XXXX‑XXXX‑{aad[-4:]}" if aad else "—"
                    if gps_lat and gps_lon:
                        overview_coords.append((gps_lat, gps_lon, nm))

                    with st.container():
                        col_img, col_info = st.columns([1, 3], gap="small")
                        with col_img:
                            st.image(Image.open(path), caption=f"ID {pid}", width=140)
                        with col_info:
                            st.markdown(
                                f"""**{nm}**, {ag} yrs — {gen}<br>
                                **Relation**: {rel or '—'}<br>
                                **Contact**: {c_name or '—'} ({c_num or '—'})<br>
                                **Address**: {addr or '—'}<br>
                                **Aadhaar**: {masked_aad}<br>
                                **Last seen**: {loc}""",
                                unsafe_allow_html=True,
                            )
                        if gps_lat and gps_lon:
                            m = folium.Map([gps_lat, gps_lon], zoom_start=11)
                            folium.Marker([gps_lat, gps_lon], popup=loc).add_to(m)
                            show_map(m, key=f"match_map_{pid}", h=200, w=260)
                    st.markdown("---")

                if overview_coords:
                    ov_map = folium.Map(location=[overview_coords[0][0], overview_coords[0][1]], zoom_start=5)
                    for lat, lon, title in overview_coords:
                        folium.Marker([lat, lon], popup=title).add_to(ov_map)
                    st.markdown("#### 🗺️ Overview of all matched locations")
                    show_map(ov_map, key="overview_map", h=250, w=350)
            else:
                st.info("No matches above threshold. Try lowering strictness.")
        except ValueError as err:
            st.error(str(err))

# ── 3) MY SUBMITTED CASES ─────────────────────────────────────────────────────
with tabs[2]:
    st.markdown("### 📂 My Submitted Cases")
    st.info(f"Showing records submitted by **{username}**")
    df = db.get_user_cases(user_id)
    if df.empty:
        st.warning("You have not submitted any cases yet.")
    else:
        for _, row in df.iterrows():
            with st.container():
                c1, c2 = st.columns([1, 3])
                with c1:
                    st.image(Image.open(row['photo_path']), width=140, caption=f"{row['name']}")
                with c2:
                    st.markdown(
                        f"**{row['name']}**, {row['age']} yrs — {row['gender']}  \n"
                        f"📍 Last seen: {row['loc']} on {row['date']}  \n"
                        f"📝 Notes: {row['notes'] or '—'}  \n"
                        f"📞 Contact: {row['contact_name'] or '—'} ({row['relation'] or '—'})  \n"
                        f"📱 {row['contact_number'] or '—'} | Aadhaar: {row['aadhaar_number'] or '—'}"
                    )
                    if row['gps_lat'] and row['gps_lon']:
                        m = folium.Map(location=[row['gps_lat'], row['gps_lon']], zoom_start=11)
                        folium.Marker(
                            [row['gps_lat'], row['gps_lon']],
                            popup=row['loc'],
                            tooltip="Last Known Location",
                        ).add_to(m)
                        st_folium(m, width=300, height=200)

                    # 🟢 Mark as Found button
                    if st.button(f"🟢 Mark '{row['name']}' as Found", key=f"found_btn_{row['id']}"):
                        db.mark_person_as_found(row["id"])
                        st.success(f"{row['name']} marked as found ✅")
                        st.rerun()
                st.markdown("---")

# ── 4) FOUND CASES ───────────────────────────────────────────────────────────
with tabs[3]:
    st.markdown("### 🟢 Found Cases (Resolved)")

    # Pull everything *you* marked as found (include photo_path for the card)
    conn = db.sqlite3.connect(db.DB_PATH)
    df_found = pd.read_sql_query(
        """
        SELECT id, name, age, gender, loc, gps_lat, gps_lon,
            date, notes, photo_path
        FROM found_persons
        WHERE created_by = ?
        ORDER BY date DESC
        """,
        conn,
        params=(user_id,),
    )
    conn.close()

    if df_found.empty:
        st.info("No cases marked as found yet.")
    else:
        # ---------- optional: one‑off CSS for the green cards ---------------
        st.markdown(
            """
            <style>
                .found-card {
                    background: #1b5e20;
                    border-radius: 14px;
                    padding: 1rem;
                    margin-bottom: 1.1rem;
                    box-shadow: 0 0 12px rgba(0,0,0,0.35);
                }
                .found-card h4, .found-card p, .found-card span {
                    color: #e8f5e9 !important;
                }
                .found-card small {
                    color: #a5d6a7 !important;
                    font-size: 0.83rem;
                }
                .delete-btn-container {
                    margin-top: 1rem;
                }
            </style>
            """,
            unsafe_allow_html=True,
        )

        for _, row in df_found.iterrows():
            with st.container():
                st.markdown('<div class="found-card">', unsafe_allow_html=True)

                col_img, col_info, col_map = st.columns([1, 2, 2])

                # 1️⃣  Photo
                with col_img:
                    if row["photo_path"]:
                        st.image(row["photo_path"], width=120, caption="Photo")
                    else:
                        st.markdown("<small>No photo on file</small>", unsafe_allow_html=True)

                # 2️⃣  Info block + delete button
                with col_info:
                    st.markdown(
                        f"""
                        <h4>✅ {row['name']}</h4>
                        <span>{row['age']} yrs — {row['gender']}</span><br>
                        <small>📍 Last seen: {row['loc']}</small><br>
                        <small>📅 {row['date']}</small><br>
                        """,
                        unsafe_allow_html=True,
                    )
                    if row["notes"]:
                        st.markdown(
                            f"<p style='margin-top:0.6rem;'>📝 {row['notes']}</p>",
                            unsafe_allow_html=True,
                        )

                    # Delete button with confirmation
                    with st.container():
                        if st.button(f"🗑️ Delete", key=f"delete_{row['id']}"):
                            db.delete_found_person(row["id"])
                            st.success(f"Deleted record of {row['name']}")
                            st.rerun()

                # 3️⃣  Map
                with col_map:
                    lat = row["gps_lat"]
                    lon = row["gps_lon"]
                    if lat is not None and lon is not None and not math.isnan(lat) and not math.isnan(lon):
                        m = folium.Map(
                            location=[lat, lon],
                            zoom_start=11,
                            tiles="CartoDB dark_matter",
                        )
                        folium.Marker(
                            [lat, lon],
                            tooltip=row["loc"],
                            icon=folium.Icon(color="green", icon="ok-sign"),
                        ).add_to(m)
                        show_map(m, h=180, w=260, key=f"found_map_{row['id']}")
                    else:
                        st.markdown("<small>— no coordinates —</small>", unsafe_allow_html=True)

                st.markdown("</div>", unsafe_allow_html=True)   # Close card
