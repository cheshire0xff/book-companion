"""The HTML pages of book-view: plain strings, with one inline stylesheet and no scripts."""

from __future__ import annotations

from html import escape
from pathlib import Path
from urllib.parse import quote

from markdown_it import MarkdownIt

from book_companion.core.progress import Status
from book_companion.view.scan import (
    Entity,
    Library,
    Series,
    Volume,
    is_spoiler,
    link_path,
    slug_title,
)

# Raw HTML in a note is shown as text, never run.
_MARKDOWN = MarkdownIt("commonmark", {"html": False}).enable("table")

NOTE_LABELS = {
    "metadata.md": "Metadata",
    "reference.md": "Reference",
    "chapters.md": "Chapter notes",
    "chapters-condensed.md": "Condensed notes",
    "series.md": "Series notes",
}

STYLE = """
:root {
  color-scheme: light dark;
  --bg: #f6f3ee; --surface: #ffffff; --text: #1f1c18; --muted: #6d675e;
  --border: #e2dcd2; --accent: #8a4a1f; --warn-bg: #fff4dc; --warn-text: #7a4b00;
  --error-bg: #fde8e6; --error-text: #8c1d12; --placeholder: #ece6dc;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #161412; --surface: #201d1a; --text: #ece7df; --muted: #a59e93;
    --border: #36312b; --accent: #e3a66f; --warn-bg: #3a2c12; --warn-text: #f3cd85;
    --error-bg: #3d1c18; --error-text: #f5b3aa; --placeholder: #2b2723;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg); color: var(--text);
  font: 16px/1.5 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
}
main { max-width: 1120px; margin: 0 auto; padding: 20px 16px 64px; }
a { color: var(--accent); }
h1 { font: 600 2rem/1.2 Charter, "Iowan Old Style", Georgia, serif; margin: 8px 0 4px; }
h2 { font: 600 1.3rem/1.3 Charter, "Iowan Old Style", Georgia, serif; margin: 32px 0 12px; }
.crumbs { font-size: .9rem; color: var(--muted); }
.crumbs a { color: var(--muted); text-decoration: none; }
.crumbs a:hover { color: var(--accent); text-decoration: underline; }
.byline, .muted { color: var(--muted); }
.byline { margin: 0 0 16px; }
.grid { display: grid; gap: 16px; --min: 180px;
        grid-template-columns: repeat(auto-fill, minmax(min(var(--min), 100%), 1fr)); }
@media (max-width: 520px) { .grid { --min: 140px; gap: 12px; } }
h1 + .grid { margin-top: 16px; }
.card {
  display: block; background: var(--surface); border: 1px solid var(--border);
  border-radius: 10px; overflow: hidden; color: inherit; text-decoration: none;
}
a.card:hover { border-color: var(--accent); }
.card .body { padding: 10px 12px 12px; }
.card .name { font-weight: 600; }
.card .muted { font-size: .875rem; }
.thumb { display: block; width: 100%; aspect-ratio: 4 / 5; object-fit: cover;
         object-position: center 25%; background: var(--placeholder); }
.thumb.empty { display: grid; place-items: center; font: 600 2.5rem Georgia, serif;
               color: var(--muted); }
.series-card { padding: 16px; }
.series-card h2 { margin: 0 0 2px; }
.strip { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 12px; }
.strip img { width: 52px; height: 52px; object-fit: cover; object-position: center 25%;
             border-radius: 6px; background: var(--placeholder); }
.panel { background: var(--surface); border: 1px solid var(--border);
         border-radius: 10px; padding: 12px 16px; }
.banner { border-radius: 10px; padding: 12px 16px; margin: 12px 0; }
.banner.error { background: var(--error-bg); color: var(--error-text); }
.books { list-style: none; padding: 0; margin: 0; display: grid; gap: 8px; }
.books li { display: flex; flex-wrap: wrap; gap: 6px 12px; align-items: baseline; }
.pill { display: inline-block; padding: 1px 10px; border: 1px solid var(--border);
        border-radius: 999px; font-size: .875rem; text-decoration: none; }
.pill.past { border-color: var(--warn-text); color: var(--warn-text); }
.entity { display: grid; gap: 24px; }
@media (min-width: 860px) {
  .entity.has-images { grid-template-columns: minmax(0, 5fr) minmax(0, 6fr); align-items: start; }
}
.gallery { display: grid; gap: 20px; }
figure { margin: 0; }
figure img { display: block; max-width: 100%; max-height: 85vh; margin: 0 auto;
             border-radius: 10px; background: var(--placeholder); }
figcaption { font-size: .875rem; color: var(--muted); margin: 6px 0; overflow-wrap: anywhere; }
details > summary { cursor: pointer; color: var(--accent); }
details.prompt { margin-top: 4px; }
details.prompt > .prose { margin-top: 8px; font-size: .95rem; }
details.spoiler > summary {
  background: var(--warn-bg); color: var(--warn-text); border-radius: 10px;
  padding: 12px 16px; list-style-position: inside;
}
.prose { font-family: Charter, "Iowan Old Style", Georgia, serif; font-size: 1.05rem;
         line-height: 1.6; max-width: 75ch; overflow-wrap: break-word; }
.prose h1 { font-size: 1.8rem; }
.prose li { margin: 4px 0; }
.prose blockquote { margin: 12px 0; padding: 4px 16px; border-left: 3px solid var(--border);
                    color: var(--muted); }
.prose code { font-size: .9em; }
.prose img { max-width: 100%; }
.prose table { display: block; overflow-x: auto; border-collapse: collapse; font-size: .95rem; }
.prose th, .prose td { border: 1px solid var(--border); padding: 6px 10px; vertical-align: top;
                       text-align: left; }
"""


def render_markdown(text: str) -> str:
    html: str = _MARKDOWN.render(text)  # typed Any: the renderer is pluggable
    return html


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def _href(library: Library, path: Path, directory: bool = False) -> str:
    return escape(quote(link_path(library.root, path, directory)))


def _page(title: str, crumbs: list[tuple[str, str | None]], body: str) -> str:
    trail = " › ".join(f'<a href="{href}">{escape(label)}</a>' if href else escape(label)
                       for label, href in crumbs)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title>
<style>{STYLE}</style>
</head>
<body>
<main>
<nav class="crumbs">{trail}</nav>
{body}
</main>
</body>
</html>
"""


def _series_crumbs(library: Library, series: Series) -> list[tuple[str, str | None]]:
    return [("Library", "/"), (series.title, _href(library, series.path, directory=True))]


def describe_progress(series: Series) -> str:
    progress = series.progress
    if progress is None:
        return "Reading progress unavailable"
    parts = []
    if not series.standalone and progress.book is not None:
        parts.append(f"Book {progress.book}")
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


def _volume_label(series: Series, volume: Volume) -> str:
    if series.standalone or volume.number is None:
        return volume.title
    return f"Book {volume.number}: {volume.title}"


def _thumb(library: Library, entity: Entity, css: str = "thumb") -> str:
    if not entity.images:
        return f'<div class="{css} empty" aria-hidden="true">{escape(entity.name[:1])}</div>'
    image = entity.images[0]
    return (f'<img class="{css}" src="{_href(library, image.path)}" alt="{escape(entity.name)}" '
            f'loading="lazy">')


def _count(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def index_page(library: Library) -> str:
    if not library.series:
        body = ('<h1>Book library</h1><p class="muted">No books yet. Import an EPUB with the '
                "book-import skill, then reload this page.</p>")
        return _page("Book library", [("Library", None)], body)
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
    body = (f"<h1>Book library</h1>"
            f'<div class="grid" style="--min: 320px">{"".join(cards)}</div>')
    return _page("Book library", [("Library", None)], body)


def series_page(library: Library, series: Series) -> str:
    out = [f"<h1>{escape(series.title)}</h1>",
           f'<p class="byline">{escape(series.author)}'
           f"{' · standalone' if series.standalone else ''}</p>"]
    if series.progress_error:
        out.append(f'<div class="banner error">Could not read the reading progress: '
                   f"{escape(series.progress_error)} Every memory note is treated as a spoiler "
                   "until it is fixed.</div>")
    else:
        out.append(f'<div class="panel"><strong>Reading progress:</strong> '
                   f"{escape(describe_progress(series))}"
                   + _progress_notes(series) + "</div>")

    out.append("<h2>Books</h2><ul class=\"books\">")
    for volume in series.volumes:
        links = []
        for note in volume.notes:
            label = NOTE_LABELS.get(note.name, note.name)
            if is_spoiler(volume, note):
                links.append(f'<a class="pill past" href="{_href(library, note)}" '
                             f'title="Past your reading progress">⚠ {escape(label)}</a>')
            else:
                links.append(f'<a class="pill" href="{_href(library, note)}">{escape(label)}</a>')
        notes = "".join(links) or '<span class="muted">no notes</span>'
        out.append(f"<li><span>{escape(_volume_label(series, volume))}</span>{notes}</li>")
    if series.note:
        out.append(f'<li><a class="pill" href="{_href(library, series.note)}">Series notes</a>'
                   "</li>")
    out.append("</ul>")

    for name, entities in series.categories.items():
        out.append(f'<h2 id="{escape(name)}">{escape(slug_title(name))} '
                   f'<span class="muted">({len(entities)})</span></h2><div class="grid">')
        for entity in entities:
            detail = _count(len(entity.images), "image") if entity.images else "no images"
            if entity.description is None:
                detail += " · no description"
            out.append(f'<a class="card" href="{_href(library, entity.path, directory=True)}">'
                       f"{_thumb(library, entity)}"
                       f'<div class="body"><div class="name">{escape(entity.name)}</div>'
                       f'<div class="muted">{detail}</div></div></a>')
        out.append("</div>")
    if not series.categories:
        out.append('<p class="muted">No characters, locations or other entities yet.</p>')
    return _page(series.title, [("Library", "/"), (series.title, None)], "".join(out))


def _progress_notes(series: Series) -> str:
    """The free-form notes below the front matter of reading-progress.md."""
    text = _read(series.path / "reading-progress.md")
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), 0)
        text = "\n".join(lines[end + 1:])
    if not text.strip():
        return ""
    return (f'<details><summary>Progress notes</summary><div class="prose">'
            f"{render_markdown(text)}</div></details>")


def _without_title(text: str) -> str:
    """Drop the '# Name' line a description starts with; the page shows it as its title."""
    lines = text.splitlines()
    first = next((i for i, line in enumerate(lines) if line.strip()), None)
    if first is not None and lines[first].startswith("# "):
        del lines[first]
    return "\n".join(lines)


def entity_page(library: Library, series: Series, entity: Entity) -> str:
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
    series_href = _href(library, series.path, directory=True)
    crumbs = _series_crumbs(library, series) + [
        (category, f"{series_href}#{escape(quote(entity.category))}"), (entity.name, None)]
    return _page(f"{entity.name} · {series.title}", crumbs, "".join(out))


def note_page(library: Library, series: Series, volume: Volume | None, note: Path) -> str:
    label = NOTE_LABELS.get(note.name, note.name)
    content = f'<div class="prose">{render_markdown(_read(note))}</div>'
    if volume is not None and is_spoiler(volume, note):
        where = "This book" if series.standalone or volume.number is None \
            else f"Book {volume.number}"
        content = (f'<details class="spoiler"><summary>⚠ Spoilers: {escape(where)} is past your '
                   f"reading progress ({escape(describe_progress(series))}). Show anyway"
                   f"</summary>{content}</details>")
    crumbs = _series_crumbs(library, series)
    title = series.title
    if volume is not None and not series.standalone:
        crumbs.append((_volume_label(series, volume), None))
        title = volume.title
    crumbs.append((label, None))
    return _page(f"{label} · {title}", crumbs, content)


def error_page(status: int, message: str) -> str:
    return _page(f"{status}", [("Library", "/")],
                 f"<h1>{status}</h1><p>{escape(message)}</p>")
