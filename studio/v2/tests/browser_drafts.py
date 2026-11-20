"""Browser coverage for local drafts, version conflicts and interrupted saves."""

import asyncio
import json
import os

from browser_interactions import (
    BASE,
    add_set,
    add_template,
    api,
    editor_page,
    header,
    hold_response,
    open_template,
)
from playwright.async_api import async_playwright, expect


async def reopen(context, owner, template):
    page = await context.new_page()
    await page.goto("/")
    await page.get_by_role("button", name=owner["name"], exact=True).click()
    await open_template(page, template["name"])
    return page


async def recover(page, phrase):
    menu = page.locator(".draft-recovery")
    if not await menu.evaluate("(details) => details.open"):
        await menu.locator("summary").click()
    await (
        menu.locator(".draft-option")
        .filter(has_text=phrase)
        .get_by_role("button", name="恢复草稿")
        .click()
    )
    await expect(header(page)).to_have_value(phrase)


async def divergent_tabs(browser, client):
    owner = await add_set(client, "多标签页草稿")
    template = await add_template(client, owner, "分支模板")
    target = await add_template(client, owner, "尝试切换的模板")
    url = "templates/" + template["id"]
    async with editor_page(browser, owner, template) as first:
        context = first.context
        second = await reopen(context, owner, template)
        await header(first).fill("第一个标签的文本")
        await header(second).fill("第二个标签的文本")
        await second.close()
        await first.close()

        page = await reopen(context, owner, template)
        await expect(header(page)).to_have_value("")
        await expect(page.locator(".draft-recovery summary")).to_have_text("本机草稿 (2)")
        await recover(page, "第一个标签的文本")
        await recover(page, "第二个标签的文本")
        await page.get_by_role("button", name="保存", exact=True).click()
        await expect(page.locator(".document-bar .badge").first).to_have_text("v2")
        await recover(page, "第一个标签的文本")
        stale_notice = page.get_by_text("已恢复旧版本草稿，可用“复制模板”保留当前编辑。")
        await expect(stale_notice).to_be_visible()
        async with page.expect_response(
            lambda response: (
                response.request.method == "PUT" and response.url.endswith("/api/v2/" + url)
            )
        ) as rejected:
            await page.get_by_role("button", name=target["name"], exact=True).click()
        assert (await rejected.value).status == 409
        await expect(page.get_by_role("alert")).to_contain_text("模板已有更新版本")
        await expect(stale_notice).to_have_count(0)
        await expect(page.locator(".document-bar strong")).to_have_text(template["name"])
        await expect(header(page)).to_have_value("第一个标签的文本")
        assert (await api(client, url))["document"]["header"] == "第二个标签的文本"
        await page.get_by_role("button", name="复制模板", exact=True).click()
        await expect(page.locator(".document-bar strong")).to_have_text(
            template["name"] + " · 副本"
        )
        await expect(header(page)).to_have_value("第一个标签的文本")
    print("divergent drafts recovered independently; stale draft cannot overwrite newer server")


async def legacy_draft(browser, client):
    owner = await add_set(client, "旧草稿")
    template = await add_template(client, owner, "旧草稿模板")
    key = "ds-draft-" + template["id"]
    draft = {**template, "document": {**template["document"], "header": "旧版编辑"}}
    context = await browser.new_context(base_url=BASE, viewport={"width": 1440, "height": 1000})
    try:
        page = await context.new_page()
        await page.goto("/")
        await page.get_by_role("button", name=owner["name"], exact=True).click()
        await page.evaluate(
            "([key, json]) => localStorage.setItem(key, json)", [key, json.dumps(draft)]
        )
        await open_template(page, template["name"])
        await expect(header(page)).to_have_value("旧版编辑")
        await page.get_by_role("button", name="保存", exact=True).click()
        await expect(page.locator(".document-bar .badge").first).to_have_text("v2")
        assert await page.evaluate("(key) => localStorage.getItem(key)", key) is None
    finally:
        await context.close()
    print("legacy local draft recovered and retired after save")


async def recovered_source_isolated(browser, client):
    owner = await add_set(client, "草稿来源隔离")
    template = await add_template(client, owner, "来源模板")
    async with editor_page(browser, owner, template) as source:
        context = source.context
        await header(source).fill("仍然在第一个标签中的原草稿")
        second = await reopen(context, owner, template)
        await expect(header(second)).to_have_value("仍然在第一个标签中的原草稿")
        await header(second).fill("从自动恢复派生的新编辑")
        await expect(second.locator(".draft-recovery summary")).to_have_text("本机草稿 (1)")
        await second.get_by_role("button", name="保存", exact=True).click()
        await expect(second.locator(".document-bar .badge").first).to_have_text("v2")
        await source.close()
        await second.close()
        reopened = await reopen(context, owner, template)
        await expect(header(reopened)).to_have_value("从自动恢复派生的新编辑")
        await expect(reopened.locator(".document-bar .badge").first).to_have_text("v2")
        await recover(reopened, "仍然在第一个标签中的原草稿")
        await expect(reopened.locator(".document-bar .badge").first).to_have_text("v1")
        server = await api(client, "templates/" + template["id"])
        assert server["document"]["header"] == "从自动恢复派生的新编辑"
    print("saving a recovery derivative preserves its still-unsaved source branch")


async def copy_during_save(browser, client):
    owner = await add_set(client, "保存期间复制")
    template = await add_template(client, owner, "原稿")
    path = "templates/" + template["id"]
    async with editor_page(browser, owner, template) as page:
        await header(page).fill("已提交的编辑")
        async with hold_response(page, "**/api/v2/" + path, "PUT") as (started, release):
            await page.get_by_role("button", name="保存", exact=True).click()
            await asyncio.wait_for(started.wait(), 10)
            await header(page).fill("复制时的编辑")
            async with hold_response(page, "**/api/v2/templates", "POST") as (
                copy_started,
                copy_release,
            ):
                await page.get_by_role("button", name="复制模板", exact=True).click()
                await asyncio.wait_for(copy_started.wait(), 10)
                await header(page).fill("复制请求期间仍只属于原稿的编辑")
                copy_release.set()
                await expect(
                    page.get_by_role("button", name=template["name"] + " · 副本", exact=True)
                ).to_be_visible()
                await expect(page.locator(".document-bar strong")).to_have_text(template["name"])
            release.set()
            await expect(page.locator(".document-bar strong")).to_have_text(
                template["name"] + " · 副本"
            )
        await expect(header(page)).to_have_value("复制时的编辑")
        await open_template(page, template["name"])
        await expect(header(page)).to_have_value("复制请求期间仍只属于原稿的编辑")
        await expect(page.locator(".document-bar .badge").first).to_have_text("v2")
        await page.get_by_role("button", name="保存", exact=True).click()
        await expect(page.locator(".document-bar .badge").first).to_have_text("v3")
        assert (await api(client, path))["document"]["header"] == "复制请求期间仍只属于原稿的编辑"
    print("the pending original save advances the recovered draft before switching to its copy")


async def retry_own_save_after_lost_response(browser, client):
    owner = await add_set(client, "保存确认中断")
    template = await add_template(client, owner, "重试自己的保存")
    path = "templates/" + template["id"]
    request_path = "/api/v2/" + path
    async with editor_page(browser, owner, template) as page:
        await header(page).fill("确认中断时已写入服务器的内容")
        page.once("dialog", lambda dialog: dialog.accept())
        await page.reload()
        await page.get_by_role("button", name=owner["name"], exact=True).click()
        await open_template(page, template["name"])
        await expect(
            page.get_by_text("已恢复本机未保存草稿，请核对后保存", exact=True)
        ).to_be_visible()
        save = page.get_by_role("button", name="保存", exact=True)

        async def drop_ack(route):
            if route.request.method != "PUT":
                await route.continue_()
                return
            await route.fetch()
            await route.abort("failed")

        await page.route("**" + request_path, drop_ack)
        try:
            await save.click()
            await expect(page.get_by_role("alert")).to_be_visible()
            await expect(save).to_be_enabled()
            await expect(
                page.get_by_text("已恢复本机未保存草稿，请核对后保存", exact=True)
            ).to_have_count(0)
        finally:
            await page.unroute("**" + request_path, drop_ack)
        committed = await api(client, path)
        assert committed["version"] == 2
        assert committed["document"]["header"] == "确认中断时已写入服务器的内容"
        await expect(page.locator(".document-bar .badge").first).to_have_text("v1")

        async with page.expect_response(
            lambda response: (
                response.request.method == "PUT" and response.url.endswith(request_path)
            )
        ) as retry:
            await save.click()
        response = await retry.value
        assert response.status == 200, await response.text()
        await expect(page.locator(".document-bar .badge").first).to_have_text("v2")
        await expect(page.locator(".save-state")).to_contain_text("已保存")
        await expect(page.get_by_role("alert")).to_have_count(0)
        await expect(
            page.get_by_text("已恢复本机未保存草稿，请核对后保存", exact=True)
        ).to_have_count(0)
        assert [item["version"] for item in await api(client, path + "/versions")] == [2, 1]
        assert await page.evaluate(
            "id => !Object.keys(localStorage)"
            ".some(key => key.startsWith('ds-draft-v2:' + id + ':'))",
            template["id"],
        )
    print("retrying after a lost save response confirms v2 without creating v3")


async def main():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            executable_path=os.environ.get("STUDIO_CHROMIUM", "/usr/bin/chromium"),
            headless=True,
        )
        try:
            client = await playwright.request.new_context(base_url=BASE)
            await divergent_tabs(browser, client)
            await legacy_draft(browser, client)
            await recovered_source_isolated(browser, client)
            await copy_during_save(browser, client)
            await retry_own_save_after_lost_response(browser, client)
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
