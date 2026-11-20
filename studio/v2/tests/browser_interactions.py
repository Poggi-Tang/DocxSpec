"""Browser regressions against an isolated Studio instance with LibreOffice.

STUDIO_TEST_URL selects the running app. Set STUDIO_TEST_AI=1 to also verify
the conversion flow against a locally configured model fixture.
"""

import asyncio
import base64
import hashlib
import io
import os
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from docx import Document
from playwright.async_api import async_playwright, expect

BASE = os.environ.get("STUDIO_TEST_URL", "http://127.0.0.1:4177")
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aVZkAAAAASUVORK5CYII="
)


async def api(client, path, body=None):
    path = "/api/v2/" + path
    response = await (client.get(path) if body is None else client.post(path, data=body))
    assert response.ok, (path, await response.text())
    return await response.json()


async def open_template(page, name):
    await page.get_by_role("button", name=name, exact=True).click()
    await expect(page.locator(".document-bar strong")).to_have_text(name)


def header(page):
    return page.locator("label").filter(has_text="页眉").locator("textarea")


def select_node(page, name):
    return page.locator(".outline").get_by_role("button", name=name, exact=True).click()


@asynccontextmanager
async def hold_response(page, glob, method, *, ready_only=False):
    """Let the real backend act, then delay just the first matching response."""
    started, release, delivered = asyncio.Event(), asyncio.Event(), asyncio.Event()

    async def handle(route):
        if route.request.method != method or started.is_set():
            await route.continue_()
            return
        response = await route.fetch()
        if ready_only and (await response.json())["status"] != "ready":
            await route.fulfill(response=response)
            return
        started.set()
        try:
            await release.wait()
            await route.fulfill(response=response)
        finally:
            delivered.set()

    await page.route(glob, handle)
    try:
        yield started, release
    finally:
        release.set()
        if started.is_set():
            await delivered.wait()
        await page.unroute(glob, handle)


async def add_set(client, name, engine="libreoffice"):
    return await api(client, "sets", {"name": name + " " + uuid4().hex[:6], "engine": engine})


async def add_template(client, owner, name, nodes=(), data=None):
    return await api(
        client,
        "templates",
        {
            "name": name + " " + uuid4().hex[:6],
            "set_id": owner["id"],
            "document": {"nodes": nodes},
            "data": data or {},
        },
    )


@asynccontextmanager
async def editor_page(browser, owner, template):
    context = await browser.new_context(base_url=BASE, viewport={"width": 1440, "height": 1000})
    page = await context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    try:
        await page.goto("/")
        await page.get_by_role("button", name=owner["name"], exact=True).click()
        await open_template(page, template["name"])
        yield page
        assert not errors, errors
    finally:
        await context.close()


async def saves_and_undo(browser, client):
    owner = await add_set(client, "保存回归")
    first = await add_template(client, owner, "编辑模板")
    second = await add_template(client, owner, "切换目标")
    route = "**/api/v2/templates/" + first["id"]
    async with editor_page(browser, owner, first) as page:
        await header(page).fill("第一份编辑")
        async with hold_response(page, route, "PUT") as (started, release):
            await page.get_by_role("button", name="保存", exact=True).click()
            await asyncio.wait_for(started.wait(), 10)
            await header(page).fill("保存期间的新编辑")
            release.set()
            await expect(page.locator(".save-state")).to_contain_text("未保存")
            await expect(page.locator(".document-bar .badge").first).to_have_text("v2")

        restored = await page.context.new_page()
        await restored.goto("/")
        await restored.get_by_role("button", name=owner["name"], exact=True).click()
        await open_template(restored, first["name"])
        await expect(header(restored)).to_have_value("保存期间的新编辑")
        await restored.close()

        async with hold_response(page, route, "PUT") as (started, release):
            await page.get_by_role("button", name=second["name"], exact=True).click()
            await asyncio.wait_for(started.wait(), 10)
            await header(page).fill("切换期间的新编辑")
            release.set()
            await expect(page.locator(".document-bar strong")).to_have_text(second["name"])

        await open_template(page, first["name"])
        await expect(header(page)).to_have_value("切换期间的新编辑")
        await header(page).fill("保存后撤销")
        save = page.get_by_role("button", name="保存", exact=True)
        await save.click()
        await expect(page.locator(".document-bar .badge").first).to_have_text("v5")
        await page.get_by_title("撤销", exact=True).click()
        await expect(header(page)).to_have_value("切换期间的新编辑")
        await expect(page.locator(".document-bar .badge").first).to_have_text("v5")
        await save.click()
        await expect(page.locator(".document-bar .badge").first).to_have_text("v6")
        await expect(page.get_by_role("alert")).to_have_count(0)
        assert (await api(client, "templates/" + first["id"]))["document"][
            "header"
        ] == "切换期间的新编辑"

        await page.get_by_title("历史版本", exact=True).click()
        original_version = page.locator(".version").filter(has_text="v1 ·")
        async with hold_response(page, route + "/versions/1", "GET") as (started, release):
            await original_version.get_by_role("button", name="恢复到编辑区").click()
            await asyncio.wait_for(started.wait(), 10)
            await page.get_by_role("button", name="关闭", exact=True).click()
            await header(page).fill("读取历史版本期间的新编辑")
            async with page.expect_response(
                lambda response: response.url.endswith("/versions/1") and response.ok
            ) as received:
                release.set()
            await (await received.value).json()
        await expect(header(page)).to_have_value("读取历史版本期间的新编辑")


async def image_upload(browser, client):
    owner = await add_set(client, "上传回归")
    template = await add_template(
        client,
        owner,
        "含图模板",
        [
            {"id": "picture", "kind": "image", "label": "原图片"},
            {"id": "second", "kind": "paragraph", "label": "独立正文", "text": "之前的文字"},
        ],
    )
    async with editor_page(browser, owner, template) as page:
        await select_node(page, "原图片")
        async with hold_response(page, "**/api/v2/assets", "POST") as (started, release):
            await page.locator("input[type=file]").set_input_files(
                {"name": "pic.png", "mimeType": "image/png", "buffer": PNG}
            )
            await asyncio.wait_for(started.wait(), 10)
            await page.get_by_label("组件名称", exact=True).fill("新图片名称")
            await page.get_by_label("宽度（厘米）", exact=True).fill("11")
            await select_node(page, "独立正文")
            await page.get_by_label("内容", exact=True).fill("上传途中编辑的正文")
            release.set()
        await expect(page.get_by_label("内容", exact=True)).to_have_value("上传途中编辑的正文")
        await select_node(page, "新图片名称")
        await expect(page.get_by_label("宽度（厘米）", exact=True)).to_have_value("11")
        await expect(page.locator(".asset-preview")).to_be_visible()


async def preview_waits_for_pending_save(browser, client):
    owner = await add_set(client, "预览快照回归")
    template = await add_template(
        client, owner, "含页眉的模板", [{"kind": "paragraph", "text": "Preview regression"}]
    )
    template_path = "templates/" + template["id"]
    save_route = "**/api/v2/" + template_path
    async with editor_page(browser, owner, template) as page:
        save = page.get_by_role("button", name="保存", exact=True)
        preview = page.get_by_role("button", name="更新预览", exact=True)
        async with hold_response(page, save_route, "PUT") as (started, release):
            await header(page).fill("先前保存的内容")
            await save.click()
            await asyncio.wait_for(started.wait(), 10)
            await header(page).fill("点击预览前的内容")
            await preview.click()
            async with page.expect_request(
                lambda request: request.method == "POST" and request.url.endswith("/renders")
            ) as sent:
                release.set()
            assert (await sent.value).post_data_json["document"]["header"] == "点击预览前的内容"

        download = page.get_by_role("button", name="DOCX", exact=True)
        await expect(download).to_be_enabled(timeout=40_000)
        assert (await api(client, template_path))["document"]["header"] == "点击预览前的内容"

        async with hold_response(page, save_route, "PUT") as (started, release):
            await header(page).fill("正在保存的内容")
            await save.click()
            await asyncio.wait_for(started.wait(), 10)
            await header(page).fill("本次预览的内容")
            await preview.click()
            await header(page).fill("点击预览后继续编辑")
            release.set()
            await expect(page.get_by_role("status")).to_have_text(
                "模板在准备预览期间已修改，请重新更新预览"
            )
        assert (await api(client, template_path))["document"]["header"] == "正在保存的内容"
        await expect(download).to_be_disabled()
        await expect(header(page)).to_have_value("点击预览后继续编辑")


async def preview_cancels_obsolete_jobs(browser, client):
    owner = await add_set(client, "过时任务回归")
    first = await add_template(
        client, owner, "原模板", [{"kind": "paragraph", "text": "First preview"}]
    )
    second = await add_template(
        client, owner, "切换模板", [{"kind": "paragraph", "text": "Second preview"}]
    )

    def submitted(response):
        return (
            response.ok and response.request.method == "POST" and response.url.endswith("/renders")
        )

    def cancelled(request):
        return request.method == "DELETE" and "/api/v2/jobs/" in request.url

    async with editor_page(browser, owner, first) as page:
        preview = page.get_by_role("button", name="更新预览", exact=True)
        download = page.get_by_role("button", name="DOCX", exact=True)
        async with hold_response(page, "**/api/v2/jobs/*", "GET") as (started, release):
            async with page.expect_response(submitted) as queued:
                await preview.click()
            job = await (await queued.value).json()
            await asyncio.wait_for(started.wait(), 10)
            async with page.expect_request(cancelled) as cancel:
                await open_template(page, second["name"])
            assert (await cancel.value).url.endswith("/jobs/" + job["id"])
            async with page.expect_response(
                lambda response: (
                    response.request.method == "GET" and response.url.endswith("/jobs/" + job["id"])
                )
            ):
                release.set()
        await expect(download).to_be_disabled()

        async with hold_response(page, "**/api/v2/renders", "POST") as (started, release):
            await preview.click()
            await asyncio.wait_for(started.wait(), 10)
            await page.get_by_label("排版引擎").select_option("word")
            await expect(page.get_by_label("排版引擎")).to_have_value("word")
            async with (
                page.expect_response(submitted) as queued,
                page.expect_request(cancelled) as cancel,
            ):
                release.set()
            job = await (await queued.value).json()
            assert (await cancel.value).url.endswith("/jobs/" + job["id"])
        await expect(download).to_be_disabled()


async def scope_and_pdf(browser, client):
    owner = await add_set(client, "预览回归")
    other = await add_set(client, "另一个模板集", engine="wps")
    target = await add_template(client, other, "WPS 模板")
    nodes = [
        {"id": "root", "kind": "paragraph", "label": "在重复区块外", "text": "Report heading"},
        {
            "id": "insideA",
            "kind": "repeat",
            "label": "重复 A",
            "source": "cases",
            "children": [
                {"id": "inner", "kind": "paragraph", "label": "在重复区块内", "text": "CASE "},
                {"id": "tableA", "kind": "table", "label": "表 A", "rows": [["状态"], ["通过"]]},
                {
                    "id": "caption",
                    "kind": "caption",
                    "label": "表 A 的题注",
                    "text": "Case results",
                },
            ],
        },
        {
            "id": "insideB",
            "kind": "repeat",
            "label": "重复 B",
            "source": "others",
            "children": [
                {"id": "tableB", "kind": "table", "label": "表 B", "rows": [["另一张表"]]},
            ],
        },
    ]
    for index in range(1, 18):
        nodes += [
            {"kind": "pagebreak"},
            {"kind": "paragraph", "text": f"PDF location marker {index:02d}"},
        ]
    template = await add_template(
        client,
        owner,
        "多页报告",
        nodes,
        {
            "project": {"name": "Example"},
            "cases": [{"name": "Integration"}],
            "others": [{"foreign": "Other collection"}],
        },
    )
    async with editor_page(browser, owner, template) as page:
        await select_node(page, "在重复区块外")
        fields = page.get_by_label("插入数据字段").locator("option")
        await expect(fields).to_have_text(["＋ 插入数据字段", "project.name"])
        await select_node(page, "在重复区块内")
        await expect(fields).to_have_text(["＋ 插入数据字段", "project.name", "item.name"])
        await page.get_by_label("插入数据字段").select_option("item.name")
        await select_node(page, "表 A 的题注")
        targets = page.get_by_label("关联对象").locator("option")
        await expect(targets).to_have_text(
            [
                "请选择表格",
                "表 A · tabl",
            ]
        )
        await page.get_by_label("关联对象").select_option("tableA")

        engine = page.get_by_label("排版引擎")
        download = page.get_by_role("button", name="DOCX", exact=True)
        preview = page.get_by_role("button", name="更新预览", exact=True)
        async with hold_response(page, "**/api/v2/jobs/*", "GET", ready_only=True) as (
            started,
            release,
        ):
            await preview.click()
            await asyncio.wait_for(started.wait(), 40)
            await engine.select_option("word")
            await expect(engine).to_have_value("word")
            async with page.expect_response(
                lambda r: r.request.method == "GET" and "/api/v2/jobs/" in r.url and r.ok
            ) as response:
                release.set()
            assert (await (await response.value).json())["status"] == "ready"
        # Allow the completed response to be handled before checking the blocked UI.
        await page.wait_for_timeout(250)
        await expect(page.locator(".render-label")).to_have_count(0)
        await expect(download).to_be_disabled()

        await engine.select_option("libreoffice")
        await preview.click()
        await expect(page.locator('.pdf-page canvas[data-ready="true"]')).to_have_count(
            18, timeout=40_000
        )
        canvas = page.locator(".canvas")
        first_page = page.locator('[data-pdf-page="1"]')
        zoom = page.get_by_label("缩放", exact=True)
        page_input = page.get_by_role("spinbutton", name="跳转页码")
        await expect(zoom).to_have_value("page")
        fit_page = await first_page.bounding_box()
        viewport = await canvas.bounding_box()
        assert fit_page["y"] >= viewport["y"]
        assert fit_page["y"] + fit_page["height"] <= viewport["y"] + viewport["height"]

        await zoom.select_option("width")
        fit_width = await first_page.bounding_box()
        assert fit_width["width"] > fit_page["width"]
        await zoom.select_option("125")
        await page.get_by_role("button", name="放大", exact=True).click()
        await expect(zoom).to_have_value("150")
        assert (await first_page.bounding_box())["width"] > fit_width["width"]

        await zoom.select_option("page")
        await page_input.fill("16")
        await page_input.press("Enter")
        await expect(page_input).to_have_value("16")
        await page.get_by_role("button", name="下一页", exact=True).click()
        await expect(page_input).to_have_value("17")
        await page.get_by_role("button", name="上一页", exact=True).click()
        await expect(page_input).to_have_value("16")
        await page.locator('[data-pdf-page="18"]').scroll_into_view_if_needed()
        await expect(page_input).to_have_value("18")

        hit = page.get_by_title("编辑 PDF location marker 17", exact=True)
        await hit.scroll_into_view_if_needed()
        await page.evaluate("window.firstCanvas = document.querySelector('.pdf-page canvas')")
        before = await canvas.evaluate("(element) => element.scrollTop")
        assert before > 1000
        await hit.click()
        await expect(hit).to_have_attribute("aria-pressed", "true")
        assert await page.evaluate(
            "window.firstCanvas === document.querySelector('.pdf-page canvas')"
        )
        assert abs(await canvas.evaluate("(element) => element.scrollTop") - before) < 5
        await expect(download).to_be_enabled()

        manifest_path = await page.get_by_role("link", name="产物记录").get_attribute("href")
        manifest = await (await client.get(manifest_path)).json()
        version = (await api(client, "templates/" + template["id"]))["version"]
        async with page.expect_download() as received:
            await download.click()
        artifact = await received.value
        assert artifact.suggested_filename == f"{template['name']}-v{version}.docx"
        downloaded = Path(await artifact.path()).read_bytes()
        assert hashlib.sha256(downloaded).hexdigest() == manifest["hashes"]["report.docx"]
        await expect(page.locator(".document-bar strong")).to_have_text(template["name"])

        await page.get_by_role("button", name=other["name"], exact=True).click()
        await expect(page.locator(".document-bar strong")).to_have_text(template["name"])
        await expect(engine).to_have_value("libreoffice")
        await expect(download).to_be_enabled()
        await open_template(page, target["name"])
        await expect(engine).to_have_value("wps")
        await expect(download).to_be_disabled()


async def conversion_review(browser, client):
    owner = await add_set(client, "转换回归")
    original = await add_template(client, owner, "正在编辑的模板")
    report = Document()
    report.add_paragraph("审核回归测试内容")
    table = report.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "验收项目"
    table.cell(0, 1).text = "通过"
    buffer = io.BytesIO()
    report.save(buffer)
    filename = "review-fixture-" + uuid4().hex[:6]
    converted = filename + " · AI 模板"

    async with editor_page(browser, owner, original) as page:
        await page.get_by_role("button", name="AI 转化模板", exact=True).click()
        upload = page.get_by_role("dialog", name="AI 转化模板")
        await expect(upload.get_by_text(owner["name"], exact=True)).to_be_visible()
        start = upload.get_by_role("button", name="开始转换", exact=True)
        await expect(start).to_be_disabled()
        selected_file = upload.get_by_label("选择 DOCX 报告")
        await selected_file.set_input_files(
            {"name": "错误内容.docx", "mimeType": "application/octet-stream", "buffer": b"invalid"}
        )
        await start.click()
        await expect(upload.get_by_role("alert")).to_contain_text("文件不是有效的 DOCX")
        await expect(upload.get_by_role("button", name="重试转换", exact=True)).to_be_enabled()

        submitted = []
        page.on(
            "request",
            lambda request: (
                submitted.append(request.url) if "/conversions?" in request.url else None
            ),
        )
        async with hold_response(page, "**/api/v2/jobs/*", "GET", ready_only=True) as (
            started,
            release,
        ):
            await selected_file.set_input_files(
                {
                    "name": filename + ".docx",
                    "mimeType": (
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    ),
                    "buffer": buffer.getvalue(),
                }
            )
            await expect(upload.get_by_text(filename + ".docx", exact=True)).to_be_visible()
            assert not submitted, "staging a file must not submit it"
            await start.click()
            await asyncio.wait_for(started.wait(), 15)
            await expect(upload.get_by_role("status")).to_contain_text(filename + ".docx")
            await upload.get_by_role("button", name="关闭", exact=True).click()
            await header(page).fill("转换期间的草稿")

            async def temporary_read_failure(route):
                await route.fulfill(status=503, json={"detail": "审核内容暂时无法读取"})

            await page.route("**/api/v2/templates/*/review", temporary_read_failure, times=1)
            release.set()

        await page.get_by_role("button", name="查看失败详情", exact=True).click()
        await expect(upload.get_by_text("审核内容暂时无法读取", exact=True)).to_be_visible()
        await expect(upload.get_by_text(filename + ".docx", exact=True)).to_be_visible()
        await upload.get_by_role("button", name="继续查询转换结果", exact=True).click()
        await expect(upload.get_by_role("button", name="打开审核", exact=True)).to_be_visible()
        assert len(submitted) == 1, "retrying a result must reuse the original job"
        await upload.get_by_role("button", name="关闭", exact=True).click()
        show = page.get_by_role("button", name="打开审核 · " + converted, exact=True)
        await show.wait_for()

        await expect(page.locator(".document-bar strong")).to_have_text(original["name"])
        await expect(header(page)).to_have_value("转换期间的草稿")
        await expect(page.get_by_role("dialog")).to_have_count(0)
        await show.click()
        await expect(page.locator(".document-bar strong")).to_have_text(converted)
        review = page.get_by_role("dialog", name="转换审核")
        await expect(review).to_be_visible()
        source = review.get_by_role("region", name="报告原文")
        generated = review.get_by_role("region", name="模板当前内容")
        await expect(source).to_contain_text("审核回归测试内容")
        await expect(generated).to_contain_text("审核回归测试内容")
        await review.get_by_role("button", name="标为已审核", exact=True).click()
        await expect(review.get_by_role("status")).to_have_text("已审核 1 / 2 项")
        await review.get_by_role("button", name="下一项", exact=True).click()
        await expect(source.get_by_role("cell", name="验收项目")).to_be_visible()
        await expect(generated.get_by_role("cell", name="通过")).to_be_visible()
        await review.get_by_role("button", name="上一项", exact=True).click()
        await generated.get_by_role("button", name="在编辑器中定位", exact=True).click()
        await expect(page.get_by_label("内容", exact=True)).to_have_value("审核回归测试内容")
        await page.get_by_role("button", name="转换审核", exact=True).click()
        await expect(review.get_by_role("status")).to_have_text("已审核 1 / 2 项")

        await page.reload()
        await page.get_by_role("button", name=owner["name"], exact=True).click()
        await open_template(page, converted)
        await page.get_by_role("button", name="转换审核", exact=True).click()
        await expect(review.get_by_role("status")).to_have_text("已审核 1 / 2 项")
        await review.get_by_role("button", name="上一项", exact=True).click()
        await review.get_by_role("button", name="取消已审核", exact=True).click()
        await expect(review.get_by_role("status")).to_have_text("已审核 0 / 2 项")
        assert (await api(client, "templates/" + original["id"]))["document"][
            "header"
        ] == "转换期间的草稿"


async def main():
    async with async_playwright() as playwright:
        client = await playwright.request.new_context(base_url=BASE)
        browser = await playwright.chromium.launch(
            executable_path=os.environ.get("STUDIO_CHROMIUM", "/usr/bin/chromium"),
            headless=True,
        )
        try:
            cases = [
                saves_and_undo,
                image_upload,
                preview_waits_for_pending_save,
                preview_cancels_obsolete_jobs,
                scope_and_pdf,
            ]
            if os.environ.get("STUDIO_TEST_AI") == "1":
                cases.append(conversion_review)
            for case in cases:
                await case(browser, client)
                print(case.__name__ + " passed", flush=True)
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
