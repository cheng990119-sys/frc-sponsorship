import streamlit as st
import pandas as pd

# 網頁標題與基本設定
st.set_page_config(page_title="FRC 贊助商寄信系統", layout="wide")
st.title("✉️ FRC 贊助商公關寄信管理系統")

# ==========================================
# Step 1: 專案設定與信件格式
# ==========================================
st.header("Step 1: 新增專案與設定信件格式")
project_name = st.text_input("專案名稱", value="2026 FRC 赴美參賽贊助計畫")

st.markdown("請在下方輸入本次專案的寄信格式。您可以使用大括號 `{}` 來插入 Excel 表格中的欄位名稱，系統會自動替換。")
default_template = """尊敬的 {企業／贊助單位} 貴賓 您好：

我們是來自台灣的高中機器人競賽團隊。得知貴公司在【{主要產品／業務領域}】領域的專業，我們深感敬佩！
考量到我們團隊在【{潛在贊助項目／形式}】的需求，希望能有機會向貴公司爭取支持。

若有機會進一步討論，歡迎隨時聯繫！

公關團隊 敬上"""

# 文字區域讓使用者編輯信件內容
email_template = st.text_area("✏️ 信件內容編輯區", value=default_template, height=250)

# ==========================================
# Step 2: 載入贊助商 Excel 表格
# ==========================================
st.header("Step 2: 載入贊助商 Excel 資料")
uploaded_file = st.file_uploader("上傳贊助商名單 (.xlsx)", type=["xlsx"])

if uploaded_file is not None:
    # 讀取 Excel 檔案 (預設讀取第一個工作表，您可以根據需要修改)
    df = pd.read_excel(uploaded_file, sheet_name="全部彙總清單")
    
    with st.expander("👀 點擊查看完整贊助商名單資料"):
        st.dataframe(df)

    # ==========================================
    # Step 3: 動態預覽與備註確認
    # ==========================================
    st.header("Step 3: 檢視廠商備註與信件預覽")
    
    # 建立下拉選單選擇廠商
    company_list = df['企業／贊助單位'].dropna().unique().tolist()
    selected_company = st.selectbox("🔍 選擇要預覽的廠商", company_list)

    if selected_company:
        # 抓取該廠商的資料行
        row_data = df[df['企業／贊助單位'] == selected_company].iloc[0]
        
        # 顯示廠商備註 (說明與贊助契機)
        st.subheader(f"💡 【{selected_company}】專屬備註與契機")
        st.info(row_data.get('說明與贊助契機', '無備註資料'))
        
        # 準備變數字典，用於替換信件模板
        # 將該行的資料轉為字典，確保欄位名稱與模板中的 {} 能夠對應
        format_dict = row_data.to_dict()
        
        try:
            # 將變數套用入信件模板
            preview_text = email_template.format(**format_dict)
            st.subheader("📝 信件預覽")
            # 使用 text 顯示，保留換行格式
            st.text(preview_text)
            
            # (未來可擴充功能) 寄出按鈕
            if st.button(f"🚀 寄送專屬企劃書給 {selected_company}"):
                st.success("（這是一個測試按鈕）信件寄送功能尚未串接！")
                
        except KeyError as e:
            st.error(f"⚠️ 信件模板中包含了無法識別的變數 {e}，請確認大括號內的名稱與 Excel 欄位完全一致！")