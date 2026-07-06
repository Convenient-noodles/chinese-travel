"""
预生成压测用户 Token，跳过 bcrypt 登录瓶颈
运行一次即可，生成 tokens.json
"""
import requests, json

BASE = "http://localhost:8000"
PASSWORD = "123456"
COUNT = 20

tokens = {}
for i in range(1, COUNT + 1):
    username = f"testuser_{i}"
    r = requests.post(f"{BASE}/api/auth/login", json={"username": username, "password": PASSWORD})
    if r.status_code == 200:
        tokens[username] = r.json()["access_token"]
        print(f"✅ {username}")
    else:
        print(f"❌ {username}: {r.status_code}")

# 同时获取 admin 的 token（用于知识库接口压测）
r = requests.post(f"{BASE}/api/auth/login", json={"username": "admin", "password": PASSWORD})
if r.status_code == 200:
    tokens["admin"] = r.json()["access_token"]
    print(f"✅ admin（管理员，用于知识库压测）")
else:
    print(f"⚠️  admin 登录失败: {r.status_code}，知识库接口将跳过")

with open("tokens.json", "w") as f:
    json.dump(tokens, f)

print(f"\n已保存 {len(tokens)} 个 Token 到 tokens.json")
