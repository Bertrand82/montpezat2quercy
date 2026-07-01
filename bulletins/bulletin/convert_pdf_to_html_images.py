#!/usr/bin/env python3
"""
Convert "Bulletin Montpezat Juillet 26.pdf" to one HTML file per page.

Output:
  bulletins/bulletin/target/page_0.html, page_1.html, ...
  bulletins/bulletin/target/images/   (all extracted images)

Approach:
  - Vector drawings  → absolutely-positioned CSS <div> elements
  - Embedded images  → saved as files in target/images/, referenced by relative path
  - Text spans       → absolutely-positioned visible <span> elements with
                       correct color, font-size and approximate font-family
  This ensures text zones are *real HTML text*, not pixel images.
"""

import os
import re
import fitz  # PyMuPDF

PDF_PATH = os.path.join(os.path.dirname(__file__), "Bulletin Montpezat Juillet 26.pdf")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "target")
IMAGES_DIR = os.path.join(OUTPUT_DIR, "images")

# Scale from PDF points to CSS pixels (1 pt = 1.333 px @ 96 dpi)
SCALE = 1.5

# Map PDF font names → CSS font-family
FONT_MAP = {
    "Kodchasan": "Kodchasan",
    "Montserrat": "Montserrat",
    "AvenirNextCondensed": "Oswald",
    "AvenirNext": "Montserrat",
    "Srisakdi": "Srisakdi",
    "BalooBhaijaan": "Baloo Bhaijaan 2",
    "Fallinlove": "Pacifico",
    "NEONWORLDDEMO": "Impact",
}

GOOGLE_FONTS = [
    "Kodchasan:wght@400;700",
    "Montserrat:wght@400;600;700",
    "Oswald:wght@400;700",
    "Srisakdi:wght@400;700",
    "Baloo+Bhaijaan+2:wght@400;700",
    "Pacifico",
]

# ─────────────────────────── helpers ─────────────────────────────────────────


def rgb_tuple_to_css(t) -> str:
    """Convert (r,g,b) floats 0-1 to CSS #rrggbb."""
    r, g, b = (int(round(c * 255)) for c in t[:3])
    return f"#{r:02x}{g:02x}{b:02x}"


def pdf_font_to_css(font_name: str) -> str:
    """Return a CSS font-family for a PDF font name."""
    clean = re.sub(r'^[A-Z]{6}\+', '', font_name)
    for key, value in FONT_MAP.items():
        if clean.startswith(key):
            return value
    return "sans-serif"


def html_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
    )


# ─────────────────────────── content builders ────────────────────────────────


def build_drawings_html(page, scale: float) -> list:
    """Return HTML strings for vector background shapes."""
    items = []
    for d in page.get_drawings():
        fill = d.get("fill")
        if fill is None:
            continue
        rect = d.get("rect")
        if rect is None:
            continue
        x0, y0, x1, y1 = rect
        pw, ph = page.rect.width, page.rect.height
        x0 = max(0, x0) * scale
        y0 = max(0, y0) * scale
        x1 = min(pw, x1) * scale
        y1 = min(ph, y1) * scale
        w = x1 - x0
        h = y1 - y0
        if w <= 0 or h <= 0:
            continue
        color = rgb_tuple_to_css(fill)
        opacity = fill[3] if len(fill) > 3 else 1.0
        opacity_css = f"opacity:{opacity:.2f};" if opacity < 1.0 else ""
        items.append(
            f'<div style="position:absolute;left:{x0:.1f}px;top:{y0:.1f}px;'
            f'width:{w:.1f}px;height:{h:.1f}px;'
            f'background:{color};{opacity_css}"></div>'
        )
    return items


def build_images_html(doc, page, scale: float, image_counter: list) -> list:
    """Save embedded images to disk and return <img> HTML strings with relative paths."""
    items = []
    seen_xrefs = set()
    for img_info in page.get_images(full=True):
        xref = img_info[0]
        if xref in seen_xrefs:
            continue
        seen_xrefs.add(xref)

        rects = page.get_image_rects(xref)
        if not rects:
            continue

        try:
            img_data = doc.extract_image(xref)
        except Exception:
            continue

        ext = img_data.get("ext", "png")
        # Save image file
        img_filename = f"img_{image_counter[0]:04d}.{ext}"
        img_path = os.path.join(IMAGES_DIR, img_filename)
        with open(img_path, "wb") as f:
            f.write(img_data["image"])
        image_counter[0] += 1

        rel_path = f"images/{img_filename}"

        for rect in rects:
            x0 = rect.x0 * scale
            y0 = rect.y0 * scale
            w = (rect.x1 - rect.x0) * scale
            h = (rect.y1 - rect.y0) * scale
            if w <= 0 or h <= 0:
                continue
            items.append(
                f'<img src="{rel_path}" '
                f'style="position:absolute;left:{x0:.1f}px;top:{y0:.1f}px;'
                f'width:{w:.1f}px;height:{h:.1f}px;" alt="">'
            )
    return items


def build_text_html(page, scale: float) -> list:
    """Return HTML <span> strings for text content with full styling."""
    items = []
    blocks = page.get_text(
        "dict",
        flags=fitz.TEXT_PRESERVE_WHITESPACE | fitz.TEXT_PRESERVE_LIGATURES,
    )["blocks"]

    for block in blocks:
        if block.get("type") != 0:
            continue
        for line in block["lines"]:
            for span in line["spans"]:
                raw_text = span["text"]
                if not raw_text.strip():
                    continue

                ox, oy = span["origin"]
                size_pt = span["size"]

                left = ox * scale
                top = (oy - size_pt) * scale
                font_size = size_pt * scale

                # Convert color: PyMuPDF returns int packed as 0xRRGGBB
                color_int = span["color"]
                r = (color_int >> 16) & 0xFF
                g = (color_int >> 8) & 0xFF
                b = color_int & 0xFF
                color = f"#{r:02x}{g:02x}{b:02x}"

                font_family = pdf_font_to_css(span["font"])
                flags = span["flags"]
                bold = "font-weight:bold;" if (flags & 16) else ""
                italic = "font-style:italic;" if (flags & 2) else ""

                escaped = html_escape(raw_text)
                items.append(
                    f'<span style="position:absolute;left:{left:.1f}px;top:{top:.1f}px;'
                    f'font-size:{font_size:.1f}px;color:{color};'
                    f'font-family:\'{font_family}\',sans-serif;'
                    f'white-space:pre;line-height:1;{bold}{italic}">'
                    f'{escaped}</span>'
                )
    return items


# ─────────────────────────── page builder ────────────────────────────────────

PAGE_TEMPLATE = """\
<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Bulletin Montpezat – Page {display_num}</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?{gfonts_query}&display=swap" rel="stylesheet">
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: #888;
      display: flex;
      flex-direction: column;
      align-items: center;
      font-family: sans-serif;
    }}
    nav {{
      width: 100%;
      background: #333;
      color: #fff;
      text-align: center;
      padding: 8px 16px;
      font-size: 14px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      position: sticky;
      top: 0;
      z-index: 100;
    }}
    nav a {{ color: #ccc; text-decoration: none; font-size: 13px; }}
    nav a:hover {{ color: #fff; }}
    .page {{
      position: relative;
      width: {page_w}px;
      height: {page_h}px;
      margin: 16px;
      overflow: hidden;
      box-shadow: 0 4px 20px rgba(0,0,0,0.5);
      background: white;
    }}
  </style>
</head>
<body>
  <nav>
    <span>{prev_link}</span>
    <span>Bulletin Montpezat en Quercy – Page {display_num} / {total}</span>
    <span>{next_link}</span>
  </nav>

  <div class="page">
{content}
  </div>
</body>
</html>
"""


def build_page_html(doc, page, page_num: int, total: int, scale: float,
                    image_counter: list) -> str:
    pw = page.rect.width * scale
    ph = page.rect.height * scale

    drawings = build_drawings_html(page, scale)
    images = build_images_html(doc, page, scale, image_counter)
    texts = build_text_html(page, scale)

    # Layer order: drawings (background) → images → text (top)
    content_lines = drawings + images + texts
    content = "\n".join(f"    {line}" for line in content_lines)

    prev_link = (
        f'<a href="page_{page_num - 1}.html">&larr; Page {page_num}</a>'
        if page_num > 0 else ""
    )
    next_link = (
        f'<a href="page_{page_num + 1}.html">Page {page_num + 2} &rarr;</a>'
        if page_num < total - 1 else ""
    )

    gfonts_query = "&".join(
        f"family={f.replace(' ', '+')}" for f in GOOGLE_FONTS
    )

    return PAGE_TEMPLATE.format(
        display_num=page_num + 1,
        total=total,
        page_w=f"{pw:.0f}",
        page_h=f"{ph:.0f}",
        content=content,
        prev_link=prev_link,
        next_link=next_link,
        gfonts_query=gfonts_query,
    )


# ─────────────────────────── main ────────────────────────────────────────────

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(IMAGES_DIR, exist_ok=True)

    doc = fitz.open(PDF_PATH)
    total = len(doc)
    print(f"Converting {total} pages  →  '{OUTPUT_DIR}'")
    print(f"Images will be saved to  →  '{IMAGES_DIR}'")

    # Shared counter across all pages to avoid filename collisions
    image_counter = [0]

    for page_num in range(total):
        page = doc[page_num]
        html = build_page_html(doc, page, page_num, total, SCALE, image_counter)
        out_path = os.path.join(OUTPUT_DIR, f"page_{page_num}.html")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html)
        size_kb = len(html) // 1024
        print(f"  page_{page_num}.html  ({size_kb} KB)")

    doc.close()
    img_count = image_counter[0]
    print(f"\nDone – {total} HTML files written to '{OUTPUT_DIR}'")
    print(f"      {img_count} image files extracted to '{IMAGES_DIR}'")


if __name__ == "__main__":
    main()
