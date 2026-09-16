import sys
import os
import json
import io
import openpyxl

sys.stdout.reconfigure(encoding='utf-8')

from app import (
    load_users, save_users, load_projects, save_projects,
    hash_password, safe_format_template, extract_email, read_excel_data,
    USERS_FILE, PROJECTS_FILE
)

def test_user_management():
    print("[1/5] 驗證使用者管理與密碼加密功能...")
    users = load_users()
    assert "admin" in users, "預設 admin 帳號應存在"
    assert users["admin"]["password"] == hash_password("admin123"), "預設密碼哈希比對應成功"
    
    # 測試新增帳號
    test_username = "test_opt_user"
    users[test_username] = {
        "password": hash_password("secret456"),
        "role": "user",
        "real_name": "測試成員"
    }
    save_users(users)
    
    reloaded_users = load_users()
    assert test_username in reloaded_users, "新增帳號應成功寫入並可重新載入"
    assert reloaded_users[test_username]["real_name"] == "測試成員"
    print("   ✅ 使用者管理與密碼哈希驗證通過！")

def test_project_management():
    print("[2/5] 驗證專案管理與寄件紀錄功能...")
    projects = load_projects()
    test_proj = "系統優化測試專案"
    projects[test_proj] = {
        "sent_companies": [{"company": "測試科技", "sender": "測試成員"}],
        "template": "Hello {企業／贊助單位}"
    }
    save_projects(projects)
    
    reloaded_projects = load_projects()
    assert test_proj in reloaded_projects, "專案建立應成功寫入"
    assert len(reloaded_projects[test_proj]["sent_companies"]) == 1
    print("   ✅ 專案管理與資料寫入驗證通過！")

def test_template_formatting():
    print("[3/5] 驗證 SafeFormatter 信件範本替換防爆機制...")
    context = {
        "企業／贊助單位": "聯發科技",
        "team_name": "FRC 7636",
        "contact_person": "李四",
        "sender_email": "team7636@gmail.com",
        "pdf_filename": "企劃書.pdf"
    }
    
    # 測試正常替換
    template1 = "致 {企業／贊助單位}，我們是 {team_name}。"
    res1 = safe_format_template(template1, context)
    assert "聯發科技" in res1 and "FRC 7636" in res1
    
    # 測試含未定義變數與特殊大括號
    template2 = "致 {企業／贊助單位}，贊助項目 {100%} 需求：{missing_var}"
    res2 = safe_format_template(template2, context)
    assert "聯發科技" in res2
    assert "{100%}" in res2
    assert "{missing_var}" in res2
    
    print("   ✅ SafeFormatter 防爆與邊界條件替換驗證通過！")

def test_email_extraction():
    print("[4/5] 驗證 Email 解析器健壯性...")
    assert extract_email("聯絡人: 王小明 email: test@example.com 電話: 0912345678") == "test@example.com"
    assert extract_email("service.support-center@company.org.tw") == "service.support-center@company.org.tw"
    assert extract_email("無 Email 資訊") is None
    assert extract_email(None) is None
    assert extract_email("") is None
    print("   ✅ Email 解析功能驗證通過！")

def test_excel_reading():
    print("[5/5] 驗證 openpyxl Excel 相容讀取器...")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "全部彙總清單"
    ws.append(["編號", "企業／贊助單位", "聯絡資訊", "說明與贊助契機"])
    ws.append([1, "台積電", "contact@tsmc.com", "硬體設備贊助"])
    ws.append([2, "鴻海", "pr@foxconn.com", "材料經費支持"])
    
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    
    records = read_excel_data(buf)
    assert len(records) == 2, f"應解析出 2 筆記錄，實際解析出 {len(records)} 筆"
    assert records[0]["企業／贊助單位"] == "台積電"
    assert records[1]["聯絡資訊"] == "pr@foxconn.com"
    print("   ✅ openpyxl Excel 相容讀取器驗證通過！")

if __name__ == "__main__":
    print("=" * 60)
    print("      公關寄信系統 - 系統功能與架構優化確認測試")
    print("=" * 60)
    
    try:
        test_user_management()
        test_project_management()
        test_template_formatting()
        test_email_extraction()
        test_excel_reading()
        print("\n" + "=" * 60)
        print("🎉 系統優化確認完成：所有功能模組、邊界防禦與數據模組 100% 通過驗證！")
        print("=" * 60)
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ 測試過程發現問題: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
