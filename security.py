import os
import time
import json
import hashlib
import hmac
import secrets
from datetime import datetime
from filelock import FileLock

LOG_FILE = "security_audit.log"
LOG_LOCK = "security_audit.log.lock"

# ==========================================
# 1. PBKDF2 加鹽密碼保護與驗證 (PBKDF2 Hashing)
# ==========================================
PBKDF2_ITERATIONS = 100000

def generate_salted_password_hash(password: str) -> str:
    """使用 PBKDF2-HMAC-SHA256 搭配 16-byte 隨機 Salt 產生加密字串"""
    salt = secrets.token_bytes(16)
    hash_bytes = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2:sha256:{PBKDF2_ITERATIONS}${salt.hex()}${hash_bytes.hex()}"

def verify_password(stored_hash: str, provided_password: str) -> bool:
    """驗證密碼，相容舊版單純 SHA-256 與新版 PBKDF2 加鹽密碼"""
    if not stored_hash or not provided_password:
        return False
    
    # 判斷是否為新版 PBKDF2 格式 (pbkdf2:sha256:iterations$salt$hash)
    if stored_hash.startswith("pbkdf2:sha256:"):
        try:
            parts = stored_hash.split("$")
            if len(parts) != 3:
                return False
            header, salt_hex, hash_hex = parts
            iterations = int(header.split(":")[2])
            salt = bytes.fromhex(salt_hex)
            expected_hash = bytes.fromhex(hash_hex)
            
            calculated_hash = hashlib.pbkdf2_hmac('sha256', provided_password.encode('utf-8'), salt, iterations)
            return hmac.compare_digest(calculated_hash, expected_hash)
        except Exception:
            return False
    else:
        # 舊版 SHA-256 雜湊驗證
        legacy_hash = hashlib.sha256(provided_password.encode('utf-8')).hexdigest()
        return hmac.compare_digest(legacy_hash, stored_hash)

def is_legacy_hash(stored_hash: str) -> bool:
    """檢查密碼是否仍為舊版 SHA-256，用以執行無感升級"""
    return not stored_hash.startswith("pbkdf2:sha256:")

# ==========================================
# 2. 外網數據異常擷取/扒取偵測器 (Anti-Scraping Detector)
# ==========================================
class ScrapingDetector:
    """使用滑動窗口 (Sliding Window) 演算法追蹤存取頻率，防範外網爬蟲扒取」"""
    def __init__(self, window_seconds=60):
        self.window_seconds = window_seconds
        self.history = {}  # {client_id: [timestamp1, timestamp2, ...]}

    def record_access(self, client_id: str, threshold_per_minute=30):
        """記錄一次資料存取，若 1 分鐘內超過 threshold_per_minute 則回傳警報標籤"""
        now = time.time()
        if client_id not in self.history:
            self.history[client_id] = []

        # 過濾窗口外的舊時間戳
        cutoff = now - self.window_seconds
        self.history[client_id] = [t for t in self.history[client_id] if t > cutoff]
        self.history[client_id].append(now)

        current_count = len(self.history[client_id])
        is_suspicious = current_count > threshold_per_minute

        warning_msg = None
        if is_suspicious:
            warning_msg = f"⚠️ [外網擷取警報] ID [{client_id}] 在 60 秒內讀取 {current_count} 次資料 (超過標準 {threshold_per_minute} 次/分)"

        return is_suspicious, current_count, warning_msg

# 全域單例偵測器
scraping_detector = ScrapingDetector()

# ==========================================
# 3. 資安稽核日誌記錄器 (Security Audit Logger)
# ==========================================
def log_security_event(event_type: str, username: str, status: str, details: str, client_ip: str = "127.0.0.1"):
    """將資安事件原子化寫入 security_audit.log"""
    timestamp = datetime.now().isoformat(timespec='seconds')
    log_entry = f"[{timestamp}] [{event_type}] [User: {username}] [IP: {client_ip}] [Status: {status}] - {details}\n"

    try:
        with FileLock(LOG_LOCK, timeout=5):
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(log_entry)
    except Exception as e:
        print(f"❌ 寫入資安日誌失敗: {e}")

def get_recent_security_logs(max_entries=100):
    """讀取最新的資安稽核日誌條目，供管理員後台審閱"""
    if not os.path.exists(LOG_FILE):
        return []
    try:
        with FileLock(LOG_LOCK, timeout=5):
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()
                return [line.strip() for line in lines[-max_entries:]]
    except Exception:
        return []

# ==========================================
# 4. 會話閒置自動保護 (Session Timeout Manager)
# ==========================================
def check_session_timeout(last_active_timestamp: float, timeout_seconds=1800) -> bool:
    """檢查會話是否閒置超過 timeout_seconds (預設 30 分鐘 = 1800 秒)"""
    if not last_active_timestamp:
        return False
    return (time.time() - last_active_timestamp) > timeout_seconds
