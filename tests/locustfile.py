"""
旅伴系统 — 压力测试脚本（免登录版）

用法:
    1. python gen_tokens.py          # 预生成 Token（一次性）
    2. locust -f locustfile.py --host=http://localhost:8000

优化:
    - 预生成 Token 跳过 bcrypt 登录，专注测 SSE + DB 并发
    - 每个用户随机选一个 Token，模拟多用户分布
"""

import random, json, time
from locust import HttpUser, task, between, events

# ============================================================
SSE_TIMEOUT = 120

with open("test_questions.json", "r", encoding="utf-8") as f:
    TEST_QUESTIONS = json.load(f)

with open("tokens.json", "r", encoding="utf-8") as f:
    _all_tokens = json.load(f)
    TOKENS = [v for k, v in _all_tokens.items() if k != "admin"]
    ADMIN_TOKEN = _all_tokens.get("admin")

print(f"已加载 {len(TOKENS)} 个普通用户 Token | {len(TEST_QUESTIONS)} 条问题")
if ADMIN_TOKEN:
    print(f"已加载管理员 Token（用于知识库压测）")
else:
    print(f"⚠️  未找到管理员 Token，知识库接口将跳过")


@events.init.add_listener
def on_init(environment, **kwargs):
    print("=" * 60)
    print(f"  免登录模式 — 专注测 SSE + DB 并发")
    print("=" * 60)


class TourismUser(HttpUser):
    wait_time = between(2, 5)

    def on_start(self):
        """直接用预生成 Token，跳过登录"""
        self.token = random.choice(TOKENS)
        self.client.headers["Authorization"] = f"Bearer {self.token}"
        self.conv_id = None  # 初始化，防止 AttributeError

        # 快速创建会话
        with self.client.post(
            "/api/conversations",
            json={"title": "压测"},
            catch_response=True,
            name="01_创建会话",
        ) as r:
            if r.status_code in (200, 201):
                self.conv_id = r.json().get("id")
                r.success()
            else:
                r.failure(f"status={r.status_code} body={r.text[:100]}")

    @task(70)
    def chat(self):
        if not hasattr(self, "token"):
            return
        q = random.choice(TEST_QUESTIONS)
        with self.client.post(
            "/api/chat/stream",
            json={"message": q, "conversation_id": self.conv_id},
            stream=True,
            timeout=SSE_TIMEOUT,
            catch_response=True,
            name="02_SSE问答",
        ) as r:
            if r.status_code != 200:
                r.failure(f"HTTP {r.status_code} body={r.text[:120]}")
                return
            for line in r.iter_lines(decode_unicode=True):
                if "event: done" in line:
                    r.success()
                    return
                if "event: error" in line:
                    r.failure(line[:200])
                    return
            # 流结束但未收到 done/error → 超时
            r.failure("SSE stream ended without done/error event")

    @task(15)
    def list_conv(self):
        if not hasattr(self, "token"):
            return
        self.client.get("/api/conversations?page=1&page_size=10", name="03_会话列表")

    @task(10)
    def multi_turn(self):
        if not self.conv_id:
            return
        for q in random.sample(TEST_QUESTIONS, 3):
            with self.client.post(
                "/api/chat/stream",
                json={"message": q, "conversation_id": self.conv_id},
                stream=True,
                timeout=SSE_TIMEOUT,
                catch_response=True,
                name="04_多轮对话",
            ) as r:
                if r.status_code != 200:
                    r.failure(f"HTTP {r.status_code} body={r.text[:120]}")
                    return
                for line in r.iter_lines(decode_unicode=True):
                    if "event: done" in line:
                        r.success()
                        break
                    if "event: error" in line:
                        r.failure(line[:200])
                        return
                else:
                    r.failure("SSE stream ended without done/error event")
                    return
            time.sleep(random.uniform(1, 3))

    @task(5)
    def knowledge(self):
        if not ADMIN_TOKEN:
            return  # 没有管理员 Token，跳过
        # 使用管理员 Token 访问知识库
        headers = {"Authorization": f"Bearer {ADMIN_TOKEN}"}
        with self.client.get(
            "/api/admin/knowledge?page=1&page_size=10",
            headers=headers,
            catch_response=True,
            name="05_知识库",
        ) as r:
            if r.status_code == 200:
                r.success()
            else:
                r.failure(f"HTTP {r.status_code} body={r.text[:120]}")
