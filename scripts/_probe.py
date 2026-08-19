# -*- coding: utf-8 -*-
"""临时探针：v4-pro 对真实命理题返回什么（4000 tokens）。"""
import json
import re
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")
text = open(r"E:\data\DeepSeekHarness\home\.credentials.yaml", encoding="utf-8").read()
key = re.search(r"^DEEPSEEK_API_KEY:\s*[\"']?([^\"'\s]+)", text, re.M).group(1)

pack = json.load(open(r"E:\data\repos\bazi-entity-v3\dist\mingli-pack.json", encoding="utf-8"))
it = pack["items"][0]
options = "\n".join(f"{o['letter']}. {o['text']}" for o in it["options"])
prompt = (
    "你是资深命理师。基于以下四柱盘面与 BFFT 判据（clues），"
    "回答题目。只输出一个字母（A/B/C/D），不要解释。\n\n"
    f"题目：{it['question']}\n"
    f"选项：\n{options}\n\n"
    f"四柱：{it['chart']['four_pillars']}\n"
    f"日主：{it['chart']['day_master']}\n\n"
    f"判据：{it.get('clues', '')}"
)
body = json.dumps({
    "model": "deepseek-v4-pro",
    "messages": [{"role": "user", "content": prompt}],
    "temperature": 0,
    "max_tokens": 4000,
    "reasoning_effort": "low",
}).encode()
req = urllib.request.Request("https://api.deepseek.com/chat/completions", data=body, headers={
    "Content-Type": "application/json",
    "Authorization": f"Bearer {key}",
})
r = json.loads(urllib.request.urlopen(req, timeout=180).read())
msg = r["choices"][0]["message"]
print("content:", repr(msg.get("content")))
print("reasoning tail:", repr((msg.get("reasoning_content") or "")[-200:]))
print("finish_reason:", r["choices"][0].get("finish_reason"))
