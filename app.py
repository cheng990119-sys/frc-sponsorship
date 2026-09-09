import streamlit as st
import pandas as pd
import os
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

# ==========================================
# 網頁基本設定 & 狀態初始化 (模擬資料庫)
# ==========================================
st.set_page_config(page_title="FRC 贊助商寄信系統", layout="wide")

# 預設信件模板
DEFAULT_TEMPLATE = """尊敬的 {企業／贊助單位} 貴賓與團隊 您好：

我們是來自台灣的高中機器人競賽團隊【{team_name}】。

考量到團隊在【{潛在贊助項目／形式}】的需求，希望能有機會向貴公司爭取支持與合作（{說明與贊助契機}）。

我們為貴單位量身編製了專屬贊助合作企劃書，隨信檢附如附件：
▶ 專屬企劃書：{pdf_filename}

敬祝 商祺

【{team_name}】公關團隊"""

# 初始化 session_state
if "page" not in st.session_state:
    st.session_state.page = "home"
if "current_project" not in st.session_state:
    st.session_state.current_project = None
if "projects" not in st.session_state:
    # 預設給一個範例專案
    st.session_state.projects = {
        "2026 FRC 赴美參賽贊助計畫": {
            "sent_companies": [],
            "template": DEFAULT_TEMPLATE
        }
    }

# 自動擷取 Email 的小工具
def extract_email(contact_str):
    if pd.isna(contact_str): return None
    match = re.search(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', str(contact_str))
    return match.group(0) if match else None

# ==========================================
# 頁面 1：乾淨的首頁 (專案管理區)
# ==========================================
if st.session_state.page == "home":
    st.title("👋 歡迎來到 FRC 贊助商公關寄信系統")
    st.markdown("請選擇要進入的專案，或是建立全新的企劃專案。")
    st.divider()
    
    col_new, col_list = st.columns([1, 2])
    
    # 左側：新增專案區塊
    with col_new:
        st.subheader("➕ 建立新專案")
        with st.form("new_project_form"):
            new_proj_name = st.text_input("為您的新專案命名：", placeholder="例如：2027 台灣區賽募資")
            submit_btn = st.form_submit_button("建立專案", type="primary", use_container_width=True)
            
            if submit_btn:
                if not new_proj_name.strip():
                    st.error("專案名稱不能為空！")
                elif new_proj_name in st.session_state.projects:
                    st.error("此專案名稱已經存在，請換一個名字！")
                else:
                    # 建立新專案的資料結構
                    st.session_state.projects[new_proj_name] = {
                        "sent_companies": [],
                        "template": DEFAULT_TEMPLATE
                    }
                    st.success(f"成功建立專案：{new_proj_name}")
                    st.rerun()

    # 右側：現有專案列表區塊
    with col_list:
        st.subheader("📂 我的專案列表")
        
        if not st.session_state.projects:
            st.info("目前沒有任何專案，請從左側建立一個吧！")
        else:
            # 條列出所有專案
            for proj_name, proj_data in list(st.session_state.projects.items()):
                with st.container(border=True):
                    c1, c2, c3 = st.columns([6, 2, 2])
                    with c1:
                        st.markdown(f"#### {proj_name}")
                        st.caption(f"已寄出信件：**{len(proj_data['sent_companies'])}** 封")
                    with c2:
                        if st.button("📂 開啟專案", key=f"open_{proj_name}", use_container_width=True):
                            st.session_state.current_project = proj_name
                            st.session_state.page = "project"
                            st.rerun()
                    with c3:
                        if st.button("🗑️ 刪除", key=f"del_{proj_name}", use_container_width=True):
                            del st.session_state.projects[proj_name]
                            st.rerun()

# ==========================================
# 頁面 2：專案編輯與寄信工作區
# ==========================================
elif st.session_state.page == "project":
    
    current_proj = st.session_state.current_project
    proj_data = st.session_state.projects[current_proj]

    # 頂部返回按鈕
    if st.button("🔙 返回首頁 (切換專案)"):
        st.session_state.page = "home"
        st.session_state.current_project = None
        st.rerun()
        
    st.title(f"📁 專案：{current_proj}")
    st.divider()

    # --- 左側欄：寄件帳號設定 ---
    st.sidebar.header("🔐 寄件帳號設定")
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

    # 讀取該專案專屬的信件模板
    email_template = st.text_area("✏️ 信件內容編輯區", value=proj_data["template"], height=200)
    # 即時存檔使用者修改的模板
    st.session_state.projects[current_proj]["template"] = email_template

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
                
                # 檢查該廠商是否已經在此專案中寄出過
                is_sent = selected_company in proj_data["sent_companies"]
                
                btn_col1, btn_col2 = st.columns([2, 8])
                
                with btn_col1:
                    btn_text = "🚀 再次寄送" if is_sent else f"🚀 確定寄送"
                    
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
                                    
                                    # 將紀錄寫入「當前專案」中
                                    if selected_company not in proj_data["sent_companies"]:
                                        proj_data["sent_companies"].append(selected_company)
                                    st.rerun()
                                    
                                except Exception as e:
                                    st.error(f"❌ 寄件失敗：{e}")
                
                with btn_col2:
                    if is_sent:
                        st.success("✅ 已寄出 (此專案已有紀錄)")
                        
            except KeyError as e:
                st.error(f"⚠️ 信件模板變數錯誤：{e}")