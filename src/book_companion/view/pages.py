"""The content of each book-view page, as a `Page` for layout.py to frame.

Every value from the library is HTML-escaped here, and Markdown is rendered with
raw HTML disabled, so a note can never inject markup or scripts.
"""

from __future__ import annotations

from html import escape
from pathlib import Path
from urllib.parse import quote

from markdown_it import MarkdownIt

from book_companion.core.layout import PROGRESS_FILE
from book_companion.core.progress import Status
from book_companion.view.layout import Crumb, Page
from book_companion.view.scan import (
    Entity,
    Library,
    Series,
    Volume,
    is_spoiler,
    link_path,
    slug_title,
)

_MARKDOWN = MarkdownIt("commonmark", {"html": False}).enable("table")

NOTE_LABELS = {
    "metadata.md": "Metadata",
    "review.md": "Review",
    "reference.md": "Reference",
    "chapters.md": "Chapter notes",
    "chapters-condensed.md": "Condensed notes",
    "series.md": "Series notes",
}

HOME = Crumb("Library", "/")


def render_markdown(text: str) -> str:
    html: str = _MARKDOWN.render(text)  # typed Any: the renderer is pluggable
    return html


def describe_progress(series: Series) -> str:
    progress = series.progress
    if progress is None:
        return "Reading progress unavailable"
    parts = []
    if not series.standalone and progress.volume is not None:
        parts.append(f"Volume {progress.volume}")
    if progress.status is Status.READING and progress.chapter is not None:
        part = f"part {progress.part}, " if progress.part is not None else ""
        parts.append(f"read through {part}chapter {progress.chapter}")
    elif progress.status is Status.READING and progress.section is not None:
        parts.append(f"read through section {progress.section}")
    else:
        parts.append(progress.status.value)
    if progress.updated is not None:
        parts.append(f"updated {progress.updated.isoformat()}")
    return " · ".join(parts)


# Pages


def index_page(library: Library) -> Page:
    crumbs = (Crumb("Library"),)
    if not library.series:
        return Page("Book library", crumbs,
                    '<h1>Book library</h1><p class="muted">No books yet. Import an EPUB with '
                    "the book-import skill, then reload this page.</p>")
    cards = []
    for series in library.series:
        counts = [_count(len(series.volumes), "book")] + [
            _count(len(group), slug_title(name).lower().rstrip("s"))
            for name, group in series.categories.items()]
        strip = "".join(_thumb(library, entity, css="") for entity in series.entities
                        if entity.images)
        cards.append(
            f'<a class="card series-card" href="{_href(library, series.path, directory=True)}">'
            f"<h2>{escape(series.title)}</h2>"
            f'<div class="muted">{escape(series.author)}</div>'
            f"<div>{escape(describe_progress(series))}</div>"
            f'<div class="muted">{escape(" · ".join(counts))}</div>'
            + (f'<div class="strip">{strip}</div>' if strip else "") + "</a>")
    body = f'<h1>Book library</h1><div class="grid" style="--min: 320px">{"".join(cards)}</div>'
    return Page("Book library", crumbs, body)


def series_page(library: Library, series: Series) -> Page:
    out = [f"<h1>{escape(series.title)}</h1>",
           f'<p class="byline">{escape(series.author)}'
           f"{' · standalone' if series.standalone else ''}</p>"]
    if series.progress_error:
        out.append(f'<div class="banner error">Could not read the reading progress: '
                   f"{escape(series.progress_error)} Every memory note is treated as a spoiler "
                   "until it is fixed.</div>")
    else:
        out.append(f'<div class="panel"><strong>Reading progress:</strong> '
                   f"{escape(describe_progress(series))}{_progress_notes(series)}</div>")
    out.append(_books(library, series))
    for name, entities in series.categories.items():
        out.append(_category(library, name, entities))
    if not series.categories:
        out.append('<p class="muted">No characters, locations or other entities yet.</p>')
    return Page(series.title, (HOME, Crumb(series.title)), "".join(out))


def entity_page(library: Library, series: Series, entity: Entity) -> Page:
    category = slug_title(entity.category)
    out = [f"<h1>{escape(entity.name)}</h1>",
           f'<p class="byline">{escape(category.rstrip("s"))} · {escape(series.title)}</p>']
    figures = []
    for image in entity.images:
        prompt = ""
        if image.prompt is not None:
            prompt = (f'<details class="prompt"><summary>Prompt</summary>'
                      f'<div class="prose">{render_markdown(_read(image.prompt))}</div></details>')
        href = _href(library, image.path)
        figures.append(f'<figure><a href="{href}"><img src="{href}" alt="{escape(entity.name)}">'
                       f"</a><figcaption>{escape(image.path.name)}</figcaption>{prompt}</figure>")
    if entity.description is not None:
        text = _without_title(_read(entity.description))
        description = f'<div class="prose">{render_markdown(text)}</div>'
    else:
        description = '<p class="muted">No description yet.</p>'
    if figures:
        out.append(f'<div class="entity has-images"><div class="gallery">{"".join(figures)}</div>'
                   f"<div>{description}</div></div>")
    else:
        out.append(f'<div class="entity">{description}</div>')
    if entity.pending:
        out.append("<h2>Prompts waiting for an image</h2>")
        for path in entity.pending:
            out.append(f'<details class="prompt"><summary>{escape(path.name)}</summary>'
                       f'<div class="prose">{render_markdown(_read(path))}</div></details>')
    series_url = _url(library, series.path, directory=True)
    crumbs = (HOME, Crumb(series.title, series_url),
              Crumb(category, f"{series_url}#{quote(entity.category)}"), Crumb(entity.name))
    return Page(f"{entity.name} · {series.title}", crumbs, "".join(out))


def note_page(library: Library, series: Series, volume: Volume | None, note: Path) -> Page:
    label = NOTE_LABELS.get(note.name, note.name)
    content = f'<div class="prose">{render_markdown(_read(note))}</div>'
    if volume is not None and is_spoiler(volume, note):
        where = ("This book" if series.standalone or volume.number is None
                 else f"Volume {volume.number}")
        content = (f'<details class="spoiler"><summary>⚠ Spoilers: {escape(where)} is past your '
                   f"reading progress ({escape(describe_progress(series))}). Show anyway"
                   f"</summary>{content}</details>")
    crumbs = [HOME, Crumb(series.title, _url(library, series.path, directory=True))]
    title = series.title
    if volume is not None and not series.standalone:
        crumbs.append(Crumb(_volume_label(series, volume)))
        title = volume.title
    crumbs.append(Crumb(label))
    return Page(f"{label} · {title}", tuple(crumbs), content)


def error_page(status: int, message: str) -> Page:
    return Page(str(status), (HOME,), f"<h1>{status}</h1><p>{escape(message)}</p>")


# Pieces


def _books(library: Library, series: Series) -> str:
    heading = "Book" if series.standalone else "Volumes"
    out = [f'<h2>{heading}</h2><ul class="books">']
    for volume in series.volumes:
        links = []
        for note in volume.notes:
            label = escape(NOTE_LABELS.get(note.name, note.name))
            if is_spoiler(volume, note):
                links.append(f'<a class="pill past" href="{_href(library, note)}" '
                             f'title="Past your reading progress">⚠ {label}</a>')
            else:
                links.append(f'<a class="pill" href="{_href(library, note)}">{label}</a>')
        notes = "".join(links) or '<span class="muted">no notes</span>'
        out.append(f"<li><span>{escape(_volume_label(series, volume))}</span>{notes}</li>")
    if series.note:
        out.append(f'<li><a class="pill" href="{_href(library, series.note)}">Series notes</a>'
                   "</li>")
    out.append("</ul>")
    return "".join(out)


def _category(library: Library, name: str, entities: list[Entity]) -> str:
    cards = []
    for entity in entities:
        detail = _count(len(entity.images), "image") if entity.images else "no images"
        if entity.description is None:
            detail += " · no description"
        cards.append(f'<a class="card" href="{_href(library, entity.path, directory=True)}">'
                     f"{_thumb(library, entity)}"
                     f'<div class="body"><div class="name">{escape(entity.name)}</div>'
                     f'<div class="muted">{detail}</div></div></a>')
    return (f'<h2 id="{escape(name)}">{escape(slug_title(name))} '
            f'<span class="muted">({len(entities)})</span></h2>'
            f'<div class="grid">{"".join(cards)}</div>')


def _progress_notes(series: Series) -> str:
    """The free-form notes below the front matter of reading-progress.md."""
    lines = _read(series.path / PROGRESS_FILE).splitlines()
    if lines and lines[0].strip() == "---":
        end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), 0)
        lines = lines[end + 1:]
    text = "\n".join(lines)
    if not text.strip():
        return ""
    return (f'<details><summary>Progress notes</summary><div class="prose">'
            f"{render_markdown(text)}</div></details>")


def _thumb(library: Library, entity: Entity, css: str = "thumb") -> str:
    if not entity.images:
        return f'<div class="{css} empty" aria-hidden="true">{escape(entity.name[:1])}</div>'
    return (f'<img class="{css}" src="{_href(library, entity.images[0].path)}" '
            f'alt="{escape(entity.name)}" loading="lazy">')


def _volume_label(series: Series, volume: Volume) -> str:
    if series.standalone or volume.number is None:
        return volume.title
    return f"Volume {volume.number}: {volume.title}"


def _without_title(text: str) -> str:
    """Drop the '# Name' line a description starts with; the page shows it as its title."""
    lines = text.splitlines()
    first = next((i for i, line in enumerate(lines) if line.strip()), None)
    if first is not None and lines[first].startswith("# "):
        del lines[first]
    return "\n".join(lines)


def _count(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def _url(library: Library, path: Path, directory: bool = False) -> str:
    """The percent-encoded URL of a library file or folder."""
    return quote(link_path(library.root, path, directory))


def _href(library: Library, path: Path, directory: bool = False) -> str:
    return escape(_url(library, path, directory))
