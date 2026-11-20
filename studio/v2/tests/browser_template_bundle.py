"""Export an unsaved template snapshot from the actual Studio browser interface."""

import asyncio
import hashlib
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

from browser_interactions import BASE, PNG, add_set, add_template, api, editor_page, header
from playwright.async_api import async_playwright, expect

from docxspec.report import render_report


async def main():
    async with async_playwright() as playwright:
        client = await playwright.request.new_context(base_url=BASE)
        response = await client.post(
            "/api/v2/assets",
            multipart={
                "file": {"name": "sample.png", "mimeType": "image/png", "buffer": PNG},
            },
        )
        assert response.ok
        image_id = (await response.json())["id"]
        owner = await add_set(client, "模板包验收", engine="word")
        template = await add_template(
            client,
            owner,
            "导出用验收模板",
            [
                {"id": "heading", "kind": "heading", "text": "{{project.name}}"},
                {"id": "picture", "kind": "image", "asset": image_id},
            ],
            {"project": {"name": "不应随模板导出的示例数据"}},
        )
        browser = await playwright.chromium.launch(
            executable_path=os.environ.get("STUDIO_CHROMIUM", "/usr/bin/chromium"),
            headless=True,
        )
        try:
            async with editor_page(browser, owner, template) as page:
                await header(page).fill("未保存的标题 · {{project.name}}")
                await expect(page.get_by_role("button", name="DOCX", exact=True)).to_be_disabled()
                await expect(page.locator(".save-state")).to_contain_text("未保存")
                await page.set_viewport_size({"width": 850, "height": 900})
                export = page.get_by_role("button", name="导出模板包", exact=True)
                assert await export.evaluate(
                    "button => button.getBoundingClientRect().right <= "
                    "button.parentElement.getBoundingClientRect().right"
                )
                async with page.expect_download() as received:
                    await export.click()
                download = await received.value
                assert download.suggested_filename == f"{template['name']}-模板包.zip"
                bundle = Path(await download.path())
                with ZipFile(bundle) as package:
                    assert set(package.namelist()) == {"template.json", f"assets/{image_id}"}
                    manifest = json.loads(package.read("template.json"))
                    assert manifest["document"]["header"] == "未保存的标题 · {{project.name}}"
                    assert "不应随模板导出的示例数据" not in package.read("template.json").decode()
                with TemporaryDirectory(prefix="docxspec-browser-bundle-") as directory:
                    report = render_report(
                        bundle,
                        {"project": {"name": "独立业务数据"}},
                        Path(directory) / "report.docx",
                    )
                    with ZipFile(report) as docx:
                        assert "独立业务数据" in docx.read("word/document.xml").decode()
                        assert any(
                            "未保存的标题 · 独立业务数据" in docx.read(name).decode()
                            for name in docx.namelist()
                            if name.startswith("word/header")
                        )
                        assert any(
                            hashlib.sha256(docx.read(name)).hexdigest() == image_id
                            for name in docx.namelist()
                            if name.startswith("word/media/")
                        )
                saved = await api(client, "templates/" + template["id"])
                assert saved["document"]["header"] == ""
                assert saved["version"] == 1

            broken = await add_template(
                client,
                owner,
                "图片资源缺失",
                [{"id": "picture", "kind": "image", "asset": "0" * 64}],
            )
            async with editor_page(browser, owner, broken) as page:
                export = page.get_by_role("button", name="导出模板包", exact=True)
                await export.click()
                await expect(page.get_by_role("alert")).to_contain_text("图片资源不存在")
                await expect(export).to_be_enabled()
        finally:
            await browser.close()
    print("Studio ZIP download and Python rendering with separate business data passed")


if __name__ == "__main__":
    asyncio.run(main())
