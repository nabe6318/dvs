import streamlit as st
import numpy as np
import AMD_Tools4 as amd
from datetime import date

# --- DVRモデル ---
def DVR(Ta, Para=[10.0, 1050.0]):
    return (Ta - Para[0]) / Para[1] if Ta > Para[0] else 0.0

# --- セッションステートに履歴を保存 ---
if "location_history" not in st.session_state:
    st.session_state.location_history = []  # 履歴 = [(name, lat, lon), ...]

st.title("🌾 出穂日予測アプリ")
st.markdown("気象データとDVRモデルに基づいて、地点の出穂日を予測します。")

# --- 入力: 新しい地点の登録 ---
st.subheader("📍 地点の入力")
with st.form(key="location_form"):
    place_name = st.text_input("地点名（例: 松本圃場）", value="圃場A")
    lat = st.number_input("緯度 (latitude)", format="%.6f", value=35.802075)
    lon = st.number_input("経度 (longitude)", format="%.6f", value=137.930848)
    submitted = st.form_submit_button("この地点を登録して使用")

    if submitted:
        new_entry = (place_name.strip(), round(lat, 6), round(lon, 6))
        if new_entry not in st.session_state.location_history:
            st.session_state.location_history.append(new_entry)
        st.session_state.selected_location = new_entry

# --- 過去の地点履歴から選択 ---
st.subheader("📚 過去の地点から選択")
if st.session_state.location_history:
    selected_label = st.selectbox(
        "地点を選択",
        options=[f"{name} ({lat}, {lon})" for name, lat, lon in st.session_state.location_history]
    )
    selected_index = [f"{n} ({la}, {lo})" for n, la, lo in st.session_state.location_history].index(selected_label)
    place_name, lat, lon = st.session_state.location_history[selected_index]
else:
    st.info("まだ地点が登録されていません。上で新しい地点を入力してください。")

# --- パラメータ設定 ---
st.subheader("⚙️ モデル設定")
base_temp = st.number_input("基準温度（℃）", value=10.0)
acc_temp = st.number_input("出穂到達積算温度（℃・日）", value=1050.0)
dvs_start = st.number_input("初期DVS値", value=0.1)

# --- 移植日と予測終了日 ---
st.subheader("📅 期間設定")
start_date = st.date_input("移植日（開始日）", value=date(2024, 5, 20))
end_date = st.date_input("予測終了日", value=date(2024, 9, 30))

# --- 出穂日予測ボタン ---
if st.button("🌾 出穂日を予測する"):
    with st.spinner("気象データを取得中..."):
        date_range = [start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")]
        latlon_box = [lat, lat, lon, lon]

        try:
            data, tim, _, _ = amd.GetMetData("TMP_mea", date_range, latlon_box)
        except Exception as e:
            st.error(f"気象データの取得に失敗しました: {e}")
            st.stop()

        Ta_series = data[:, 0, 0]  # 1点の温度時系列
        para = [base_temp, acc_temp]

        DVS = dvs_start
        result = []
        heading_day = None
        for i, Ta in enumerate(Ta_series):
            DVS += DVR(Ta, Para=para)
            result.append((i, float(Ta), DVS))
            if DVS > 1.0:
                heading_day = tim[i]
                break

        # --- 結果の表示 ---
        if heading_day:
            st.success(f"📅 出穂日: {heading_day.strftime('%Y-%m-%d')}（{place_name}）")
        else:
            st.warning("出穂に到達しませんでした（期間内でDVS < 1.0）")

        st.line_chart([r[2] for r in result], use_container_width=True)
        st.dataframe(
            {
                "日目": [r[0] for r in result],
                "気温": [f"{r[1]:.1f}" for r in result],
                "DVS": [f"{r[2]:.3f}" for r in result]
            },
            use_container_width=True
        )