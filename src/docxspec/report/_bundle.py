"""Portable, versioned component templates and offline report generation."""

from __future__ import annotations

import hashlib
import io
import re
import stat
import struct
import zlib
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import TemporaryDirectory
from types import MappingProxyType
from typing import Annotated, Any, BinaryIO, Literal
from zipfile import ZIP_DEFLATED, ZIP_STORED, BadZipFile, ZipFile, ZipInfo

from PIL import Image
from pydantic import BaseModel, ConfigDict, Field

from docxspec import DEFAULT_MASTER_TEMPLATE, refresh_docx_fields
from docxspec._staged_output import staged_output

from ._compiler import compile_document
from ._models import DocumentModel, Node

BUNDLE_FORMAT = "docxspec-template-bundle-v1"
_MANIFEST = "template.json"
_MAX_MANIFEST = 24 * 1024 * 1024
# Studio normalizes up to 20 million pixels to RGB PNG. Allow one extra
# filter byte per row, even for a one-column image, plus PNG/zlib overhead.
_MAX_ASSET = 80 * 1024 * 1024
_MAX_ASSET_TOTAL = 128 * 1024 * 1024
_MAX_ASSETS = 1000
_MAX_INDEX = 512 * 1024
_MAX_ARCHIVE = _MAX_MANIFEST + _MAX_ASSET_TOTAL + 2 * _MAX_INDEX
_MAX_PIXELS = 20_000_000
_SHA_PATTERN = r"^[0-9a-f]{64}$"
_SHA = re.compile(_SHA_PATTERN)
_SHA_TEXT = Annotated[str, Field(pattern=_SHA_PATTERN)]
_IMAGE_FORMATS = ("PNG", "JPEG", "GIF", "BMP", "TIFF")
_EOCD = struct.Struct("<4s4H2LH")

_Document = DocumentModel | Mapping[str, Any]


class _Manifest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    format: Literal["docxspec-template-bundle-v1"]
    name: str = Field(min_length=1, max_length=100)
    document: DocumentModel
    master_sha256: _SHA_TEXT
    asset_ids: list[_SHA_TEXT] = Field(max_length=_MAX_ASSETS)


@dataclass(frozen=True, slots=True)
class TemplateBundle:
    """Validated template loaded from a portable ZIP, including its fixed images."""

    name: str
    document: DocumentModel
    master_sha256: str
    _assets: Mapping[str, bytes] = field(repr=False)

    @property
    def asset_ids(self) -> tuple[str, ...]:
        """Hashes of the images stored in this bundle."""
        return tuple(self._assets)


def _master_digest() -> str:
    return hashlib.sha256(Path(DEFAULT_MASTER_TEMPLATE).read_bytes()).hexdigest()


def _document(value: _Document) -> DocumentModel:
    raw = value.model_dump(mode="json") if isinstance(value, DocumentModel) else value
    return DocumentModel.model_validate(raw)


def _fixed_assets(nodes: list[Node]) -> set[str]:
    hashes: set[str] = set()
    for node in nodes:
        if node.kind == "image" and not node.source and node.asset:
            hashes.add(node.asset)
        hashes.update(_fixed_assets(node.children))
    return hashes


def _bounded_image(path: Path) -> bytes:
    with path.open("rb") as source:
        raw = source.read(_MAX_ASSET + 1)
    if len(raw) > _MAX_ASSET:
        raise ValueError("图片不能超过 80 MiB")
    return raw


def _check_image(raw: bytes) -> None:
    try:
        with Image.open(io.BytesIO(raw), formats=_IMAGE_FORMATS) as image:
            if image.width * image.height > _MAX_PIXELS:
                raise ValueError("图片不能超过 2000 万像素")
            image.verify()
    except (OSError, SyntaxError, Image.DecompressionBombError) as exc:
        raise ValueError("图片无效或格式不受支持，请使用 PNG、JPEG、GIF、BMP 或 TIFF") from exc


def _read_asset(assets: Path | None, digest: str) -> bytes:
    if _SHA.fullmatch(digest) is None:
        raise ValueError("图片资源 ID 必须是 64 位小写 SHA-256")
    if assets is None or not (assets / digest).is_file():
        raise ValueError(f"图片资源不存在：{digest}")
    raw = _bounded_image(assets / digest)
    if hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError(f"图片资源哈希不匹配：{digest}")
    _check_image(raw)
    return raw


def register_report_asset(source: str | Path, assets: str | Path) -> str:
    """Store a local image by SHA-256 without changing its bytes and return its ID."""
    raw = _bounded_image(Path(source))
    _check_image(raw)
    digest = hashlib.sha256(raw).hexdigest()
    destination = Path(assets) / digest
    with staged_output(destination) as staged:
        staged.write_bytes(raw)
    return digest


def export_template_bundle(
    document: _Document,
    output: str | Path,
    *,
    name: str,
    assets: str | Path | None = None,
) -> Path:
    """Write a ZIP containing the component template and its referenced fixed images.

    Business data and images bound to business data are supplied separately at render time.
    """
    model = _document(document)
    if not isinstance(name, str) or not name.strip():
        raise ValueError("模板名称不能为空")
    manifest = _Manifest(
        format=BUNDLE_FORMAT,
        name=name,
        document=model,
        master_sha256=_master_digest(),
        asset_ids=sorted(_fixed_assets(model.nodes)),
    )
    manifest_bytes = manifest.model_dump_json().encode("utf-8")
    if len(manifest_bytes) > _MAX_MANIFEST:
        raise ValueError("模板内容不能超过 24 MiB")
    directory = Path(assets) if assets is not None else None
    destination = Path(output)
    total = 0
    with staged_output(destination) as staged:
        with ZipFile(staged, "w", compression=ZIP_DEFLATED, allowZip64=False) as archive:
            archive.writestr(_MANIFEST, manifest_bytes)
            for digest in manifest.asset_ids:
                raw = _read_asset(directory, digest)
                total += len(raw)
                if total > _MAX_ASSET_TOTAL:
                    raise ValueError("模板包图片总量不能超过 128 MiB")
                archive.writestr("assets/" + digest, raw, compress_type=ZIP_STORED)
    return destination


def _check_archive_index(source: BinaryIO) -> None:
    # Inspect the directory size before ZipFile reads/indexes the whole directory.
    size = source.seek(0, io.SEEK_END)
    if not _EOCD.size <= size <= _MAX_ARCHIVE:
        raise ValueError("模板包大小无效或超过限制")
    source.seek(-_EOCD.size, io.SEEK_END)
    signature, disk, start_disk, disk_count, count, length, offset, comment = _EOCD.unpack(
        source.read(_EOCD.size)
    )
    if (
        signature != b"PK\x05\x06"
        or disk
        or start_disk
        or disk_count != count
        or not 1 <= count <= _MAX_ASSETS + 1
        or length > _MAX_INDEX
        or offset + length != size - _EOCD.size
        or comment
    ):
        raise ValueError("模板包的 ZIP 目录不受支持")


def _members(archive: ZipFile) -> dict[str, ZipInfo]:
    members: dict[str, ZipInfo] = {}
    total = 0
    for item in archive.infolist():
        name = item.filename
        limit = _MAX_MANIFEST
        if name != _MANIFEST:
            if not name.startswith("assets/") or _SHA.fullmatch(name[7:]) is None:
                raise ValueError(f"模板包含无效文件名：{name!r}")
            limit = _MAX_ASSET
            total += item.file_size
        if (
            name in members
            or item.orig_filename != name
            or stat.S_ISLNK(item.external_attr >> 16)
            or item.flag_bits & 1
            or item.compress_type not in (ZIP_DEFLATED, ZIP_STORED)
        ):
            raise ValueError("模板包含重复或不受支持的 ZIP 条目")
        if item.file_size > limit or total > _MAX_ASSET_TOTAL:
            raise ValueError("模板包内容超过大小限制")
        members[name] = item
    if len(members) > _MAX_ASSETS + 1 or _MANIFEST not in members:
        raise ValueError("模板包文件数无效或缺少模板清单")
    return members


def _read_member(archive: ZipFile, item: ZipInfo) -> bytes:
    with archive.open(item) as source:
        raw = source.read(item.file_size + 1)
    if len(raw) != item.file_size:
        raise ValueError("模板包文件大小与 ZIP 清单不一致")
    return raw


def load_template_bundle(source: str | Path) -> TemplateBundle:
    """Read and verify a template bundle without extracting its ZIP paths."""
    try:
        with Path(source).open("rb") as file:
            _check_archive_index(file)
            with ZipFile(file) as archive:
                members = _members(archive)
                manifest = _Manifest.model_validate_json(_read_member(archive, members[_MANIFEST]))
                if not manifest.name.strip():
                    raise ValueError("模板名称不能为空")
                declared = set(manifest.asset_ids)
                if (
                    len(declared) != len(manifest.asset_ids)
                    or declared != _fixed_assets(manifest.document.nodes)
                    or set(members) != {_MANIFEST, *("assets/" + digest for digest in declared)}
                ):
                    raise ValueError("模板包图片清单与模板或文件不一致")
                assets: dict[str, bytes] = {}
                for digest in sorted(declared):
                    raw = _read_member(archive, members["assets/" + digest])
                    if hashlib.sha256(raw).hexdigest() != digest:
                        raise ValueError(f"图片资源哈希不匹配：{digest}")
                    _check_image(raw)
                    assets[digest] = raw
    except (
        BadZipFile,
        EOFError,
        RuntimeError,
        NotImplementedError,
        struct.error,
        zlib.error,
    ) as exc:
        raise ValueError("模板包 ZIP 文件无效或已损坏") from exc
    return TemplateBundle(
        manifest.name, manifest.document, manifest.master_sha256, MappingProxyType(assets)
    )


def render_report(
    template: TemplateBundle | _Document | str | Path,
    data: Mapping[str, Any],
    output: str | Path,
    *,
    assets: str | Path | None = None,
    field_engine: str = "mark",
) -> Path:
    """Generate a DOCX using the same compiler and DS master as Studio.

    A ZIP path or loaded bundle provides fixed images. For data-bound images,
    register them in the supplied assets directory and provide their IDs in data.
    A plain component model loads all images from that directory.
    """
    bundle = load_template_bundle(template) if isinstance(template, (str, Path)) else template
    embedded: Mapping[str, bytes] = {}
    if isinstance(bundle, TemplateBundle):
        if bundle.master_sha256 != _master_digest():
            raise ValueError("模板包的 DS 母版与当前 docxspec 版本不同，请使用匹配的版本")
        embedded = bundle._assets
        model = _document(bundle.document)
    else:
        model = _document(bundle)
    if not isinstance(data, Mapping):
        raise ValueError("报告数据应为字段名到值的映射")

    directory = Path(assets) if assets is not None else None
    destination = Path(output)
    with (
        TemporaryDirectory(prefix="docxspec-assets-") as folder,
        staged_output(destination) as staged,
    ):
        local_assets = Path(folder)
        total = 0

        def resolve(digest: str) -> Path:
            nonlocal total
            target = local_assets / digest
            if not target.is_file():
                raw = embedded.get(digest)
                if raw is None:
                    raw = _read_asset(directory, digest)
                total += len(raw)
                if total > _MAX_ASSET_TOTAL:
                    raise ValueError("报告图片总量不能超过 128 MiB")
                target.write_bytes(raw)
            return target

        compile_document(model, dict(data), local_assets, staged, asset_resolver=resolve)
        refresh_docx_fields(staged, engine=field_engine, strict=True)
    return destination
