import streamlit as st
import numpy as np
import pandas as pd
import folium
from streamlit_folium import st_folium
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import date
import AMD_Tools4 as amd

# ============================================================
# DVR / DVS モデル
# ============================================================
def DVR(Ta, base=10.0, acc=1050.0):
    """日平均気温 Ta から日発育速度 DVR を計算（単純積算温度型）"""
    return (Ta - base) / acc if Ta > base else 0.0

# ============================================================
# DVS → ステージ判定（出穂=1.0、移植時DVS=0.1）
# ※ しきい値は提案どおり（後で修正しやすい）
# ============================================================
STAGE_RULES = [
    (0.10, "移植直後（活着期）"),
    (0.30, "分げつ開始期"),
    (0.55, "最高分げつ期"),
    (0.75, "幼穂形成期"),
    (0.90, "穂ばらみ期"),
    (1.00, "出穂期"),
    (1.05, "開花期"),
    (1.15, "乳熟期"),
    (1.30, "糊熟期"),
    (1.45, "黄熟期"),
    (1.60, "成熟期（刈取適期）"),
]

def stage_from_dvs(dvs: float) -> str:
    """DVS値から日本語ステージ名を返す"""
    stage = "（移植前）"
    for th, name in STAGE_RULES:
        if dvs >= th:
            stage = name
        else:
            break
    return stage

# ============================================================
# UI 設定
# ============================================================
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
    dvs_start = st.number_input("初期DVS値（移植時）", value=0.1)

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

            # 観測（推定）気温
            data, tim, _, _ = amd.GetMetData("TMP_mea", date_range, latlon_box)
            # 平年値
            norm, _, _, _ = amd.GetMetData("TMP_mea", date_range, latlon_box, cli=True)

        except Exception as e:
            st.error(f"データ取得エラー: {e}")
            st.stop()

    Ta_series = data[:, 0, 0]
    norm_series = norm[:, 0, 0]
    tim = pd.to_datetime(tim)

    DVS = float(dvs_start)
    cumsum_temp = 0.0
    heading_day = None

    records = []
    for i in range(len(Ta_series)):
        Ta = float(Ta_series[i])
        norm_Ta = float(norm_series[i])

        delta_dvs = DVR(Ta, base=base_temp, acc=acc_temp)
        DVS += delta_dvs

        # 参考：基準温度を超えた日のみ積算（元コード踏襲）
        if Ta > base_temp:
            cumsum_temp += Ta

        stage = stage_from_dvs(DVS)

        records.append((tim[i], Ta, norm_Ta, DVS, cumsum_temp, stage))

        if (DVS >= 1.0) and (heading_day is None):
            heading_day = tim[i]

    df = pd.DataFrame(records, columns=["日付", "気温", "平年値", "DVS", "累積温度", "ステージ"])

    # ============================================================
    # 結果表示：出穂日
    # ============================================================
    if heading_day is not None:
        st.success(f"📅 出穂日予測: {heading_day.strftime('%Y-%m-%d')}（DVS≥1.0）")
    else:
        st.warning("期間内に出穂しませんでした（DVS < 1.0）")

    # ============================================================
    # ステージ到達日の対応表（初日）
    # ============================================================
    stage_rows = []
    for th, name in STAGE_RULES:
        hit = df[df["DVS"] >= th].head(1)
        if len(hit) == 1:
            stage_rows.append({
                "ステージ": name,
                "しきい値DVS": th,
                "到達日": hit.iloc[0]["日付"].strftime("%Y-%m-%d"),
                "到達時DVS": float(hit.iloc[0]["DVS"]),
            })
        else:
            stage_rows.append({
                "ステージ": name,
                "しきい値DVS": th,
                "到達日": "",
                "到達時DVS": np.nan,
            })

    stage_df = pd.DataFrame(stage_rows)

    st.subheader("🗓️ DVSとステージ対応（到達日一覧）")
    st.dataframe(stage_df, use_container_width=True)

    stage_csv = stage_df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "📥 ステージ到達日一覧CSV",
        stage_csv,
        file_name="dvs_stage_table.csv",
        mime="text/csv"
    )

    # ============================================================
    # 折れ線グラフ（DVS推移：出穂後も含む）
    # ============================================================
    st.subheader("📈 DVS推移（出穂後も含む）")
    fig1, ax1 = plt.subplots()
    ax1.plot(df["日付"], df["DVS"], label="DVS")
    ax1.axhline(y=1.0, linestyle="--", label="出穂閾値（DVS=1.0）")
    ax1.set_xlabel("日付")
    ax1.set_ylabel("DVS")
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
    plt.xticks(rotation=45)
    ax1.legend()
    st.pyplot(fig1)

    # ============================================================
    # 折れ線グラフ（気温と平年値）
    # ============================================================
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

    # ============================================================
    # 累積温度グラフ
    # ============================================================
    st.subheader("🔥 出穂までの累積温度（参考）")
    fig3, ax3 = plt.subplots()
    ax3.plot(df["日付"], df["累積温度"])
    ax3.set_xlabel("日付")
    ax3.set_ylabel("累積温度（℃・日）")
    ax3.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
    plt.xticks(rotation=45)
    st.pyplot(fig3)

    # ============================================================
    # データ表示とCSVダウンロード（ステージ列つき）
    # ============================================================
    st.subheader("📋 予測データ（ステージ列つき）")
    st.dataframe(df, use_container_width=True)

    csv = df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "📥 予測データCSVダウンロード",
        csv,
        file_name="heading_prediction.csv",
        mime="text/csv"
    )
