import streamlit as st
import numpy as np
import pandas as pd
import folium
from streamlit_folium import st_folium
import AMD_Tools4 as amd
from datetime import date

# --- DVRモデル ---
def DVR(Ta, Para=[10.0, 1050.0]):
    return (Ta - Para[0]) / Para[1] if Ta > Para[0] else 0.0

# --- アプリタイトル ---
st.set_page_config(layout="centered")
st.title("🌾 出穂日予測アプリ")
st.markdown("気象データとDVRモデルに基づいて、地点の出穂日を予測します。")

# --- 地図で地点を選択 ---
st.subheader("📍 地図から地点を選択")
m = folium.Map(location=[36.0, 137.0], zoom_start=6, control_scale=True)
m.add_child(folium.LatLngPopup())  # クリックした位置を表示
st_map = st_folium(m, height=500, width=700)

lat = lon = None
if st_map and st_map.get("last_clicked"):
    lat = round(st_map["last_clicked"]["lat"], 6)
    lon = round(st_map["last_clicked"]["lng"], 6)
    st.success(f"✅ 選択された地点：緯度 {lat}, 経度 {lon}")
else:
    st.info("地図をクリックして地点を選んでください。")

# --- モデルパラメータ設定 ---
st.subheader("⚙️ モデル設定")
col1, col2, col3 = st.columns(3)
with col1:
    base_temp = st.number_input("基準温度（℃）", value=10.0)
with col2:
    acc_temp = st.number_input("出穂到達積算温度（℃・日）", value=1050.0)
with col3:
    dvs_start = st.number_input("初期DVS値", value=0.1)

# --- 期間設定 ---
st.subheader("📅 期間の設定")
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("移植日（開始日）", value=date(2025, 5, 15))
with col2:
    end_date = st.date_input("予測終了日", value=date(2025, 9, 30))

# --- 出穂日予測実行 ---
if st.button("🌾 出穂日を予測する"):
    if lat is None or lon is None:
        st.error("地点を地図から選択してください。")
        st.stop()

    with st.spinner("気象データを取得中..."):
        date_range = [start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")]
        latlon_box = [lat, lat, lon, lon]

        try:
            data, tim, _, _ = amd.GetMetData("TMP_mea", date_range, latlon_box)
        except Exception as e:
            st.error(f"気象データの取得に失敗しました: {e}")
            st.stop()

        Ta_series = data[:, 0, 0]  # 温度時系列
        para = [base_temp, acc_temp]

        DVS = dvs_start
        result = []
        heading_day = None
        for i, Ta in enumerate(Ta_series):
            DVS += DVR(Ta, Para=para)
            result.append((i + 1, float(Ta), DVS))
            if DVS > 1.0:
                heading_day = tim[i]
                break

        # --- 結果表示 ---
        if heading_day:
            st.success(f"📅 出穂日予測：{heading_day.strftime('%Y-%m-%d')}（地点：緯度{lat}, 経度{lon}）")
        else:
            st.warning("⚠️ 出穂に到達しませんでした（期間内で DVS < 1.0）")

        # グラフと表
        st.subheader("📈 DVSの推移")
        st.line_chart([r[2] for r in result], use_container_width=True)

        st.subheader("📋 データテーブル")
        df = pd.DataFrame({
            "日目": [r[0] for r in result],
            "気温 (℃)": [round(r[1], 1) for r in result],
            "DVS": [round(r[2], 3) for r in result]
        })
        st.dataframe(df, use_container_width=True)