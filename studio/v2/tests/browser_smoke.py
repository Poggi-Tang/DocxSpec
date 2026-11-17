import hashlib
import json
import os
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

out = str(Path(__file__).resolve().parents[1] / "evidence")
Path(out).mkdir(exist_ok=True)
base = os.environ.get("STUDIO_TEST_URL", "http://127.0.0.1:4177")
with sync_playwright() as p:
    b = p.chromium.launch(
        executable_path=os.environ.get("STUDIO_CHROMIUM", "/usr/bin/chromium"),
        headless=True,
        args=["--no-sandbox"],
    )
    page = b.new_page(viewport={"width": 1440, "height": 1000}, device_scale_factor=1)
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(base)
    page.get_by_text("模板管理", exact=True).wait_for()
    set_name = "产品测试模板集 " + str(time.time())
    page.once("dialog", lambda d: d.accept(set_name))
    page.get_by_role("button", name="新建模板集").click()
    page.get_by_role("button", name=set_name, exact=True).wait_for()
    page.once("dialog", lambda d: d.accept("功能测试报告"))
    page.get_by_role("button", name="新建模板", exact=True).click()
    page.get_by_label("模板名称").wait_for()
    page.get_by_role("button", name="一级标题 DS 内置", exact=True).click()
    page.get_by_label("组件名称", exact=True).fill("验收结论")
    page.get_by_label("内容", exact=True).fill("验收结论")
    page.get_by_label("字号（pt）").fill("18")
    page.once("dialog", lambda d: d.accept("报告结论标题"))
    page.get_by_role("button", name="保存为新组件", exact=True).click()
    page.get_by_role("button", name="报告结论标题 我的组件 · v1").wait_for()
    # Native drag into structure, then choose parent container.
    page.get_by_role("button", name="正文 DS 内置", exact=True).drag_to(page.locator(".canvas"))
    page.get_by_label("内容", exact=True).fill("所有功能测试结果已记录，请审核。")
    page.get_by_role("button", name="保存", exact=True).click()
    page.get_by_text("已保存 v2", exact=True).wait_for()
    page.get_by_label("排版引擎").select_option("libreoffice")
    page.get_by_role("button", name="更新预览", exact=True).click()
    page.locator(".pdf-page canvas").first.wait_for(timeout=150000)
    page.wait_for_timeout(1500)
    page.screenshot(path=out + "/studio-real-preview.png", full_page=True)
    assert page.locator(".pdf-page canvas").count() > 0
    assert not page.get_by_role("button", name="DOCX", exact=True).is_disabled()
    manifest_url = page.get_by_role("link", name="产物记录").get_attribute("href")
    manifest = json.load(urllib.request.urlopen(base + manifest_url))
    for name, expected in manifest["hashes"].items():
        raw = urllib.request.urlopen(base + manifest_url.replace("manifest.json", name)).read()
        assert hashlib.sha256(raw).hexdigest() == expected
        open(out + "/" + name, "wb").write(raw)
    page.get_by_label("内容", exact=True).fill("修改后应显示预览已过期。")
    page.get_by_text("模板已修改，以下为旧预览 · 请更新").wait_for()
    assert page.get_by_role("button", name="DOCX", exact=True).is_disabled()
    page.screenshot(path=out + "/studio-stale-preview.png", full_page=True)
    page.get_by_role("button", name="保存", exact=True).click()
    page.get_by_text("已保存 v4", exact=True).wait_for()
    page.reload()
    page.get_by_role("button", name=set_name, exact=True).click()
    page.get_by_role("button", name="功能测试报告", exact=True).click()
    page.locator(".tree-node").filter(has_text="正文").last.click()
    assert page.get_by_label("内容", exact=True).input_value() == "修改后应显示预览已过期。"
    page.get_by_role("button", name="AI 转化模板", exact=True).click()
    page.get_by_text("尚未配置模型服务。", exact=False).wait_for()
    assert page.locator("input[type=file]").is_disabled()
    assert errors == [], errors
    open(out + "/browser-result.json", "w").write(
        json.dumps(
            {
                "passed": True,
                "browser_errors": errors,
                "pages": manifest["pages"],
                "engine": manifest["engine_version"],
                "hashes": manifest["hashes"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    b.close()
print("Browser flow passed")
