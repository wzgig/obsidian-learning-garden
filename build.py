from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import stat
import tempfile
from pathlib import Path, PureWindowsPath

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markdown_it import MarkdownIt


SLUG_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
BUILD_MARKER_NAME = ".public-site-build-marker"
BUILD_MARKER_CONTENT = "lexicon-garden-static-build-v1\n"
PRIVATE_CONTEXT_START = "<!-- PRIVATE-SOURCE-CONTEXT:START -->"
PRIVATE_CONTEXT_END = "<!-- PRIVATE-SOURCE-CONTEXT:END -->"
PRIORITY_RANKS = {
    "low": 0,
    "later": 0,
    "normal": 1,
    "routine": 1,
    "medium": 2,
    "watch": 2,
    "high": 3,
    "focus": 3,
    "urgent": 4,
    "critical": 4,
}
PRIORITY_PRESENTATION = {
    0: ("later", "稍后"),
    1: ("normal", "常规"),
    2: ("watch", "关注"),
    3: ("high", "优先"),
    4: ("urgent", "立即复习"),
}
CONTEXT_STATUS_PRESENTATION = {
    "needs_context": "语境待确认",
    "complete": "语境完整",
    "ready": "语境就绪",
    "verified": "已核验",
    "source_mismatch": "来源待核",
}
CALLOUT_LABELS = {
    "summary": "一眼记住",
    "abstract": "摘要",
    "note": "提示",
    "info": "说明",
    "tip": "提示",
    "example": "示例",
    "warning": "注意",
    "caution": "注意",
    "danger": "重要提醒",
}


def normalize_base_url(value: str) -> str:
    value = "/" + value.strip("/") if value.strip("/") else ""
    return value + "/"


def plain_text(markdown: str) -> str:
    value = re.sub(r"```.*?```", " ", markdown, flags=re.S)
    value = re.sub(r"!?(?:\[([^\]]+)\]\([^\)]+\))", r"\1", value)
    value = re.sub(r"[#>*_`|~-]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def strip_private_source_context(markdown: str) -> str:
    """Remove private source excerpts before rendering or indexing.

    The exporter is expected to remove these blocks first. The builder repeats the
    check as a fail-closed boundary so a malformed marker cannot silently publish
    an exam excerpt or any other private source context.
    """

    chunks: list[str] = []
    cursor = 0
    while True:
        start = markdown.find(PRIVATE_CONTEXT_START, cursor)
        stray_end = markdown.find(PRIVATE_CONTEXT_END, cursor)
        if stray_end >= 0 and (start < 0 or stray_end < start):
            raise ValueError("private source context has an unmatched end marker")
        if start < 0:
            chunks.append(markdown[cursor:])
            break
        chunks.append(markdown[cursor:start])
        end = markdown.find(PRIVATE_CONTEXT_END, start + len(PRIVATE_CONTEXT_START))
        if end < 0:
            raise ValueError("private source context has an unmatched start marker")
        cursor = end + len(PRIVATE_CONTEXT_END)

    sanitized = "".join(chunks)
    if PRIVATE_CONTEXT_START in sanitized or PRIVATE_CONTEXT_END in sanitized:
        raise ValueError("private source context marker survived sanitization")
    return re.sub(r"\n{3,}", "\n\n", sanitized).strip() + "\n"


def normalize_obsidian_callouts(markdown: str) -> str:
    """Render Obsidian callout headers as readable CommonMark blockquotes."""

    pattern = re.compile(r"(?m)^>\s*\[!([A-Za-z0-9_-]+)\][+-]?\s*(.*?)\s*$")

    def replace(match: re.Match) -> str:
        callout_type = match.group(1).lower()
        explicit_title = match.group(2).strip()
        title = explicit_title or CALLOUT_LABELS.get(callout_type, "提示")
        return f"> **{title}**"

    return pattern.sub(replace, markdown)


def strip_matching_leading_heading(markdown: str, title: str) -> str:
    """Avoid rendering the note title twice when Markdown starts with the same H1."""

    match = re.match(r"\A\ufeff?[ \t]*#\s+(.+?)[ \t]*(?:\r?\n+|\Z)", markdown)
    if match is None:
        return markdown
    heading = re.sub(r"[`*_]", "", match.group(1)).strip()
    if heading.casefold() != str(title or "").strip().casefold():
        return markdown
    return markdown[match.end() :].lstrip("\r\n")


def _nonnegative_int(value, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(0, number)


def _study_metrics(metadata: dict) -> dict:
    encounter_count = max(1, _nonnegative_int(metadata.get("encounter_count"), 1))
    lapse_count = _nonnegative_int(metadata.get("lapse_count"))
    review_count = _nonnegative_int(metadata.get("review_count"))
    priority_score = _nonnegative_int(metadata.get("priority_score"))
    priority_value = metadata.get("review_priority", "")
    raw_priority = str(priority_value).strip().lower()
    priority_rank = PRIORITY_RANKS.get(raw_priority)
    if isinstance(priority_value, int) and not isinstance(priority_value, bool):
        priority_rank = min(4, max(0, priority_value))
    if priority_rank is None:
        if priority_score >= 80:
            priority_rank = 4
        elif priority_score >= 60:
            priority_rank = 3
        elif priority_score >= 30:
            priority_rank = 2
        else:
            priority_rank = 1
    priority_key, priority_label = PRIORITY_PRESENTATION[priority_rank]
    return {
        "encounter_count": encounter_count,
        "lapse_count": lapse_count,
        "review_count": review_count,
        "priority_score": priority_score,
        "priority_rank": priority_rank,
        "priority_key": priority_key,
        "priority_label": priority_label,
        "is_repeat": encounter_count > 1,
        "has_lapse": lapse_count > 0,
        "is_focus": priority_rank >= 3 or lapse_count > 0,
        "first_seen": str(metadata.get("first_seen", "") or ""),
        "last_seen": str(metadata.get("last_seen", "") or ""),
        "next_review": str(metadata.get("next_review", "") or ""),
    }


def _context_status_label(metadata: dict) -> str:
    status = str(metadata.get("context_status", "") or "").strip()
    return CONTEXT_STATUS_PRESENTATION.get(status, status)


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _absolute_lexical(path: Path) -> Path:
    """Return an absolute normalized path without resolving links or junctions."""

    return Path(os.path.abspath(os.fspath(path)))


def _is_link_or_junction(path: Path) -> bool:
    if path.is_symlink():
        return True

    is_junction = getattr(path, "is_junction", None)
    if is_junction is not None and is_junction():
        return True

    try:
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
    except OSError:
        return False
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return bool(reparse_flag and attributes & reparse_flag)


def _path_components(path: Path, start: Path | None = None):
    if start is None:
        current = Path(path.anchor)
        remaining = path.parts[1:]
    else:
        current = start
        remaining = path.relative_to(start).parts

    for part in remaining:
        current = current / part
        yield current


def _validate_output_path(project_root: Path, requested_output: Path) -> Path:
    raw_project_root = _absolute_lexical(project_root)
    project_root = raw_project_root.resolve(strict=True)
    raw_output = _absolute_lexical(requested_output)

    try:
        internal_relative = raw_output.relative_to(raw_project_root)
    except ValueError:
        internal_relative = None

    component_start = raw_project_root if internal_relative is not None else None
    for component in _path_components(raw_output, component_start):
        if _is_link_or_junction(component):
            raise ValueError(
                f"output path must not traverse a symlink or junction: {component}"
            )

    output = raw_output.resolve(strict=False)
    filesystem_root = Path(output.anchor)
    if output == filesystem_root:
        raise ValueError(f"refusing to use a filesystem root as output: {output}")
    if output == project_root or _is_relative_to(project_root, output):
        raise ValueError(
            "output must not be the project root or one of its ancestors: "
            f"{output}"
        )

    if internal_relative is not None and not _is_relative_to(output, project_root):
        raise ValueError(f"output path escapes the project through a link: {raw_output}")

    if _is_relative_to(output, project_root):
        expected_internal_output = (project_root / "dist").resolve(strict=False)
        if output != expected_internal_output:
            raise ValueError(
                "output inside the project must use the dedicated build directory "
                f"project_root/dist: {output}"
            )

    if output.exists() and not output.is_dir():
        raise ValueError(f"output exists and is not a directory: {output}")
    if output.exists() and any(output.iterdir()):
        marker = output / BUILD_MARKER_NAME
        if _is_link_or_junction(marker) or not marker.is_file():
            raise ValueError(
                "refusing to replace a non-empty output directory without a valid "
                f"build marker: {output}"
            )
        try:
            marker_content = marker.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            raise ValueError(f"unable to verify output build marker: {marker}") from error
        if marker_content != BUILD_MARKER_CONTENT:
            raise ValueError(f"output build marker is invalid: {marker}")
    return output


def _replace_output_directory(staging: Path, output: Path) -> None:
    backup = None
    if output.exists():
        backup = Path(
            tempfile.mkdtemp(prefix=f".{output.name}.backup-", dir=output.parent)
        )
        backup.rmdir()
        output.replace(backup)

    try:
        staging.replace(output)
    except BaseException:
        if backup is not None and backup.exists() and not output.exists():
            backup.replace(output)
        raise
    else:
        if backup is not None:
            shutil.rmtree(backup)


def _safe_output_path(output: Path, relative: str) -> Path:
    relative_path = Path(relative)
    windows_path = PureWindowsPath(relative)
    if (
        relative_path.is_absolute()
        or windows_path.is_absolute()
        or bool(windows_path.drive)
        or bool(windows_path.root)
    ):
        raise ValueError(f"output file must be relative: {relative!r}")
    destination = (output / relative_path).resolve(strict=False)
    if not _is_relative_to(destination, output):
        raise ValueError(f"output file escapes the build directory: {relative!r}")
    return destination


def _load_notes(project_root: Path, content_root: Path, manifest: dict) -> list[dict]:
    if not isinstance(manifest, dict):
        raise ValueError("manifest must be an object")
    entries = manifest.get("notes")
    if not isinstance(entries, list):
        raise ValueError("manifest notes must be a list")

    renderer = MarkdownIt("commonmark", {"html": False, "typographer": True})
    notes = []
    seen_slugs: set[str] = set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ValueError(f"manifest note {index} must be an object")

        slug = entry.get("slug")
        if not isinstance(slug, str) or SLUG_PATTERN.fullmatch(slug) is None:
            raise ValueError(f"invalid public slug in manifest note {index}: {slug!r}")
        if slug in seen_slugs:
            raise ValueError(f"duplicate public slug in manifest: {slug}")
        seen_slugs.add(slug)

        kind = entry.get("kind")
        if not isinstance(kind, str) or not kind.strip():
            raise ValueError(f"invalid kind for slug {slug!r}")
        metadata = entry.get("metadata")
        if not isinstance(metadata, dict):
            raise ValueError(f"invalid metadata for slug {slug!r}")

        content_file = entry.get("content_file")
        if not isinstance(content_file, str) or not content_file.strip():
            raise ValueError(f"invalid content_file for slug {slug!r}")
        relative_source = Path(content_file)
        windows_source = PureWindowsPath(content_file)
        if (
            relative_source.is_absolute()
            or windows_source.is_absolute()
            or bool(windows_source.drive)
            or bool(windows_source.root)
        ):
            raise ValueError(f"content_file must be relative for slug {slug!r}")

        source = (project_root / relative_source).resolve(strict=False)
        if not _is_relative_to(source, content_root):
            raise ValueError(f"content_file escapes content/ for slug {slug!r}")
        if not source.is_file():
            raise ValueError(f"content_file is missing or not a file for slug {slug!r}")

        markdown = strip_private_source_context(source.read_text(encoding="utf-8"))
        markdown = strip_matching_leading_heading(markdown, entry.get("title", ""))
        markdown = normalize_obsidian_callouts(markdown)
        notes.append(
            {
                **entry,
                "kind": kind,
                "metadata": metadata,
                "study": _study_metrics(metadata),
                "context_status_label": _context_status_label(metadata),
                "display_cn": str(
                    metadata.get("zh_gloss") or entry.get("summary_cn", "") or ""
                ),
                "html": renderer.render(markdown),
                "plain": plain_text(markdown),
            }
        )
    return notes


def build_site(project_root: Path, output: Path, base_url: str) -> dict:
    project_root = Path(project_root).resolve(strict=True)
    output = _validate_output_path(project_root, Path(output))
    content_root = (project_root / "content").resolve(strict=True)
    if not _is_relative_to(content_root, project_root):
        raise ValueError("content directory escapes the project root")
    manifest = json.loads((content_root / "manifest.json").read_text(encoding="utf-8"))
    config = json.loads((project_root / "site-config.json").read_text(encoding="utf-8"))
    base_url = normalize_base_url(base_url)
    notes = _load_notes(project_root, content_root, manifest)

    for note in notes:
        note["url"] = f"{base_url}{note['slug']}.html"
        _safe_output_path(output, f"{note['slug']}.html")

    env = Environment(
        loader=FileSystemLoader(project_root / "templates"),
        autoescape=select_autoescape(["html", "xml"]),
    )
    cards = [note for note in notes if note["kind"] == "vocabulary"]
    cards.sort(
        key=lambda item: (
            -item["study"]["priority_rank"],
            -item["study"]["priority_score"],
            -item["study"]["lapse_count"],
            -item["study"]["encounter_count"],
            str(item["metadata"].get("lemma", item["title"])).lower(),
        )
    )
    pages = {note["slug"]: note for note in notes}
    if "vocabulary" not in pages:
        raise ValueError("vocabulary homepage is missing")

    shared = {
        "site": config,
        "base_url": base_url,
        "card_count": len(cards),
        "production_count": sum(
            card["metadata"].get("study_mode") == "production" for card in cards
        ),
        "phrase_count": sum(card["metadata"].get("study_mode") == "phrase" for card in cards),
        "needs_context_count": sum(
            card["metadata"].get("context_status") == "needs_context" for card in cards
        ),
        "repeat_card_count": sum(card["study"]["is_repeat"] for card in cards),
        "lapse_card_count": sum(card["study"]["has_lapse"] for card in cards),
        "focus_card_count": sum(card["study"]["is_focus"] for card in cards),
    }

    index_template = env.get_template("index.html")
    note_template = env.get_template("note.html")
    not_found_template = env.get_template("404.html")
    rendered_index = index_template.render(**shared, cards=cards)
    rendered_notes = {
        note["slug"]: note_template.render(**shared, note=note, cards=cards)
        for note in notes
    }
    rendered_not_found = not_found_template.render(**shared)

    search_data = [
        {
            "title": card["title"],
            "slug": card["slug"],
            "url": card["url"],
            "lemma": card["metadata"].get("lemma", ""),
            "forms": card["metadata"].get("forms", []),
            "pos": card["metadata"].get("pos", []),
            "study_mode": card["metadata"].get("study_mode", ""),
            "mastery": card["metadata"].get("mastery", ""),
            "summary_cn": card.get("summary_cn", ""),
            "zh_gloss": card["display_cn"],
            "summary_en": card.get("summary_en", ""),
            "encounter_count": card["study"]["encounter_count"],
            "lapse_count": card["study"]["lapse_count"],
            "review_count": card["study"]["review_count"],
            "priority_score": card["study"]["priority_score"],
            "review_priority": card["study"]["priority_key"],
            "first_seen": card["study"]["first_seen"],
            "last_seen": card["study"]["last_seen"],
            "next_review": card["study"]["next_review"],
            "plain": card["plain"][:1600],
        }
        for card in cards
    ]
    rendered_search_index = json.dumps(
        search_data, ensure_ascii=False, separators=(",", ":")
    )
    rendered_webmanifest = json.dumps(
        {
            "name": config["name"],
            "short_name": config["short_name"],
            "start_url": base_url,
            "display": "standalone",
            "background_color": "#f5f5f7",
            "theme_color": "#f5f5f7",
            "categories": ["education", "reference"],
        },
        ensure_ascii=False,
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    output = _validate_output_path(project_root, output)
    staging = Path(
        tempfile.mkdtemp(prefix=f".{output.name}.staging-", dir=output.parent)
    ).resolve(strict=True)
    try:
        shutil.copytree(project_root / "assets", _safe_output_path(staging, "assets"))
        _safe_output_path(staging, "index.html").write_text(
            rendered_index, encoding="utf-8"
        )
        for slug, rendered_note in rendered_notes.items():
            _safe_output_path(staging, f"{slug}.html").write_text(
                rendered_note, encoding="utf-8"
            )
        _safe_output_path(staging, "search-index.json").write_text(
            rendered_search_index, encoding="utf-8"
        )
        _safe_output_path(staging, "robots.txt").write_text(
            "User-agent: *\nAllow: /\n", encoding="utf-8"
        )
        _safe_output_path(staging, "404.html").write_text(
            rendered_not_found, encoding="utf-8"
        )
        _safe_output_path(staging, "site.webmanifest").write_text(
            rendered_webmanifest, encoding="utf-8"
        )
        _safe_output_path(staging, BUILD_MARKER_NAME).write_text(
            BUILD_MARKER_CONTENT, encoding="utf-8"
        )

        _validate_output_path(project_root, output)
        _replace_output_directory(staging, output)
    finally:
        if staging.exists():
            shutil.rmtree(staging)

    return {"notes": len(notes), "cards": len(cards), "output": str(output)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the public vocabulary garden.")
    parser.add_argument("--output", default="dist")
    parser.add_argument("--base-url", default="/")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    result = build_site(root, root / args.output, args.base_url)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
