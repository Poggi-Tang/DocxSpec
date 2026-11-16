"""Additional acceptance regressions: active edits, disk reopen and real generation."""

import json
from pathlib import Path
import os
from playwright.sync_api import sync_playwright

root = Path(__file__).resolve().parent
base_url = os.environ.get("STUDIO_URL", "http://127.0.0.1:4175").rstrip("/")
with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path=os.environ.get("STUDIO_BROWSER_PATH"), headless=True, args=["--no-sandbox"]
    )
    page = browser.new_page()
    page.goto(base_url + "/")
    page.wait_for_function(
        "document.querySelector('#save-status').textContent!=='尚未保存到模板库'"
    )
    for selector, value in [
        ('[data-name="0"]', "未失焦名称"),
        ('[data-field="actual"][data-index="0"]', "未失焦实际结果"),
        ('[data-field="steps"][data-index="0"][data-step="0"]', "未失焦步骤"),
        ("#intro", "未失焦章节说明"),
    ]:
        page.locator(selector).fill(value)
        page.reload()
        page.wait_for_function(
            "([selector,value])=>document.querySelector(selector)?.textContent===value",
            arg=[selector, value],
        )
    page.locator('[data-name="0"]').fill("撤销后不能保留")
    page.locator("#undo").click()
    assert page.locator('[data-name="0"]').inner_text() == "未失焦名称"
    page.locator("#redo").click()
    assert page.locator('[data-name="0"]').inner_text() == "撤销后不能保留"
    page.locator('[data-nav="0"]').click()
    page.locator("#section-text").fill("未失焦封面正文")
    page.reload()
    page.wait_for_function(
        "document.querySelector('#section-text')?.textContent==='未失焦封面正文'"
    )
    records = page.request.get(base_url + "/api/templates").json()
    assert records
    record = page.request.get(base_url + "/api/templates/" + records[0]["id"]).json()
    data = record["document"]
    data["cases"] = data["cases"][:1]
    # Test maximum supported number of cases, with plain text and no media.
    data["cases"] = [
        {
            **data["cases"][0],
            "id": f"LOAD-{i + 1:03}",
            "name": f"长报告用例{i + 1}",
            "steps": ["中文步骤" * 30] * 3,
        }
        for i in range(100)
    ]
    for c in data["cases"]:
        c.pop("image", None)
    data["selected"] = 0
    data["source"] = "测试用例"
    data["repeat"] = "每条记录"
    response = page.request.post(base_url + "/api/render", data=data, timeout=60000)
    assert response.status == 200
    (root / "evidence/acceptance/100-cases.docx").write_bytes(response.body())
    data["cases"].append(data["cases"][0])
    assert page.request.post(base_url + "/api/render", data=data).status == 400
    browser.close()
print(
    "PASS: unblurred edits survive reload, undo/redo, chapter text, 100-case DOCX and 101-case rejection"
)
