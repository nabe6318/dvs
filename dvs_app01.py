import streamlit as st
import numpy as np
import AMD_Tools4 as amd

# DVR関数（積算温度モデル）
def DVR(Ta, Para=[10.0, 1050.0]):
    return (Ta - Para[0]) / Para[1] if Ta > Para[0] else 0.0

# --- タイトル ---
st.title("出穂日予測アプリ")
st.markdown("気温データと発育速度モデル（DVR）に基づいて出穂日を予測します。")

# --- 初期値 ---
default_para = [10.0, 1050.0]

# --- 緯度経度履歴管理 ---
if "location_history" not in st.session_state:
    st.session_state.location_history = []

# --- 緯度経度の入力 ---
st.subheader("地点情報")
col1, col2 = st.columns(2)
lat = col1.number_input("緯度 (latitude)", value=35.802075, format="%.6f")
lon = col2.number_input("経度 (longitude)", value=137.930848, format="%.6f")

# --- 緯度経度履歴に追加 ---
new_location = (round(lat, 6), round(lon, 6))
if new_location not in st.session_state.location_history:
    st.session_state.location_history.append(new_location)

# --- 履歴から選択 ---
selected = st.selectbox("過去の地点から選択", st.session_state.location_history)
if st.button("この地点を使用"):
    lat, lon = selected

# --- パラメータ入力 ---
st.subheader("モデルパラメータ")
base_temp = st.number_input("基準温度（℃）", value=default_para[0])
acc_temp = st.number_input("出穂到達積算温度（℃・日）", value=default_para[1])
dvs_start = st.number_input("初期DVS値", value=0.1)

# --- 期間の指定（今年の想定） ---
date_range = ['2024-05-20', '2024-09-30']
latlon_box = [lat, lat, lon, lon]

# --- 気象データの取得とDVS計算 ---
if st.button("出穂日を予測"):
    with st.spinner("データ取得中..."):
        data, tim, _, _ = amd.GetMetData("TMP_mea", date_range, latlon_box)
        Ta_series = data[:, 0, 0]  # 日平均気温の時系列
        para = [base_temp, acc_temp]

        DVS = dvs_start
        result = []
        for i, Ta in enumerate(Ta_series):
            DVS += DVR(Ta, Para=para)
            result.append((i, float(Ta), DVS))
            if DVS > 1.0:
                break

        # --- 結果の表示 ---
        st.success(f"出穂日: {tim[i].strftime('%Y-%m-%d')}")
        st.line_chart([r[2] for r in result], use_container_width=True)
        st.dataframe(
            {
                "日目": [r[0] for r in result],
                "気温": [f"{r[1]:.1f}" for r in result],
                "DVS": [f"{r[2]:.3f}" for r in result]
            },
            use_container_width=True
        )