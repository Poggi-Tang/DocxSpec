"""Chromium exercise of first-run onboarding, dialogs, and narrow-screen editing.

Run against an isolated Studio instance with LibreOffice available.
"""

import asyncio
import os
from uuid import uuid4

from browser_interactions import BASE, add_set, add_template, api, editor_page, open_template
from playwright.async_api import async_playwright, expect


async def first_template(browser, client):
    context = await browser.new_context(base_url=BASE, viewport={"width": 1440, "height": 900})
    page = await context.new_page()
    name = "软件测试 " + uuid4().hex[:6]
    template_name = "体验测试报告"
    try:
        await page.goto("/")
        await expect(page.get_by_text("模板管理", exact=True)).to_be_visible()
        if await page.locator(".set").count():
            await page.get_by_role("button", name="添加模板集", exact=True).click()
        else:
            await expect(page.get_by_role("button", name="新建模板", exact=True)).to_have_count(0)
            await page.get_by_role("button", name="新建模板集", exact=True).click()
        modal = page.get_by_role("dialog", name="新建模板集")
        await expect(modal.get_by_label("模板集名称")).to_be_focused()
        await modal.get_by_label("模板集名称").fill(name)
        engine = modal.get_by_label("默认排版引擎")
        assert "当前环境不可用" not in await engine.locator("option:checked").inner_text()
        await engine.select_option("libreoffice")
        await modal.get_by_role("button", name="创建模板集", exact=True).click()
        await expect(modal).to_have_count(0)
        await page.get_by_role("button", name="创建报告模板", exact=True).click()
        modal = page.get_by_role("dialog", name="新建报告模板")
        await expect(modal).to_contain_text(name)
        await modal.get_by_label("新模板名称").fill(template_name)
        await modal.get_by_role("button", name="创建模板", exact=True).click()
        await expect(page.locator(".document-bar strong")).to_have_text(template_name)
        await expect(page.get_by_label("排版引擎")).to_have_value("libreoffice")
        await page.get_by_role("button", name="更新预览", exact=True).click()
        await expect(page.locator('.pdf-page canvas[data-ready="true"]').first).to_be_visible(
            timeout=30_000
        )
        await expect(page.get_by_role("button", name="DOCX", exact=True)).to_be_enabled()
    finally:
        await context.close()


async def dialog_and_sample_data(browser, client):
    owner = await add_set(client, "测试数据编辑")
    template = await add_template(
        client,
        owner,
        "键盘操作",
        [{"kind": "paragraph", "text": "项目：{{project.name}}"}],
        {"project": {"name": "旧项目"}, "testCases": [{"name": "原用例", "result": "通过"}]},
    )
    async with editor_page(browser, owner, template) as page:
        trigger = page.get_by_role("button", name="测试数据", exact=True)
        await trigger.focus()
        await page.keyboard.press("Enter")
        modal = page.get_by_role("dialog", name="测试数据")
        await expect(modal.get_by_role("button", name="数据表单")).to_be_focused()
        for key in ("Tab", "Shift+Tab"):
            for _ in range(12):
                await page.keyboard.press(key)
                assert await page.evaluate("!!document.activeElement.closest('dialog[open]')")
        await modal.get_by_role("button", name="高级 JSON", exact=True).click()
        await modal.get_by_label("测试数据 JSON").fill("{")
        await modal.get_by_role("button", name="应用数据", exact=True).click()
        await expect(modal.get_by_role("alert")).to_contain_text("JSON 格式无效")
        await expect(modal.get_by_label("测试数据 JSON")).to_have_attribute("aria-invalid", "true")
        await page.keyboard.press("Escape")
        await expect(modal).to_have_count(0)
        await expect(trigger).to_be_focused()
        await trigger.click()
        await (
            modal.get_by_role("group", name="项目", exact=True).get_by_label("名称").fill("新项目")
        )
        await modal.get_by_role("button", name="删除 测试用例第 1 条").click()
        await modal.get_by_role("button", name="添加 测试用例记录").click()
        await modal.get_by_role("group", name="第 1 条").get_by_label("名称").fill("新用例")
        await modal.get_by_role("group", name="第 1 条").get_by_label("实际结果").fill("通过")
        await modal.get_by_role("button", name="应用数据", exact=True).click()
        await expect(modal).to_have_count(0)
        await page.get_by_role("button", name="保存", exact=True).click()
        await expect(page.locator(".document-bar .badge").first).to_have_text("v2")
        saved = await api(client, "templates/" + template["id"])
        assert saved["data"] == {
            "project": {"name": "新项目"},
            "testCases": [{"name": "新用例", "result": "通过"}],
        }


async def narrow_editing(browser, client):
    owner = await add_set(client, "窄屏工作区")
    template = await add_template(
        client,
        owner,
        "移动端报告",
        [{"id": "intro", "kind": "heading", "text": "巡检结论"}],
    )
    for width in (320, 390, 768):
        page = await browser.new_page(base_url=BASE, viewport={"width": width, "height": 840})
        try:
            await page.goto("/")
            await page.get_by_role("button", name="模板与结构", exact=True).click()
            await page.get_by_role("button", name=owner["name"], exact=True).click()
            await open_template(page, template["name"])
            await page.get_by_role("button", name="模板与结构", exact=True).click()
            await page.locator(".outline .tree-node").first.click()
            properties = page.get_by_role("button", name="属性", exact=True)
            await expect(properties).to_have_attribute("aria-pressed", "true")
            content = page.get_by_role("textbox", name="内容", exact=True)
            await expect(content).to_be_visible()
            await content.fill("窄屏编辑")
            assert await page.evaluate("document.documentElement.scrollWidth") == width
            await page.get_by_role("button", name="完成", exact=True).click()
            await expect(page.get_by_role("button", name="画布与组件")).to_have_attribute(
                "aria-pressed", "true"
            )
            assert await page.evaluate("document.documentElement.scrollWidth") == width
        finally:
            await page.close()


async def main():
    async with async_playwright() as playwright:
        client = await playwright.request.new_context(base_url=BASE)
        browser = await playwright.chromium.launch(
            executable_path=os.environ.get("STUDIO_CHROMIUM", "/usr/bin/chromium"),
            headless=True,
        )
        try:
            for check in (first_template, dialog_and_sample_data, narrow_editing):
                await check(browser, client)
                print(check.__name__ + " passed", flush=True)
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
