"""Native drag, keyboard insertion and inspector regressions for Studio V2."""

import asyncio
import os

from browser_interactions import BASE, add_set, add_template, api, editor_page
from playwright.async_api import async_playwright, expect


async def drag_to(page, anchor, relative_height, *, check_hint=None):
    source = page.get_by_role("button", name="正文 DS 内置", exact=True)
    await source.scroll_into_view_if_needed()
    await anchor.scroll_into_view_if_needed()
    src = await source.bounding_box()
    dst = await anchor.bounding_box()
    dest_x = dst["x"] + dst["width"] / 2
    dest_y = dst["y"] + dst["height"] * relative_height
    await page.mouse.move(src["x"] + src["width"] / 2, src["y"] + src["height"] / 2)
    await page.mouse.down()
    await page.mouse.move(src["x"] + src["width"] / 2, src["y"] - 5, steps=8)
    # Vary the final coordinate so Chromium delivers a dragover at the target.
    await page.mouse.move(dest_x - 2, dest_y)
    await page.mouse.move(dest_x, dest_y)
    if check_hint:
        await expect(page.locator(".component-drop-hint")).to_have_text(check_hint)
    await page.mouse.up()


async def saved_doc(page, client, tid):
    await page.get_by_role("button", name="保存", exact=True).click()
    await expect(page.locator(".save-state")).to_contain_text("已保存")
    return (await api(client, "templates/" + tid))["document"]


def outline_node(page, name):
    return page.locator(".outline").get_by_role("button", name=name, exact=True)


async def editing(browser, client):
    owner = await add_set(client, "组件交互")
    template = await add_template(
        client,
        owner,
        "目标模板",
        [
            {"id": "one", "kind": "paragraph", "text": "最先", "label": "最先"},
            {"id": "group", "kind": "group", "label": "容器"},
            {"id": "heading", "kind": "heading", "text": "初稿标题", "label": ""},
        ],
        data={"project": {"name": "项目甲"}},
    )
    async with editor_page(browser, owner, template) as page:
        # A selected row is not a fallback target for a drop over blank canvas.
        await outline_node(page, "初稿标题 H1").click()
        await page.get_by_role("button", name="组件结构", exact=True).click()
        await expect(page.locator(".component-drop-hint")).to_have_text(
            "点击组件：插入「初稿标题」之后"
        )
        await drag_to(page, page.locator(".canvas"), 0.72)
        assert len(await page.locator(".outline .tree-node").all()) == 3

        target = page.locator(".structure-view").get_by_role(
            "button", name="初稿标题 H1", exact=True
        )
        await drag_to(page, target, 0.1, check_hint="插入「初稿标题」之前")
        await expect(page.get_by_label("组件名称", exact=True)).to_have_value("正文")
        await page.get_by_label("组件名称", exact=True).fill("插在标题之前")

        await drag_to(page, outline_node(page, "容器"), 0.5, check_hint="添加到「容器」内")
        await page.get_by_label("组件名称", exact=True).fill("容器中的组件")

        await drag_to(
            page,
            page.get_by_text("拖到此处，添加到文档末尾", exact=True),
            0.5,
            check_hint="添加到文档末尾",
        )
        await page.get_by_label("组件名称", exact=True).fill("追加到末尾")

        title_row = outline_node(page, "初稿标题 H1")
        await title_row.press("Enter")
        caption = page.get_by_role("textbox", name="内容", exact=True)
        await expect(caption).to_be_focused()
        await expect(title_row).to_have_attribute("aria-pressed", "true")
        await caption.fill("前面旧字段后面")
        await caption.evaluate("(field) => field.setSelectionRange(2, 5)")
        await page.get_by_label("插入数据字段").select_option("project.name")
        await expect(caption).to_have_value("前面{{project.name}}后面")
        await expect(caption).to_be_focused()
        assert await caption.evaluate("(field) => field.selectionStart") == len(
            "前面{{project.name}}"
        )
        await expect(outline_node(page, "前面{{project.name}}后面 H1")).to_have_count(1)
        await page.get_by_label("组件名称", exact=True).fill("固定标题名")
        await caption.fill("改过内容")
        await expect(outline_node(page, "固定标题名 H1")).to_have_count(1)

        size = page.get_by_role("spinbutton", name="字号（pt）")
        await size.fill("14")
        await size.fill("99")
        await expect(size).to_have_attribute("aria-invalid", "true")
        await expect(page.get_by_text("请输入 5–72 pt 之间的数字。 此值未应用。")).to_be_visible()
        doc = await saved_doc(page, client, template["id"])
        assert [row["label"] for row in doc["nodes"]] == [
            "最先",
            "容器",
            "插在标题之前",
            "固定标题名",
            "追加到末尾",
        ]
        assert doc["nodes"][1]["children"][0]["label"] == "容器中的组件"
        assert doc["nodes"][3]["style"]["size"] == 14
        await size.fill("20")
        await expect(size).not_to_have_attribute("aria-invalid", "true")
        await page.get_by_role("button", name="完成", exact=True).press("Enter")
        await expect(outline_node(page, "固定标题名 H1")).to_be_focused()
    print("Explicit drag positions, selection, caret and local parameter validation passed")


async def pdf_drop(browser, client):
    owner = await add_set(client, "PDF 真实落点")
    template = await add_template(
        client,
        owner,
        "PDF 模板",
        [
            {"id": "first", "kind": "paragraph", "text": "First Unique Paragraph"},
            {"id": "last", "kind": "paragraph", "text": "Last Unique Paragraph"},
        ],
    )
    async with editor_page(browser, owner, template) as page:
        await page.get_by_role("button", name="更新预览", exact=True).click()
        await page.locator('.pdf-page canvas[data-ready="true"]').first.wait_for(timeout=150000)
        # The drop belongs to the visible mapped paragraph, not the selected first row.
        await outline_node(page, "First Unique Paragraph").click()
        hit = page.get_by_role("button", name="编辑 Last Unique Paragraph", exact=True)
        await drag_to(page, hit, 0.85, check_hint="插入「Last Unique Paragraph」之后")
        await page.get_by_label("组件名称", exact=True).fill("从 PDF 添加")
        doc = await saved_doc(page, client, template["id"])
        assert [row["id"] for row in doc["nodes"][:2]] == ["first", "last"]
        assert doc["nodes"][2]["label"] == "从 PDF 添加"
    print("Native drop against a real LibreOffice PDF position passed")


async def main():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            executable_path=os.environ.get("STUDIO_CHROMIUM", "/usr/bin/chromium"),
            headless=True,
        )
        try:
            client = await playwright.request.new_context(base_url=BASE)
            await editing(browser, client)
            await pdf_drop(browser, client)
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
