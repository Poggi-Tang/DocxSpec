"""End-to-end browser test against server.py, including real downloaded DOCX."""

from pathlib import Path
import io
import json
import zipfile
from playwright.sync_api import sync_playwright

root = Path(__file__).resolve().parent
(root / "evidence").mkdir(exist_ok=True)
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/usr/bin/chromium", headless=True, args=["--no-sandbox"])
    context = b.new_context(viewport={"width": 1487, "height": 1058}, device_scale_factor=1)
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto("http://127.0.0.1:4175/")
    page.wait_for_function(
        "document.querySelector('#save-status').textContent!=='尚未保存到模板库'"
    )
    page.locator('[data-name="0"]').fill("浏览器实测登录")
    page.locator("#save-template").click()
    page.locator("#template-name").fill("浏览器实测模板")
    page.locator("#confirm-save").click()
    page.locator("#save-dialog").wait_for(state="hidden")
    assert "已保存到模板库" in page.locator("#save-status").inner_text()
    page.reload()
    page.wait_for_function(
        "document.querySelector('[data-name=\"0\"]')?.textContent==='浏览器实测登录'"
    )
    page.locator("#open-template").click()
    page.locator("[data-open]").first.click()
    page.locator("#library-dialog").wait_for(state="hidden")
    page.locator("#sample").click()
    data = json.loads(page.locator("#data-input").input_value())
    data[0]["expected"] = "数据值 <成功> & 中文"
    page.locator("#data-input").fill(json.dumps(data, ensure_ascii=False))
    page.locator("#apply-data").click()
    page.locator("[data-upload]").first.click()
    page.locator("#image-file").set_input_files(str(root / "evidence/desktop.png"))
    page.locator("#paper .upload img").wait_for()
    page.locator("#save-template").click()
    page.locator("#confirm-save").click()
    page.locator("#save-dialog").wait_for(state="hidden")
    with page.expect_download() as info:
        page.locator("#generate").click()
    target = root / "evidence/browser-report.docx"
    info.value.save_as(target)
    with zipfile.ZipFile(target) as z:
        xml = z.read("word/document.xml").decode()
        assert "浏览器实测登录" in xml
        assert "&lt;成功&gt;" in xml
        assert "数据值" in xml
        assert "{{p report}}" not in xml
        assert any(n.startswith("word/media/") for n in z.namelist())
    with page.expect_download() as info:
        page.locator("#export").click()
    config = root / "evidence/browser-template.json"
    info.value.save_as(config)
    page.locator("#config-file").set_input_files(str(config))
    page.wait_for_function("document.querySelector('#save-status').textContent==='有未保存的修改'")
    assert "浏览器实测登录" in page.locator("#paper").inner_text()
    page.locator("#save-template").click()
    page.locator("#template-name").fill("导入后保存")
    page.locator("#confirm-save").click()
    page.locator("#save-dialog").wait_for(state="hidden")
    page.locator("#paper .upload img").wait_for()
    page.screenshot(path=str(root / "evidence/workflow-desktop.png"))
    # New browser context proves reopening uses server persistence, not localStorage.
    second = b.new_context()
    other = second.new_page()
    other.goto("http://127.0.0.1:4175/")
    other.on("dialog", lambda d: d.accept())
    other.locator("#open-template").click()
    other.locator("[data-open]").first.click()
    other.locator("#library-dialog").wait_for(state="hidden")
    assert "浏览器实测登录" in other.locator("#paper").inner_text()
    other.locator("#paper .upload img").wait_for()
    page.set_viewport_size({"width": 390, "height": 844})
    assert page.evaluate("document.documentElement.scrollWidth<=innerWidth")
    page.screenshot(path=str(root / "evidence/workflow-mobile.png"))
    # Bad imports and cross-origin calls must not mutate stored records.
    response = context.request.post("http://127.0.0.1:4175/api/validate", data={"schema": "bad"})
    assert response.status == 400
    response = context.request.post(
        "http://127.0.0.1:4175/api/templates",
        headers={"Origin": "https://external.invalid"},
        data={},
    )
    assert response.status == 403
    assert context.request.get("http://127.0.0.1:4175/.data/studio.sqlite3").status == 404
    assert not errors, errors
    b.close()
    print(
        "PASS: edit → save → reload → open → data + image → DOCX → export/import → fresh-browser reopen; invalid input and cross-origin protection"
    )
