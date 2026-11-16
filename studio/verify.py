from playwright.sync_api import sync_playwright
import json, os
from pathlib import Path

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=os.environ.get("STUDIO_BROWSER_PATH"), headless=True, args=["--no-sandbox"])
    page = b.new_page(viewport={"width": 1487, "height": 1058}, device_scale_factor=1)
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
    page.goto(os.environ.get("STUDIO_URL", "http://127.0.0.1:4175/"))
    page.evaluate("document.fonts.ready")
    page.screenshot(path="evidence/desktop.png")
    page.locator("#source").select_option("失败用例")
    assert "没有记录" in page.locator("#paper").inner_text()
    page.locator("#empty").select_option("显示待补充")
    assert "待补充" in page.locator("#paper").inner_text()
    page.locator("#source").select_option("测试用例")
    page.locator("#repeat").select_option("仅首条记录")
    assert page.locator("#paper .block").count() == 1
    page.locator("#undo").click()
    assert page.locator("#paper .block").count() == 2
    page.locator("#redo").click()
    assert page.locator("#paper .block").count() == 1
    page.locator("#sample").click()
    page.locator("#data-input").fill("bad")
    page.locator("#apply-data").click()
    assert page.locator("#data-error").inner_text()
    data = [
        dict(
            id="QA-01",
            name="验证用例",
            steps=["输入数据"],
            expected="预期正常",
            actual="结果正常",
            result="通过",
        )
    ]
    page.locator("#data-input").fill(json.dumps(data, ensure_ascii=False))
    page.locator("#apply-data").click()
    assert "验证用例" in page.locator("#paper").inner_text()
    page.locator("#font-size").select_option("20")
    assert page.locator("#paper .block").evaluate("(el)=>getComputedStyle(el).fontSize") == "20px"
    page.locator("#preview").click()
    assert "预期正常" in page.locator("#preview-body").inner_text()
    assert "{{" not in page.locator("#preview-body").inner_text()
    page.screenshot(path="evidence/preview.png")
    page.keyboard.press("Escape")
    page.locator("[data-upload]").first.click()
    page.locator("#image-file").set_input_files("evidence/desktop.png")
    page.locator("#paper .upload img").wait_for()
    page.locator("#add-section").click()
    page.locator("#section-name").fill("附录")
    page.locator("#confirm-section").click()
    assert "附录" in page.locator("#paper h1").inner_text()
    with page.expect_download() as d:
        page.locator("#export").click()
    assert d.value.suggested_filename == "docxspec-template.json"
    page.set_viewport_size({"width": 390, "height": 844})
    page.locator('[data-nav="2"]').click()
    page.screenshot(path="evidence/mobile.png")
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.locator("#properties").click()
    assert page.locator(".props.drawer").is_visible()
    page.screenshot(path="evidence/mobile-properties.png")
    page.locator("#properties").click()
    assert errors == [], errors
    b.close()
    print(
        "PASS: sample validation, repetition, empty state, undo/redo, properties, resolved preview, image upload, sections, JSON download, mobile overflow, no JS errors"
    )
