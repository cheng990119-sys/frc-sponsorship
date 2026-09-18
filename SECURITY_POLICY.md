# 公關寄信系統 - 網頁資安管理規範與外網異常讀取防護指南
**Web Application Security Management Policy & External Access Control Guidelines**

---

## 📋 一、 文件簡介與適用範圍 (Overview & Scope)

### 1.1 目的
本規範旨在為「公關寄信系統 (FRC Sponsorship Mail System)」建立一套符合業界資安範疇（OWASP Top 10）之內部安全管理標準，專力強化對外網異常讀取、自動化資料擷取 (Scraping) 與憑證保護之管控，確保系統營運穩定與資料隱私。

### 1.2 適用對象
本規範適用於系統開發人員、網站營運管理員及所有登入系統使用之團隊成員。

---

## 🔐 二、 帳戶與身分認證資安規範 (Authentication & Account Policy)

### 2.1 密碼安全與加鹽儲存規範 (Salted Password Standard)
- **雜湊演算法**：系統密碼儲存嚴禁採用明文或無鹽單向雜湊（如單純 SHA-256/MD5）。強制採用帶有 16-byte 隨機 Salt 之 **PBKDF2-HMAC-SHA256**（迭代次數至少 10,000 次），抵禦彩虹表與字典攻擊。
- **平滑遷移**：若系統中存在舊版雜湊，應於帳號驗證通過時於背景自動無感升級為加鹽雜湊。

### 2.2 登入體驗與嘗試彈性 (Login Policy)
- **無鎖定限制**：為確保維運與使用者存取彈性，系統**不強制鎖定密碼輸入錯誤之帳號**。
- **連發與異常紀錄**：雖然不阻擋錯誤嘗試，但系統必須於背景側記錄異常頻繁的嘗試行為，供日後資安稽核。

### 2.3 發信憑證隔離規範 (Credential Isolation Standard)
- **記憶體隔離**：團隊 Gmail 帳號與應用程式密碼 (App Password) 僅得保存在當次會話記憶體 (`st.session_state`) 中。
- **禁止落盤**：嚴禁將發信密碼寫入硬碟 JSON 檔、Log 日誌或前端網頁 DOM 原始碼中。

---

## 🛡️ 三、 外網異常讀取與防擷取管理規範 (Anti-Scraping & Data Protection)

### 3.1 外網數據存取頻率控制 (Access Rate Limiting)
- **頻率上限設定**：針對外網 IP 與單一 Session，限制廠商資料切換與查看之上限（建議標準為每分鐘不超過 30 次）。
- **滑動窗口監控**：採用滑動窗口 (Sliding Window) 演算法計數，防止自動化腳本以微小間隔連發請求。

### 3.2 外網異常擷取偵測機制 (Scraping Anomaly Detection)
- **行為特徵識別**：當偵測到超越常規人類閱讀速度（如 1 秒內連續讀取多筆廠商 Email）時，系統判定為「外網異常擷取行為」。
- **警報與日誌記錄**：系統將自動於內部觸發資安警報標籤，並即時寫入資安稽核日誌。

### 3.3 敏感資料傳輸與隱私保護 (Data Privacy & DLP)
- **Excel 檔案安全**：上傳之贊助商 Excel 名單僅存於當次會話，不提供公開網址下載。
- **欄位邊界校驗**：解析聯絡資訊時嚴格執行 Regex Email 校驗，過濾非法腳本注入。

---

## ⏱️ 四、 會話與網路傳輸安全規範 (Session & Network Security)

### 4.1 會話閒置自動保護 (Session Timeout)
- **閒置銷毀**：使用者登入後若連續 30 分鐘無任何介面互動，系統應自動銷毀 Session 並退回登入頁面，防止設備未關閉造成資訊洩漏。

### 4.2 連線逾時與 Socket 保護 (Connection Timeout Policy)
- **SMTP 連線保護**：使用 `smtplib.SMTP` (Port 587 STARTTLS) 發信時，強制設定 10 秒 Socket 連線逾時。
- **IMAP4 備份保護**：使用 `imaplib.IMAP4_SSL` (Port 993) 備份信件時，強制設定 10 秒 Timeout，避免網路延遲造成連線池卡死與伺服器資源耗盡。

---

## 📊 五、 資安稽核與日誌管理規範 (Security Audit & Logging)

### 5.1 稽核日誌維護 (`security_audit.log`)
- 系統必須建立獨立的資安稽核日誌檔，記錄格式規範如下：
  `[ISO8601 時間戳記] [事件類型] [使用者/IP] [狀態] [詳細說明]`
- **稽核事件類別包含**：
  - `LOGIN_SUCCESS`：登入成功
  - `LOGIN_FAILURE`：登入失敗（記錄帳號，不限制鎖定）
  - `SCRAPING_WARNING`：外網高頻異常擷取告警
  - `CREDENTIAL_UPDATE`：帳號建立或密碼變更
  - `DATA_ACCESS`：大量廠商資料導出/讀取

### 5.2 日誌存取與後台審閱規範
- 僅具備 `admin` 權限之管理員可於系統後台檢視稽核日誌摘要。
- 資安日誌檔應具備獨立存取權限，禁止未授權修改與刪除。

---

## 🚀 六、 後續內部運作功能優化藍圖 (Operational Roadmap)

本資安規範完成核可後，後續內部運作優化將依下列順序推進：

1. **第一階段（資安實作）**：建立 `security.py` 模組，實作 PBKDF2 加鹽、外網異常擷取偵測器與資安日誌。
2. **第二階段（運作優化）**：重構 `app.py` 後台管理介面，新增「資安稽核日誌」審閱分頁。
3. **第三階段（效能與併發）**：延續併發檔案鎖與 openpyxl 高效讀取，優化頁面加載速度。

---
