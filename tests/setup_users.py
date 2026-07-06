"""
批量创建压测用户账号
运行前请确保后端服务已启动: python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

使用方法:
    cd tests
    python setup_users.py
"""

import requests
import sys

BASE = "http://localhost:8000"
USER_COUNT = 20
PASSWORD = "123456"

print(f"正在向 {BASE} 批量注册 {USER_COUNT} 个压测用户...\n")

success = 0
failed = 0

for i in range(1, USER_COUNT + 1):
    username = f"testuser_{i}"
    try:
        resp = requests.post(
            f"{BASE}/api/auth/register",
            json={
                "username": username,
                "password": PASSWORD,
                "nickname": f"压测用户{i:02d}",
            },
            timeout=10,
        )
        if resp.status_code in (200, 201):
            print(f"  ✅ {username}")
            success += 1
        elif resp.status_code == 409 or "已存在" in resp.text or "已被" in resp.text:
            print(f"  ⏭️  {username}（已存在，跳过）")
            success += 1  # 已存在也能用于压测
        else:
            print(f"  ❌ {username} — {resp.status_code}: {resp.text[:80]}")
            failed += 1
    except requests.ConnectionError:
        print("\n❌ 无法连接后端服务！请确认服务已启动:")
        print("   cd backend && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000")
        sys.exit(1)

# 确保 admin 账号存在（用于知识库压测）
print("\n检查管理员账号...")
try:
    resp = requests.post(
        f"{BASE}/api/auth/login",
        json={"username": "admin", "password": "123456"},
        timeout=10,
    )
    if resp.status_code == 200:
        print("  ✅ admin 账号已可用")
    else:
        print(f"  ⚠️  admin 登录失败: {resp.status_code}，请手动创建管理员账号")
except Exception as e:
    print(f"  ⚠️  admin 检查异常: {e}")

print(f"\n{'='*50}")
print(f"完成: {success} 个账号可用, {failed} 个失败")
print(f"账号格式: testuser_1 ~ testuser_{USER_COUNT}, 密码统一: {PASSWORD}")
print(f"管理员: admin / {PASSWORD}（用于知识库接口压测）")
print(f"{'='*50}")
