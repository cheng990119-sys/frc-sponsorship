import streamlit as st
import pandas as pd
import os
import re
import smtplib
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

# ==========================================
# 網頁基本設定 & 狀態初始化
# ==========================================
st.set_page_config(page_title="FRC 贊助商寄信系統", layout="wide")

# 初始化 session_state 變數，用來控制頁面與紀錄狀態
if "page" not in st.session_state:
    st.session_state.page = "home"  # 預設停留在首頁
if "sent_companies" not in st.session_state:
    st.session_state.sent_companies = []  # 紀錄已經寄出信件的廠商名單

# ==========================================
# 頁面 1：乾淨的歡迎首頁
# ==========================================
if st.session_state.page == "home":
    st.title("👋 歡迎來到 FRC 贊助商公關寄信系統")
    st.markdown("請選擇要建立全新的專案，或是載入之前的專案進度。")
    
    st.write("") # 空行排版
    
    col1, col2 = st.columns([1, 2])
    with col1:
        if st.button("➕ 建立新專案", use_container_width=True, type="primary"):
            st.session_state.page = "project"
            st.rerun()  # 刷新頁面，切換到專案頁
            
    with col2:
        # 這裡未來可以串接真實的資料庫或本地 JSON 檔來讀取歷史紀錄
        # 目前先做一個 UI 展示用的舊專案按鈕
        st.markdown("### 📂 最近的專案紀錄")
        if st.button("📝 2026 FRC 赴美參賽贊助計畫 (紀錄檔)"):
            st.session_state.page = "project"
            st.rerun()

# ==========================================
# 頁面 2：專案編輯與寄信工作區
# ==========================================
elif st.session_state.page == "project":
    
    # 頂部導覽列：提供返回首頁的按鈕
    if st.button("🔙 返回首頁"):
        st.session_state.page = "home"
        st.rerun()
        
    st.title("✉️ FRC 贊助商公關寄信管理區")
    st.divider()

    # --- 左側欄：寄件帳號設定 ---
    st.sidebar.header("🔐 寄件帳號設定")
    st.sidebar.info("請輸入用來寄信的 Gmail 帳號與 16 位應用程式密碼。")
    sender_email = st.sidebar.text_input("寄件者 Email", placeholder="your_team@gmail.com")
    sender_password = st.sidebar.text_input("應用程式密碼", type="password", placeholder="xxxx xxxx xxxx xxxx")

    st.sidebar.header("📂 企劃書資料夾設定")
    pdf_dir = st.sidebar.text_input("附件資料夾名稱", value="企劃書檔案")

    # --- Step 1: 團隊資訊與信件格式 ---
    st.header("Step 1: 團隊資訊與信件格式")
    col1, col2, col3 = st.columns(3)
    team_name = col1.text_input("團隊名稱", value="FRC 團隊名稱")
    contact_person = col2.text_input("聯絡人姓名", value="公關長 王小明")
    contact_phone = col3.text_input("聯絡電話", value="0912-345-678")

    default_template = """尊敬的 {企業／贊助單位} 貴賓與團隊 您好：\n\n我們是來自台灣的高中機器人競賽團隊【{team_name}】。\n\n考量到團隊在【{潛在贊助項目／形式}】的需求，希望能有機會向貴公司爭取支持與合作（{說明與贊助契機}）。\n\n敬祝 商祺\n\n【{team_name}】公關團隊"""
    email_template = st.text_area("✏️ 信件內容編輯區", value=default_template, height=200)

    def extract_email(contact_str):
        if pd.isna(contact_str): return None
        match = re.search(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', str(contact_str))
        return match.group(0) if match else None

    # --- Step 2: 載入贊助商 Excel 表格 ---
    st.header("Step 2: 載入贊助商 Excel 資料")
    uploaded_file = st.file_uploader("上傳贊助商名單 (.xlsx)", type=["xlsx"])

    if uploaded_file is not None:
        df = pd.read_excel(uploaded_file, sheet_name="全部彙總清單")
        
        with st.expander("👀 點擊查看完整贊助商名單資料"):
            st.dataframe(df)

        # --- Step 3: 動態預覽與寄信 ---
        st.header("Step 3: 檢視廠商備註與寄出信件")
        
        company_list = df['企業／贊助單位'].dropna().unique().tolist()
        selected_company = st.selectbox("🔍 選擇要處理的廠商", company_list)

        if selected_company:
            row_data = df[df['企業／贊助單位'] == selected_company].iloc[0]
            company_id = str(row_data['編號']).zfill(3)
            to_email = extract_email(row_data['聯絡資訊'])
            
            st.subheader(f"💡 【{selected_company}】專屬備註")
            st.info(row_data.get('說明與贊助契機', '無備註資料'))
            
            pdf_filename = f"{company_id}_{selected_company}_贊助企劃書.pdf"
            pdf_path = os.path.join(pdf_dir, pdf_filename)
            
            format_dict = row_data.to_dict()
            format_dict.update({"team_name": team_name, "pdf_filename": pdf_filename})
            
            try:
                preview_text = email_template.format(**format_dict)
                st.markdown("### 📝 信件預覽")
                st.text(preview_text)
                
                st.markdown("---")
                
                # 檢查該廠商是否已經在寄出名單紀錄中
                is_sent = selected_company in st.session_state.sent_companies
                
                # 建立按鈕與狀態標籤的並排版面
                btn_col1, btn_col2 = st.columns([2, 8])
                
                with btn_col1:
                    # 如果已經寄過，可以改變按鈕上的文字提醒
                    btn_text = "🚀 再次寄送" if is_sent else f"🚀 確定寄送給 {selected_company}"
                    
                    if st.button(btn_text, type="primary"):
                        if not sender_email or not sender_password:
                            st.error("⚠️ 請先在左側欄填寫寄件帳號設定！")
                        elif not to_email:
                            st.error("⚠️ 此廠商沒有有效的 Email 信箱！")
                        else:
                            with st.spinner('正在寄送信件...'):
                                try:
                                    server = smtplib.SMTP("smtp.gmail.com", 587)
                                    server.starttls()
                                    server.login(sender_email, sender_password)
                                    
                                    msg = MIMEMultipart()
                                    msg['From'], msg['To'], msg['Subject'] = sender_email, to_email, f"【贊助邀請】{team_name} — 敬致 {selected_company}"
                                    msg.attach(MIMEText(preview_text, 'plain', 'utf-8'))
                                    
                                    if os.path.exists(pdf_path):
                                        with open(pdf_path, 'rb') as f:
                                            attach = MIMEApplication(f.read(), _subtype="pdf")
                                            attach.add_header('Content-Disposition', 'attachment', filename=pdf_filename)
                                            msg.attach(attach)
                                            
                                    server.send_message(msg)
                                    server.quit()
                                    
                                    # 寄送成功後，將該廠商加入已寄出清單，並刷新頁面更新狀態
                                    if selected_company not in st.session_state.sent_companies:
                                        st.session_state.sent_companies.append(selected_company)
                                    st.rerun()
                                    
                                except Exception as e:
                                    st.error(f"❌ 寄件失敗：{e}")
                
                with btn_col2:
                    # 判斷並顯示「已寄出」綠色標籤
                    if is_sent:
                        st.success("✅ 已寄出 (本工作階段已有寄件紀錄)")
                        
            except KeyError as e:
                st.error(f"⚠️ 信件模板變數錯誤：{e}")