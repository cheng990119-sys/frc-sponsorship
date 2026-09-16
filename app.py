import streamlit as st
import pandas as pd
import os
import re
import smtplib
import time
import imaplib
import json
import hashlib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication

# ==========================================
# 網頁基本設定
# ==========================================
st.set_page_config(page_title="公關寄信系統", layout="wide")

# 系統檔案路徑
USERS_FILE = "users.json"
PROJECTS_FILE = "projects.json"

# ==========================================
# 資料庫與輔助函式
# ==========================================
def hash_password(password):
    """將密碼加密，保護帳號安全"""
    return hashlib.sha256(password.encode()).hexdigest()

def load_users():
    """讀取使用者資料，若無則建立預設管理員帳號"""
    if not os.path.exists(USERS_FILE):
        default_users = {
            "admin": {
                "password": hash_password("admin123"), 
                "role": "admin",
                "real_name": "系統管理員"
            }
        }
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(default_users, f, ensure_ascii=False, indent=4)
        return default_users
    with open(USERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_users(users_data):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users_data, f, ensure_ascii=False, indent=4)

def load_projects():
    """讀取專案與寄件紀錄"""
    if not os.path.exists(PROJECTS_FILE):
        return {}
    with open(PROJECTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_projects(projects_data):
    with open(PROJECTS_FILE, "w", encoding="utf-8") as f:
        json.dump(projects_data, f, ensure_ascii=False, indent=4)

def extract_email(contact_str):
    if pd.isna(contact_str): return None
    match = re.search(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', str(contact_str))
    return match.group(0) if match else None

# 預設信件模板
DEFAULT_TEMPLATE = """尊敬的 {企業／贊助單位} 貴賓與團隊 您好：\n\n我們是來自台灣的高中機器人競賽團隊【{team_name}】。\n\n考量到團隊在【{潛在贊助項目／形式}】的需求，希望能有機會向貴公司爭取支持與合作（{說明與贊助契機}）。\n\n我們為貴單位量身編製了專屬贊助合作企劃書，隨信檢附如附件：\n▶ 專屬企劃書：{pdf_filename}\n\n若有任何需要進一步討論之處，非常歡迎隨時聯繫。由衷感謝您撥冗閱讀！\n\n敬祝 商祺\n\n【{team_name}】公關團隊\n聯絡人：{contact_person}\n聯絡電話：{contact_phone}\n隊伍信箱：{sender_email}"""

# ==========================================
# 狀態初始化
# ==========================================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.role = ""
    st.session_state.real_name = ""
if "page" not in st.session_state:
    st.session_state.page = "home"
if "current_project" not in st.session_state:
    st.session_state.current_project = None

# ==========================================
# 登入介面 (未登入時顯示)
# ==========================================
if not st.session_state.logged_in:
    st.title("🔐 公關寄信系統")
    st.markdown("請輸入您的專屬帳號與密碼以登入系統。")
    
    with st.form("login_form"):
        login_user = st.text_input("帳號 (Username)")
        login_pwd = st.text_input("密碼 (Password)", type="password")
        submit_login = st.form_submit_button("登入", type="primary")
        
        if submit_login:
            users_db = load_users()
            if login_user in users_db and users_db[login_user]["password"] == hash_password(login_pwd):
                st.session_state.logged_in = True
                st.session_state.username = login_user
                st.session_state.role = users_db[login_user]["role"]
                st.session_state.real_name = users_db[login_user].get("real_name", login_user)
                st.rerun()
            else:
                st.error("⚠️ 帳號或密碼錯誤，請重新輸入！")
    st.stop()  # 阻擋未登入者看到下方內容

# ==========================================
# 登入後的側邊欄 (導覽與設定)
# ==========================================
st.sidebar.markdown(f"👤 登入者：**{st.session_state.real_name}**")
if st.sidebar.button("🚪 登出", use_container_width=True):
    st.session_state.logged_in = False
    st.rerun()

st.sidebar.divider()

# 根據權限顯示選單
nav_options = ["🏠 專案與寄信區"]
if st.session_state.role == "admin":
    nav_options.append("⚙️ 系統後台管理")

app_mode = st.sidebar.radio("📌 系統功能導覽", nav_options)
st.sidebar.divider()

# 讀取專案資料庫
projects_db = load_projects()

# ==========================================
# 模式 A：系統後台管理 (僅管理員可見)
# ==========================================
if app_mode == "⚙️ 系統後台管理":
    st.title("⚙️ 系統後台管理")
    st.markdown("您可以在此創建團隊成員帳號，並總覽所有專案的寄件進度。")
    
    tab1, tab2 = st.tabs(["👥 帳號管理", "📊 團隊寄件總覽"])
    
    with tab1:
        st.subheader("建立新帳號")
        with st.form("add_user_form"):
            c1, c2, c3 = st.columns(3)
            new_username = c1.text_input("登入帳號 (英文/數字)")
            new_realname = c2.text_input("成員姓名")
            new_password = c3.text_input("預設密碼", type="password")
            new_role = st.selectbox("帳號權限", ["user (一般成員)", "admin (管理員)"])
            
            if st.form_submit_button("新增帳號", type="primary"):
                users_db = load_users()
                if new_username in users_db:
                    st.error("此帳號已存在！")
                elif not new_username or not new_password:
                    st.error("帳號與密碼不得為空！")
                else:
                    users_db[new_username] = {
                        "password": hash_password(new_password),
                        "role": "admin" if "admin" in new_role else "user",
                        "real_name": new_realname
                    }
                    save_users(users_db)
                    st.success(f"✅ 成功建立帳號：{new_realname} ({new_username})")
        
        st.subheader("現有帳號列表")
        users_db = load_users()
        user_list = []
        for u, d in users_db.items():
            user_list.append({"帳號": u, "姓名": d.get("real_name", u), "權限": d["role"]})
        st.table(pd.DataFrame(user_list))

    with tab2:
        st.subheader("📂 專案進度與紀錄總覽")
        if not projects_db:
            st.info("目前尚未建立任何專案。")
        else:
            for p_name, p_data in projects_db.items():
                sent_list = p_data.get("sent_companies", [])
                with st.expander(f"📁 專案：{p_name} (已寄出 {len(sent_list)} 封)"):
                    if sent_list:
                        for record in sent_list:
                            # 顯示 廠商名稱 - 寄件者
                            if isinstance(record, dict):
                                st.markdown(f"- **{record['company']}** (寄件人: {record['sender']})")
                            else:
                                st.markdown(f"- **{record}** (早期紀錄)")
                    else:
                        st.caption("尚無寄件紀錄")

# ==========================================
# 模式 B：專案與寄信區 (所有人可見)
# ==========================================
elif app_mode == "🏠 專案與寄信區":
    
    if st.session_state.page == "home":
        st.title("✉️ 公關寄信系統 - 專案大廳")
        st.markdown("請選擇要進入的專案，或是建立全新的企劃專案。")
        st.divider()
        
        col_new, col_list = st.columns([1, 2])
        
        with col_new:
            st.subheader("➕ 建立新專案")
            with st.form("new_project_form"):
                new_proj_name = st.text_input("為您的新專案命名：")
                if st.form_submit_button("建立專案", type="primary", use_container_width=True):
                    if not new_proj_name.strip():
                        st.error("專案名稱不能為空！")
                    elif new_proj_name in projects_db:
                        st.error("此專案已經存在！")
                    else:
                        projects_db[new_proj_name] = {
                            "sent_companies": [],
                            "template": DEFAULT_TEMPLATE
                        }
                        save_projects(projects_db)
                        st.success(f"成功建立：{new_proj_name}")
                        st.rerun()

        with col_list:
            st.subheader("📂 現有專案列表")
            if not projects_db:
                st.info("目前沒有任何專案，請從左側建立一個吧！")
            else:
                for proj_name, proj_data in list(projects_db.items()):
                    with st.container(border=True):
                        c1, c2, c3 = st.columns([6, 2, 2])
                        with c1:
                            st.markdown(f"#### {proj_name}")
                            st.caption(f"已寄出信件：**{len(proj_data.get('sent_companies', []))}** 封")
                        with c2:
                            if st.button("📂 開啟", key=f"open_{proj_name}", use_container_width=True):
                                st.session_state.current_project = proj_name
                                st.session_state.page = "project"
                                st.rerun()
                        with c3:
                            # 只有管理員可以刪除專案
                            if st.session_state.role == "admin":
                                if st.button("🗑️ 刪除", key=f"del_{proj_name}", use_container_width=True):
                                    del projects_db[proj_name]
                                    save_projects(projects_db)
                                    st.rerun()

    elif st.session_state.page == "project":
        current_proj = st.session_state.current_project
        if current_proj not in projects_db:
            st.session_state.page = "home"
            st.rerun()
            
        proj_data = projects_db[current_proj]

        if st.sidebar.button("🔙 返回專案大廳", type="primary", use_container_width=True):
            st.session_state.page = "home"
            st.session_state.current_project = None
            st.rerun()
            
        st.sidebar.divider()
        st.sidebar.header("🔐 寄件帳號設定")
        sender_email = st.sidebar.text_input("團隊 Gmail 信箱", placeholder="your_team@gmail.com")
        sender_password = st.sidebar.text_input("應用程式密碼", type="password", placeholder="xxxx xxxx xxxx xxxx")
        
        st.sidebar.header("📂 系統設定")
        pdf_dir = st.sidebar.text_input("附件資料夾名稱", value="企劃書檔案")
        backup_folder = st.sidebar.text_input("Gmail 備份標籤名稱", value="FRC_Sponsorship")

        st.title(f"📁 專案：{current_proj}")
        st.divider()

        st.header("Step 1: 團隊資訊與信件格式")
        col1, col2, col3 = st.columns(3)
        team_name = col1.text_input("團隊名稱", value="FRC 團隊名稱")
        contact_person = col2.text_input("聯絡人姓名", value=st.session_state.real_name)
        contact_phone = col3.text_input("聯絡電話", value="0912-345-678")

        email_template = st.text_area("✏️ 信件內容編輯區", value=proj_data.get("template", DEFAULT_TEMPLATE), height=250)
        # 即時存檔模板
        if email_template != proj_data.get("template"):
            projects_db[current_proj]["template"] = email_template
            save_projects(projects_db)

        st.header("Step 2: 載入贊助商 Excel 資料")
        uploaded_file = st.file_uploader("上傳贊助商名單 (.xlsx)", type=["xlsx"])

        if uploaded_file is not None:
            df = pd.read_excel(uploaded_file, sheet_name="全部彙總清單")
            
            with st.expander("👀 查看完整贊助商名單"):
                st.dataframe(df)

            st.header("Step 3: 檢視與寄出")
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
                format_dict.update({
                    "team_name": team_name, "contact_person": contact_person,
                    "contact_phone": contact_phone, "sender_email": sender_email if sender_email else "尚未填寫",
                    "pdf_filename": pdf_filename
                })
                
                try:
                    preview_text = email_template.format(**format_dict)
                    st.markdown("### 📝 信件預覽")
                    st.text(preview_text)
                    st.markdown("---")
                    
                    # 檢查是否已寄出 (支援新舊資料結構)
                    sent_list = proj_data.get("sent_companies", [])
                    is_sent = any(isinstance(r, dict) and r["company"] == selected_company for r in sent_list) or (selected_company in sent_list)
                    
                    btn_col1, btn_col2 = st.columns([2, 8])
                    with btn_col1:
                        btn_text = "🚀 再次寄送" if is_sent else f"🚀 確定寄送"
                        if st.button(btn_text, type="primary"):
                            if not sender_email or not sender_password:
                                st.error("⚠️ 請先在左側欄填寫寄件帳號設定！")
                            elif not to_email:
                                st.error("⚠️ 此廠商沒有 Email！")
                            else:
                                with st.spinner('正在寄送信件與備份中...'):
                                    try:
                                        server = smtplib.SMTP("smtp.gmail.com", 587)
                                        server.starttls()
                                        server.login(sender_email, sender_password)
                                        
                                        subject = f"【贊助合作邀請】{team_name} 赴美參賽企劃書 — 敬致 {selected_company}"
                                        msg = MIMEMultipart()
                                        msg['From'], msg['To'], msg['Subject'] = sender_email, to_email, subject
                                        msg.attach(MIMEText(preview_text, 'plain', 'utf-8'))
                                        
                                        if os.path.exists(pdf_path):
                                            with open(pdf_path, 'rb') as f:
                                                attach = MIMEApplication(f.read(), _subtype="pdf")
                                                attach.add_header('Content-Disposition', 'attachment', filename=pdf_filename)
                                                msg.attach(attach)
                                                
                                        server.send_message(msg)
                                        server.quit()
                                        
                                        backup_status = ""
                                        try:
                                            imap = imaplib.IMAP4_SSL("imap.gmail.com")
                                            imap.login(sender_email, sender_password)
                                            status, response = imap.select(backup_folder)
                                            if status != 'OK': imap.create(backup_folder)
                                            imap.append(backup_folder, '\\Seen', imaplib.Time2Internaldate(time.time()), msg.as_bytes())
                                            imap.logout()
                                            backup_status = f"且已備份至 Gmail"
                                        except Exception as e:
                                            pass
                                        
                                        # 寫入寄件紀錄，包含是誰寄的
                                        if not is_sent:
                                            proj_data["sent_companies"].append({
                                                "company": selected_company,
                                                "sender": st.session_state.real_name
                                            })
                                            save_projects(projects_db)
                                        
                                        st.success(f"✅ 成功寄出 {backup_status}！")
                                        time.sleep(1.5)
                                        st.rerun()
                                        
                                    except Exception as e:
                                        st.error(f"❌ 寄件失敗：{e}")
                    
                    with btn_col2:
                        if is_sent:
                            st.success("✅ 已寄出")
                            
                except KeyError as e:
                    st.error(f"⚠️ 變數錯誤：{e}")