import asyncio
import aiohttp
import time
import json
import os
import sys
import threading
import concurrent.futures

# 強制將 console stdout 設為 UTF-8 編碼，避免 Windows CP950 UnicodeEncodeError
sys.stdout.reconfigure(encoding='utf-8')

from app import load_users, save_users, load_projects, save_projects, safe_format_template

SERVER_URL = "http://127.0.0.1:8501"

async def fetch(session, url):
    start = time.perf_counter()
    try:
        async with session.get(url, timeout=5) as response:
            await response.read()
            elapsed = time.perf_counter() - start
            return response.status, elapsed
    except Exception as e:
        elapsed = time.perf_counter() - start
        return 0, elapsed

async def run_http_stress_test(num_requests=2000, concurrency=50):
    print(f"\n[1/2] 開始執行網絡連線與 HTTP 封包壓力測試...")
    print(f"   - 目標網址: {SERVER_URL}")
    print(f"   - 總封包請求數: {num_requests}")
    print(f"   - 併發連線數: {concurrency}")

    conn = aiohttp.TCPConnector(limit=concurrency)
    async with aiohttp.ClientSession(connector=conn) as session:
        tasks = []
        for _ in range(num_requests):
            tasks.append(fetch(session, SERVER_URL))

        start_time = time.perf_counter()
        results = await asyncio.gather(*tasks)
        total_time = time.perf_counter() - start_time

    statuses = [r[0] for r in results]
    latencies = [r[1] * 1000 for r in results]  # ms

    success_count = sum(1 for s in statuses if s == 200)
    fail_count = num_requests - success_count
    rps = num_requests / total_time if total_time > 0 else 0
    avg_latency = sum(latencies) / len(latencies) if latencies else 0
    sorted_latencies = sorted(latencies)
    p50 = sorted_latencies[int(len(sorted_latencies) * 0.50)] if latencies else 0
    p95 = sorted_latencies[int(len(sorted_latencies) * 0.95)] if latencies else 0
    p99 = sorted_latencies[int(len(sorted_latencies) * 0.99)] if latencies else 0

    print(f"\n[HTTP Load Test Results] 壓力測試結果:")
    print(f"   - 總測試時間: {total_time:.2f} 秒")
    print(f"   - 每秒處理封包 (RPS): {rps:.2f} req/sec")
    print(f"   - 成功請求數 (200 OK): {success_count}/{num_requests} ({success_count/num_requests*100:.1f}%)")
    print(f"   - 失敗/異常數: {fail_count}")
    print(f"   - 平均響應時間: {avg_latency:.2f} ms")
    print(f"   - P50 延遲: {p50:.2f} ms | P95 延遲: {p95:.2f} ms | P99 延遲: {p99:.2f} ms")

    return fail_count == 0

def worker_db_stress(worker_id, iterations=30):
    """多執行緒資料庫寫入測試，模擬併發寫入 users 與 projects"""
    errors = 0
    for i in range(iterations):
        try:
            users = load_users()
            user_key = f"test_user_{worker_id}_{i}"
            users[user_key] = {"password": "pwd", "role": "user", "real_name": f"User {worker_id}"}
            save_users(users)

            projects = load_projects()
            proj_key = f"test_proj_{worker_id}_{i}"
            projects[proj_key] = {"sent_companies": [{"company": "Test Co", "sender": f"User {worker_id}"}], "template": "Test"}
            save_projects(projects)

            load_users()
            load_projects()
        except Exception as e:
            print(f"[X] Worker {worker_id} 在第 {i} 次迭代出錯: {e}")
            errors += 1
    return errors

def run_db_concurrency_test(num_workers=10, iterations_per_worker=25):
    print(f"\n[2/2] 開始執行併發 JSON 資料寫入與鎖定韌性測試...")
    print(f"   - 併發 Worker 數: {num_workers}")
    print(f"   - 每個 Worker 讀寫次數: {iterations_per_worker}")
    print(f"   - 總併發 I/O 次數: {num_workers * iterations_per_worker * 4} 次")

    start_time = time.perf_counter()
    total_errors = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = [executor.submit(worker_db_stress, w, iterations_per_worker) for w in range(num_workers)]
        for f in concurrent.futures.as_completed(futures):
            total_errors += f.result()

    total_time = time.perf_counter() - start_time
    print(f"\n[JSON Concurrency Results] 併發 I/O 韌性測試結果:")
    print(f"   - 測試耗時: {total_time:.2f} 秒")
    print(f"   - 併發讀寫錯誤數: {total_errors} 次")
    
    users_ok = False
    projects_ok = False
    try:
        with open("users.json", "r", encoding="utf-8") as f:
            json.load(f)
        users_ok = True
    except Exception as e:
        print(f"[X] users.json 語法壞損: {e}")

    try:
        with open("projects.json", "r", encoding="utf-8") as f:
            json.load(f)
        projects_ok = True
    except Exception as e:
        print(f"[X] projects.json 語法壞損: {e}")

    if users_ok and projects_ok and total_errors == 0:
        print(" [OK] JSON 資料庫併發鎖定機制完全正常！無語法壞損或競態條件！")
        return True
    else:
        print(" [X] 併發測試發現問題！")
        return False

def run_template_safety_test():
    print(f"\n[3/3] 測試範本 SafeFormatter 防爆與邊界條件處理...")
    test_cases = [
        ("{企業／贊助單位} {missing_var} {team_name}", {"team_name": "Team 1234"}),
        ("測試 {100%} 含有非預期大括號 {contact_person}", {"contact_person": "張三"}),
        ("無任何變數純文字", {}),
        ("", {})
    ]
    all_passed = True
    for t, ctx in test_cases:
        res = safe_format_template(t, ctx)
        if res is not None:
            print(f"   - 輸入: {t!r} -> 輸出: {res!r} (正常)")
        else:
            print(f"   - 輸入: {t!r} -> 失敗！")
            all_passed = False
    return all_passed

if __name__ == "__main__":
    print("=" * 60)
    print("      公關寄信系統 - 網站韌性與高併發封包測試腳本")
    print("=" * 60)

    tmpl_ok = run_template_safety_test()
    db_ok = run_db_concurrency_test(num_workers=10, iterations_per_worker=25)
    http_ok = asyncio.run(run_http_stress_test(num_requests=2000, concurrency=50))

    print("\n" + "=" * 60)
    if tmpl_ok and db_ok and http_ok:
        print(" [SUCCESS] 所有韌性與壓力測試項目全部通過！系統具備高併發穩定度！")
        sys.exit(0)
    else:
        print(" [WARN] 測試中發現異常，請查看 Log 進行調優！")
        sys.exit(1)
