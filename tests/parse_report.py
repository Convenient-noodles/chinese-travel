"""解析 Locust HTML 报告，提取关键数据"""
import re, json, sys

html_file = sys.argv[1] if len(sys.argv) > 1 else "Locust_2026-07-06-18h45_locustfile.py_http___localhost_8000.html"

with open(html_file, "r", encoding="utf-8") as f:
    html = f.read()

# 提取 stats
m = re.search(r'"stats":(\[.*?\]),"errors"', html, re.DOTALL)
if not m:
    m = re.search(r'"stats":(\[.*?\])', html, re.DOTALL)

if m:
    stats = json.loads(m.group(1))
    print(f"\n{'='*75}")
    print(f"{'接口':<18s} {'成功':>6s} {'失败':>6s} {'P50':>8s} {'P95':>8s} {'最大':>8s}")
    print(f"{'='*75}")
    for s in stats:
        name = s["name"]
        ok = s["num_requests"] - s["num_failures"]
        total = s["num_requests"]
        fail_rate = s["num_failures"] / total * 100 if total else 0
        print(f"{name:<18s} {ok:>3d}/{total:<3d} {s['num_failures']:>4d}  "
              f"{s['median_response_time']:>6.0f}ms {s.get('response_time_percentile_0.95',0):>6.0f}ms "
              f"{s['max_response_time']:>6.0f}ms  ({fail_rate:.0f}%)")
    print(f"{'='*75}")
else:
    print("未找到 stats 数据")

# 提取 errors
m2 = re.search(r'"errors":(\[.*?\])', html, re.DOTALL)
if m2:
    errors = json.loads(m2.group(1))
    if errors:
        print(f"\n失败详情 ({len(errors)}种类型):")
        for e in errors:
            print(f"  [{e['name']}] x{e['occurrences']}: {e['error'][:150]}")
    else:
        print("\n无失败记录 ✅")
