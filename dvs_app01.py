import streamlit as st
import numpy as np
import pandas as pd
import folium
from streamlit_folium import st_folium
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import date
import AMD_Tools4 as amd

# --- DVRモデル定義 ---
def DVR(Ta, base=10.0, acc=1050.0):
    return (Ta - base) / acc if Ta > base else 0.0

# --- UI設定 ---
st.set_page_config(layout="wide")
st.title("🌾 出穂日予測アプリ")
st.markdown("地図から地点を選び、気象データとDVRモデルにより出穂日を予測します。")

# --- 地図から地点を取得 ---
st.subheader("📍 地図から地点を選択")
m = folium.Map(location=[36.0, 137.0], zoom_start=6)
m.add_child(folium.LatLngPopup())
map_data = st_folium(m, height=500, width=700)

lat = lon = None
if map_data and map_data.get("last_clicked"):
    lat = round(map_data["last_clicked"]["lat"], 6)
    lon = round(map_data["last_clicked"]["lng"], 6)
    st.success(f"緯度: {lat}, 経度: {lon}")
else:
    st.warning("地図をクリックして地点を選んでください。")

# --- パラメータ入力 ---
st.subheader("⚙️ モデル設定")
col1, col2, col3 = st.columns(3)
with col1:
    base_temp = st.number_input("基準温度（℃）", value=10.0)
with col2:
    acc_temp = st.number_input("出穂到達積算温度（℃・日）", value=1050.0)
with col3:
    dvs_start = st.number_input("初期DVS値", value=0.1)

# --- 期間設定 ---
st.subheader("📅 予測期間の指定")
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("移植日", value=date(2025, 5, 15))
with col2:
    end_date = st.date_input("予測終了日", value=date(2025, 9, 30))

# --- 出穂日予測実行 ---
if st.button("🌾 出穂日を予測する"):
    if lat is None or lon is None:
        st.error("地点が選択されていません。")
        st.stop()

    with st.spinner("気象データを取得中..."):
        try:
            date_range = [start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")]
            latlon_box = [lat, lat, lon, lon]
            data, tim, _, _ = amd.GetMetData("TMP_mea", date_range, latlon_box)
            norm, _, _, _ = amd.GetMetData("TMP_mea", date_range, latlon_box, cli=True)
        except Exception as e:
            st.error(f"データ取得エラー: {e}")
            st.stop()

    Ta_series = data[:, 0, 0]
    norm_series = norm[:, 0, 0]
    tim = pd.to_datetime(tim)

    DVS = dvs_start
    cumsum_temp = 0.0
    heading_day = None

    records = []
    for i in range(len(Ta_series)):
        Ta = Ta_series[i]
        norm_Ta = norm_series[i]
        delta_dvs = DVR(Ta, base=base_temp, acc=acc_temp)
        DVS += delta_dvs
        if Ta > base_temp:
            cumsum_temp += Ta
        records.append((tim[i], Ta, norm_Ta, DVS, cumsum_temp))
        if DVS > 1.0 and heading_day is None:
            heading_day = tim[i]

    df = pd.DataFrame(records, columns=["日付", "気温", "平年値", "DVS", "累積温度"])

    # --- 結果表示 ---
    if heading_day:
        st.success(f"📅 出穂日予測: {heading_day.strftime('%Y-%m-%d')}")
    else:
        st.warning("期間内に出穂しませんでした（DVS < 1.0）")

    # --- 折れ線グラフ（DVS推移） ---
    st.subheader("📈 DVS推移（出穂後も含む）")
    fig1, ax1 = plt.subplots()
    ax1.plot(df["日付"], df["DVS"], label="DVS", color='green')
    ax1.axhline(y=1.0, color="red", linestyle="--", label="出穂閾値")
    ax1.set_xlabel("日付")
    ax1.set_ylabel("DVS")
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
    plt.xticks(rotation=45)
    ax1.legend()
    st.pyplot(fig1)

    # --- 折れ線グラフ（気温と平年値） ---
    st.subheader("🌡️ 気温 vs 平年値")
    fig2, ax2 = plt.subplots()
    ax2.plot(df["日付"], df["気温"], label="気温", marker='o')
    ax2.plot(df["日付"], df["平年値"], label="平年値", linestyle='--')
    ax2.set_xlabel("日付")
    ax2.set_ylabel("気温（℃）")
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
    plt.xticks(rotation=45)
    ax2.legend()
    st.pyplot(fig2)

    # --- 累積温度グラフ ---
    st.subheader("🔥 出穂までの累積温度")
    fig3, ax3 = plt.subplots()
    ax3.plot(df["日付"], df["累積温度"], color='orange')
    ax3.set_xlabel("日付")
    ax3.set_ylabel("累積温度（℃・日）")
    ax3.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
    plt.xticks(rotation=45)
    st.pyplot(fig3)

    # --- データ表示とCSVダウンロード ---
    st.subheader("📋 予測データ")
    st.dataframe(df)

    csv = df.to_csv(index=False).encode("utf-8-sig")
    st.download_button("📥 CSVダウンロード", csv, file_name="heading_prediction.csv", mime="text/csv")