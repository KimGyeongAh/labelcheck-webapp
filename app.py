import streamlit as st
import os
import json
import pandas as pd
from datetime import date
from io import BytesIO
from pdf2image import convert_from_bytes
from PIL import Image
import base64
import uuid

st.markdown("""
<style>
div[data-testid="column"]:first-child {
  position: sticky;
  top: 80px;
  align-self: flex-start;
  height: calc(100vh - 100px);
  overflow: auto;
  border: 1px solid #eee;
  padding: 10px;
  border-radius: 8px;
  background: white;
}
</style>
""", unsafe_allow_html=True)

# -----------------------------
# 기본 설정
# -----------------------------
st.set_page_config(layout="wide")
st.markdown("## 📝 패키지 라벨 표시 기재사항 체크리스트")

# --- 라디오 버튼 하이라이트 색상 CSS ---
st.markdown(
    """
<style>
div[role="radiogroup"] > label {
    padding: 4px 8px;
    border-radius: 6px;
    margin-right: 6px;
    margin-bottom: 2px;
}
div[role="radiogroup"] > label:nth-child(1) {
    background-color: #e6ffed;
    border: 1px solid #b3f0c2;
}
div[role="radiogroup"] > label:nth-child(2) {
    background-color: #ffeef0;
    border: 1px solid #ffccd5;
}
div[role="radiogroup"] > label:nth-child(3) {
    background-color: #f3f4f6;
    border: 1px solid #d1d5db;
}
div[role="radiogroup"] > label p {
    margin: 0;
    font-size: 0.9rem;
}
</style>
""",
    unsafe_allow_html=True,
)

# -----------------------------
# 유틸 함수
# -----------------------------
def file_to_data_url(uploaded_file):
    """업로드 파일을 img src로 쓸 수 있는 data URL로 변환"""
    if uploaded_file is None:
        return ""
    bytes_data = uploaded_file.getvalue()
    mime = "image/png" if uploaded_file.type == "image/png" else "image/jpeg"
    encoded = base64.b64encode(bytes_data).decode("utf-8")
    return f"data:{mime};base64,{encoded}"
def pdf_file_to_data_urls(uploaded_file, dpi=200):
    """
    PDF 업로드 파일을 페이지별 PNG data URL 리스트로 변환
    """
    pages = convert_from_bytes(uploaded_file.getvalue(), dpi=dpi)
    urls = []
    for page in pages:
        buf = BytesIO()
        page.save(buf, format="PNG")
        encoded = base64.b64encode(buf.getvalue()).decode("utf-8")
        urls.append(f"data:image/png;base64,{encoded}")
    return urls



def safe_filename(text: str) -> str:
    """파일/폴더명에 안전한 형태로 변환"""
    if not text:
        return ""
    bad = ['\\', '/', ':', '*', '?', '"', '<', '>', '|']
    for ch in bad:
        text = text.replace(ch, "_")
    return text.strip().replace(" ", "_")


def load_checklist(country_code: str):
    """국가 선택값 -> checklist 파일명 매핑 후 로드"""
    country_map = {
        "CE": "ce.json",
        "FDA": "fda.json",
        "KFDA": "kfda.json",
        "CHINA": "china.json",
        "JAPAN": "japan.json",
        "KSA": "ksa.json",
        "STANDARD": "standard.json",
    }

    filename = country_map.get(country_code)
    if not filename:
        return None, f"(no mapping for {country_code})"

    path = os.path.join("checklist", filename)
    if not os.path.exists(path):
        return None, path

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f), path


def read_first_row_meta(xlsx_path: str):
    """히스토리 목록용: 엑셀 1행에서 메타 정보 추출"""
    try:
        df = pd.read_excel(xlsx_path)
        if df.empty:
            return None
        first = df.iloc[0]
        return {
            "고객사": first.get("고객사", ""),
            "제품명": first.get("제품명", ""),
            "버전": first.get("버전", ""),
            "부서": first.get("부서", ""),
            "상태": first.get("상태", ""),
            "체크자": first.get("체크한 사람", ""),
            "체크 날짜": first.get("체크 날짜", ""),
            "Case ID": first.get("Case ID", ""),
        }
    except Exception:
        return None


# -----------------------------
# 탭
# -----------------------------
tab_check, tab_history = st.tabs(["📝 체크리스트", "📂 히스토리(결과 조회)"])

# =============================
# 1) 체크리스트 탭
# =============================
with tab_check:
    # -----------------------------
    # 사이드바 (공용 입력)
    # -----------------------------
    st.sidebar.header("검토 정보")

    department = st.sidebar.selectbox("사용 부서", ["디자인팀", "영업팀", "연구기획/QA"])

    country = st.sidebar.selectbox(
        "검토 국가",
        ["CE", "FDA", "KFDA", "CHINA", "JAPAN", "KSA", "STANDARD"],
    )

    client_name = st.sidebar.text_input("고객사명")
    product_name = st.sidebar.text_input("제품명/세일즈팩명")
    version = st.sidebar.text_input("버전 (예: v1, v2)", value="v1")

    status = st.sidebar.selectbox("검토 상태", ["작성중", "검토요청", "보완필요", "검토완료"])

    st.sidebar.divider()

    st.sidebar.header("체크 정보 입력")
    checker_name = st.sidebar.text_input("체크한 사람 이름")
    check_date = st.sidebar.date_input("체크 날짜", value=date.today())

    st.sidebar.header("라벨/아트워크 이미지 업로드")
    uploaded_images = st.sidebar.file_uploader(
        "파일 업로드", type=["png", "jpg", "jpeg","pdf"], accept_multiple_files=True
    )

    # ✅ 이미지 패널 접기/펼치기 토글
    show_images = st.sidebar.checkbox("📦 이미지 패널 표시(접기/펼치기)", value=True)

    # 체크리스트 로드
    checklist, checklist_path = load_checklist(country)
    if checklist is None:
        st.warning(
            f"❗ 체크리스트 파일이 없습니다: {checklist_path}\n\n"
            f"→ checklist 폴더에 해당 JSON이 있는지 확인해주세요."
        )
        checklist = []

    # 부서별 안내
    if department == "영업팀":
        st.info("📌 영업팀: 고객사 전달용으로 '없음' 항목 중심으로 확인/정리하세요.")
    elif department == "연구기획/QA":
        st.info("📌 연구기획/QA: 필수 항목 충족 여부 및 근거 문구(규정/기준)를 확인하세요.")
    else:
        st.info("📌 디자인팀: 아트워크 반영 여부(심볼/문구 위치 포함)와 누락 가능성을 확인하세요.")

    # Case ID (세션 유지)
    if "case_id" not in st.session_state:
        st.session_state.case_id = str(uuid.uuid4())[:8]
    case_id = st.session_state.case_id

    # 상단 케이스 요약
    st.markdown(
        f"""
**🧾 Case ID:** `{case_id}`  
**국가:** {country} / **부서:** {department} / **상태:** {status}  
**고객사:** {client_name or "-"} / **제품:** {product_name or "-"} / **버전:** {version or "-"}  
"""
    )

    check_results = []

    # -----------------------------
    # 본문
    # -----------------------------
    if not uploaded_images:
        st.info("⬅️ 왼쪽 사이드바에서 라벨/아트워크 이미지를 업로드하면 체크리스트가 표시됩니다.")
    else:
        image_list = uploaded_images  # 이미지 개수 제한 없음

        # -------------------------
        # 1) 왼쪽: 화면에 고정되는 이미지 패널 (토글)
        # -------------------------
        if show_images:
            img_html_parts = []

            for idx, uf in enumerate(image_list):

                # ✅ PDF이면: 페이지를 여러 장 이미지로 변환해서 추가
                if uf.type == "application/pdf" or uf.name.lower().endswith(".pdf"):
                    try:
                        pdf_urls = pdf_file_to_data_urls(uf, dpi=200)
                        for p_url in pdf_urls:
                            img_html_parts.append(
                                f'<img src="{p_url}" style="width:100%; display:block; margin:0 0 16px 0;">'
                            )
                    except Exception as e:
                        img_html_parts.append(
                            f"<p style='color:red;'>PDF 변환 실패: {uf.name}<br>{e}</p>"
                        )

                # ✅ 이미지 파일이면: 기존처럼 1장만 추가
                else:
                    data_url = file_to_data_url(uf)
                    if not data_url:
                        continue
                    img_html_parts.append(
                        f'<img src="{data_url}" style="width:100%; display:block; margin:0 0 16px 0;">'
                    )

                # ✅ 파일 사이 구분선
                if idx < len(image_list) - 1:
                    img_html_parts.append(
                        '<hr style="border:1px solid #e0e0e0; margin:16px 0;">'
                    )

            left_panel_html = f"""
            <style>
            .fixed-label-panel {{
                position: fixed;
                top: 320px;
                left: 280px;
                width: 55vw;
                height: 70vh;
                max-height: 70vh;
                overflow-y: auto;
                overflow-x: auto;

                padding: 12px 16px;
                border-radius: 12px;
                border: 1px solid #e0e0e0;
                box-shadow: 0 8px 18px rgba(0, 0, 0, 0.08);
                background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
                box-sizing: border-box;
                z-index: 9999;
            }}
            </style>

            <div class="fixed-label-panel">
                <h3>📦 업로드된 이미지</h3>
                {''.join(img_html_parts)}
            </div>
            """
            st.markdown(left_panel_html, unsafe_allow_html=True)


            left_panel_html = f"""
            <style>
            .fixed-label-panel {{
                position: fixed;
                top: 320px;
                left: 280px;
                width: 55vw;
                height: 70vh;
                max-height: 60vh;
                overflow-y: scroll;
                overflow-x: auto;

                padding: 12px 16px;
                border-radius: 12px;
                border: 1px solid #e0e0e0;
                box-shadow: 0 8px 18px rgba(0, 0, 0, 0.08);
                background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
                box-sizing: border-box;
                z-index: 9999;
            }}

            .fixed-label-panel::-webkit-scrollbar {{
                width: 10px;
                height: 10px;
            }}
            .fixed-label-panel::-webkit-scrollbar-track {{
                background: #f0f0f0;
            }}
            .fixed-label-panel::-webkit-scrollbar-thumb {{
                background: #c0c0c0;
                border-radius: 5px;
            }}
            .fixed-label-panel::-webkit-scrollbar-thumb:hover {{
                background: #999999;
            }}
            .fixed-label-panel {{
                scrollbar-width: thin;
                scrollbar-color: #c0c0c0 #f0f0f0;
            }}
            </style>

            <div class="fixed-label-panel">
                <h3>📦 업로드된 이미지</h3>
                {''.join(img_html_parts)}
            </div>
            """
            st.markdown(left_panel_html, unsafe_allow_html=True)
        else:
            st.info("📦 이미지 패널이 숨김 상태입니다. (사이드바에서 다시 켤 수 있어요)")

        # -------------------------
        # 2) 오른쪽: 체크리스트
        # -------------------------
        left_col, right_col = st.columns([3.5, 1.5], gap="large")

        with left_col:
            # 패널 유무에 따라 확보 공간을 다르게
            if show_images:
                st.markdown("<div style='height: 1100px;'></div>", unsafe_allow_html=True)
            else:
                st.markdown("<div style='height: 40px;'></div>", unsafe_allow_html=True)

        with right_col:
            st.markdown(f"### 📝 {country} 라벨 표시 기재사항 체크리스트")

            if not checklist:
                st.warning("체크리스트 항목이 비어 있습니다. checklist JSON을 확인해주세요.")
            else:
                for item in checklist:
                    item_name = item.get("항목명", "(항목명 없음)")
                    기준문구 = item.get("기준 문구", item.get("기준문구", ""))

                    st.markdown(f"#### {item_name}")
                    if 기준문구:
                        st.markdown(f"**기준 문구:** {기준문구}")

                    symbol_file = item.get("심볼")
                    if symbol_file:
                        symbol_path = os.path.join("symbol_library", symbol_file)
                        if os.path.exists(symbol_path):
                            st.image(symbol_path, caption="심볼 예시", width=80)
                        else:
                            st.warning(f"❗ 심볼 이미지가 없습니다: {symbol_file}")

                    result = st.radio(
                        "체크 결과",
                        ["있음", "없음", "해당없음"],
                        key=f"{case_id}_{country}_{item_name}_result",
                    )
                    remark = st.text_area(
                        "비고",
                        key=f"{case_id}_{country}_{item_name}_remark",
                        placeholder="필요 시 추가 메모를 입력하세요.",
                    )

                    check_results.append(
                        {
                            "Case ID": case_id,
                            "부서": department,
                            "국가": country,
                            "고객사": client_name,
                            "제품명": product_name,
                            "버전": version,
                            "상태": status,
                            "이미지명": ", ".join([img.name for img in image_list]),
                            "항목명": item_name,
                            "기준문구": 기준문구,
                            "심볼이미지": symbol_file or "",
                            "결과": result,
                            "비고": remark,
                            "체크한 사람": checker_name,
                            "체크 날짜": check_date.strftime("%Y-%m-%d"),
                        }
                    )

    # -----------------------------
    # 결과 저장 + 엑셀 다운로드
    # -----------------------------
    if check_results:
        df = pd.DataFrame(check_results)

        st.divider()
        st.markdown("### ✅ 결과 저장 / 다운로드")

        missing = []
        if not client_name:
            missing.append("고객사명")
        if not product_name:
            missing.append("제품명/세일즈팩명")
        if not checker_name:
            missing.append("체크한 사람 이름")

        if missing:
            st.warning(f"저장/공유를 위해 다음 항목을 입력해주세요: {', '.join(missing)}")

        # 공용 저장 버튼
        if st.button("💾 공용 폴더에 결과 저장"):
            if missing:
                st.error("필수 입력값이 누락되어 저장할 수 없습니다.")
            else:
                safe_client = safe_filename(client_name)
                safe_product = safe_filename(product_name)
                safe_ver = safe_filename(version)

                save_dir = os.path.join("results", country, f"{safe_client}_{safe_product}")
                os.makedirs(save_dir, exist_ok=True)

                file_name = f"{country}_{safe_client}_{safe_product}_{safe_ver}_{case_id}.xlsx"
                save_path = os.path.join(save_dir, file_name)

                with pd.ExcelWriter(save_path, engine="openpyxl") as writer:
                    df.to_excel(writer, index=False, sheet_name=f"{country}_Label_Check")

                st.success(f"✅ 결과 저장 완료: {save_path}")

        # 다운로드 버튼
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name=f"{country}_Label_Check")

        download_name = (
            f"{country}_LabelCheck_"
            f"{safe_filename(client_name) or 'Client'}_"
            f"{safe_filename(product_name) or 'Product'}_"
            f"{safe_filename(version) or 'v1'}_"
            f"{case_id}.xlsx"
        )
        st.download_button(
            label="📥 엑셀 결과 다운로드",
            data=output.getvalue(),
            file_name=download_name,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        if st.button("🆕 새 검토 건 시작 (Case ID 재생성)"):
            st.session_state.case_id = str(uuid.uuid4())[:8]
            st.rerun()


# =============================
# 2) 히스토리 탭
# =============================
with tab_history:
    st.markdown("## 📂 저장된 검토 결과 조회")

    base_dir = "results"
    if not os.path.exists(base_dir):
        st.info("아직 저장된 결과가 없습니다. 체크리스트 탭에서 먼저 '공용 폴더 저장'을 해주세요.")
    else:
        rows = []

        for ctry in os.listdir(base_dir):
            ctry_dir = os.path.join(base_dir, ctry)
            if not os.path.isdir(ctry_dir):
                continue

            for case_folder in os.listdir(ctry_dir):
                case_dir = os.path.join(ctry_dir, case_folder)
                if not os.path.isdir(case_dir):
                    continue

                for fname in os.listdir(case_dir):
                    if not fname.lower().endswith(".xlsx"):
                        continue

                    fpath = os.path.join(case_dir, fname)
                    meta = read_first_row_meta(fpath)
                    if not meta:
                        continue

                    rows.append(
                        {
                            "국가": ctry,
                            "고객사": meta.get("고객사", ""),
                            "제품명": meta.get("제품명", ""),
                            "버전": meta.get("버전", ""),
                            "부서": meta.get("부서", ""),
                            "상태": meta.get("상태", ""),
                            "체크자": meta.get("체크자", ""),
                            "체크 날짜": meta.get("체크 날짜", ""),
                            "Case ID": meta.get("Case ID", ""),
                            "파일명": fname,
                            "경로": fpath,
                        }
                    )

        if not rows:
            st.info("표시할 히스토리 결과가 없습니다.")
        else:
            df_hist = pd.DataFrame(rows)

            # 필터 UI
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                f_country = st.selectbox("국가", ["전체"] + sorted(df_hist["국가"].unique().tolist()))
            with col2:
                f_dept = st.selectbox("부서", ["전체"] + sorted(df_hist["부서"].unique().tolist()))
            with col3:
                f_status = st.selectbox("상태", ["전체"] + sorted(df_hist["상태"].unique().tolist()))
            with col4:
                keyword = st.text_input("고객사 / 제품명 검색")

            filtered = df_hist.copy()
            if f_country != "전체":
                filtered = filtered[filtered["국가"] == f_country]
            if f_dept != "전체":
                filtered = filtered[filtered["부서"] == f_dept]
            if f_status != "전체":
                filtered = filtered[filtered["상태"] == f_status]
            if keyword:
                filtered = filtered[
                    filtered["고객사"].astype(str).str.contains(keyword, case=False, na=False)
                    | filtered["제품명"].astype(str).str.contains(keyword, case=False, na=False)
                ]

            st.markdown(f"### 🔎 검색 결과 ({len(filtered)}건)")
            st.dataframe(filtered.drop(columns=["경로"]), use_container_width=True)

            st.markdown("### 📥 다운로드 / 🔗 공유")
            for _, r in filtered.iterrows():
                try:
                    with open(r["경로"], "rb") as f:
                        st.download_button(
                            label=f"📥 {r['국가']} | {r['고객사']} | {r['제품명']} | {r['버전']} | {r['상태']}",
                            data=f.read(),
                            file_name=r["파일명"],
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key=r["경로"],
                        )
                except Exception:
                    st.warning(f"파일을 열 수 없습니다: {r['파일명']}")
                    continue

                share_text = f"""
[라벨 기재사항 검토 결과 공유]

- 국가: {r['국가']}
- 고객사: {r['고객사']}
- 제품명: {r['제품명']}
- 버전: {r['버전']}
- 상태: {r['상태']}
- 체크자: {r['체크자']}
- 체크 날짜: {r['체크 날짜']}

공용 저장 경로:
{r['경로']}
"""
                with st.expander("🔗 공유용 정보 (메일 / Teams용)"):
                    st.text_area(
                        "아래 내용을 그대로 복사하여 공유하세요",
                        value=share_text.strip(),
                        height=180,
                    )
