"""Browser regressions for delayed navigation and data within the editor."""

import asyncio
import os

from browser_interactions import (
    BASE,
    PNG,
    add_set,
    add_template,
    api,
    editor_page,
    hold_response,
    open_template,
    select_node,
)
from playwright.async_api import async_playwright, expect


async def image_follows_navigation(browser, client):
    owner = await add_set(client, "上传切换")
    original = await add_template(
        client, owner, "图片原稿", [{"kind": "image", "id": "img", "label": "待上传图片"}]
    )
    other = await add_template(client, owner, "切换目标")
    async with editor_page(browser, owner, original) as page:
        await select_node(page, "待上传图片")
        async with hold_response(page, "**/api/v2/assets", "POST") as (started, release):
            await page.locator("input[type=file]").set_input_files(
                {"name": "pic.png", "mimeType": "image/png", "buffer": PNG}
            )
            await asyncio.wait_for(started.wait(), 10)
            await page.get_by_role("button", name=other["name"], exact=True).click()
            await expect(page.get_by_role("status")).to_have_text("正在等待图片上传完成")
            await expect(page.locator(".document-bar strong")).to_have_text(original["name"])
            release.set()
            await expect(page.locator(".document-bar strong")).to_have_text(other["name"])
        await open_template(page, original["name"])
        await select_node(page, "待上传图片")
        await expect(page.locator(".asset-preview")).to_be_visible()
        saved = await api(client, "templates/" + original["id"])
        assert len(saved["document"]["nodes"][0]["asset"]) == 64


async def delayed_history_keeps_data_editor(browser, client):
    owner = await add_set(client, "历史窗口切换")
    template = await add_template(client, owner, "测试数据")
    route = "**/api/v2/templates/" + template["id"] + "/versions"
    async with editor_page(browser, owner, template) as page:
        data = '{"project":{"name":"新项目"}}'
        async with hold_response(page, route, "GET") as (started, release):
            await page.get_by_title("历史版本", exact=True).click()
            await asyncio.wait_for(started.wait(), 10)
            await page.get_by_role("button", name="测试数据", exact=True).click()
            modal = page.get_by_role("dialog", name="测试数据")
            await modal.get_by_role("button", name="高级 JSON", exact=True).click()
            await modal.get_by_label("测试数据 JSON").fill(data)
            async with page.expect_response(
                lambda response: response.url.endswith("/versions") and response.ok
            ) as received:
                release.set()
            await (await received.value).json()
            await page.evaluate(
                "() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))"
            )
            await expect(modal.get_by_label("测试数据 JSON")).to_have_value(data)
        await modal.get_by_role("button", name="应用数据").click()
        await page.get_by_role("button", name="保存", exact=True).click()
        await expect(page.locator(".document-bar .badge").first).to_have_text("v2")
        saved = await api(client, "templates/" + template["id"])
        assert saved["data"]["project"]["name"] == "新项目"


async def archive_finishes_when_browsing(browser, client):
    owner = await add_set(client, "归档原模板集")
    other = await add_set(client, "归档期间浏览")
    template = await add_template(client, owner, "要归档的模板")
    destination = await add_template(client, other, "浏览目标")
    route = "**/api/v2/templates/" + template["id"]
    async with editor_page(browser, owner, template) as page:
        async with hold_response(page, route, "DELETE") as (started, release):
            page.once("dialog", lambda dialog: dialog.accept())
            await page.get_by_role("button", name="归档模板", exact=True).click()
            await asyncio.wait_for(started.wait(), 10)
            await page.get_by_role("button", name=other["name"], exact=True).click()
            await expect(page.locator(".set.selected")).to_have_text(other["name"])
            release.set()
            await expect(page.locator(".document-bar strong")).to_have_text("创建你的报告模板")
        await expect(page.locator(".set.selected")).to_have_text(other["name"])
        await open_template(page, destination["name"])
        saved = await api(client, "templates/" + template["id"])
        assert saved["archived"] == 1


async def scientific_number_condition(browser, client):
    owner = await add_set(client, "数字条件")
    template = await add_template(
        client,
        owner,
        "条件字段",
        [
            {
                "kind": "repeat",
                "source": "cases",
                "children": [
                    {
                        "kind": "condition",
                        "source": "item.amount",
                        "equals": "1e-06",
                        "children": [
                            {"kind": "paragraph", "label": "符合条件的正文", "text": "Case "},
                        ],
                    },
                ],
            },
        ],
        {"cases": [{"amount": 1e-6, "name": "visible"}, {"amount": 2e-6}]},
    )
    async with editor_page(browser, owner, template) as page:
        await select_node(page, "符合条件的正文")
        await page.get_by_label("插入数据字段").select_option("item.name")
        await page.get_by_role("button", name="更新预览", exact=True).click()
        await expect(page.get_by_title("编辑 Case visible", exact=True)).to_be_visible(
            timeout=30_000
        )
        await expect(page.get_by_role("button", name="DOCX", exact=True)).to_be_enabled()


async def main():
    async with async_playwright() as playwright:
        client = await playwright.request.new_context(base_url=BASE)
        browser = await playwright.chromium.launch(
            executable_path=os.environ.get("STUDIO_CHROMIUM", "/usr/bin/chromium"),
            headless=True,
        )
        try:
            for test in (
                image_follows_navigation,
                delayed_history_keeps_data_editor,
                archive_finishes_when_browsing,
                scientific_number_condition,
            ):
                await test(browser, client)
                print(test.__name__ + " passed", flush=True)
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
