#!/usr/bin/env python3
"""
Convert "Bulletin Montpezat Juillet 26.pdf" to one HTML file per page.
Output files: bulletins/bulletin/target/page_0.html, page_1.html, ...
"""

import base64
import os
import fitz  # PyMuPDF

PDF_PATH = os.path.join(os.path.dirname(__file__), "Bulletin Montpezat Juillet 26.pdf")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "target")
DPI = 150  # render resolution – higher = better quality / larger files

HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Bulletin Montpezat – Page {page_num}</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      background: #888;
      display: flex;
      flex-direction: column;
      align-items: center;
      font-family: sans-serif;
    }}
    header {{
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
      z-index: 10;
    }}
    header a {{
      color: #ccc;
      text-decoration: none;
      font-size: 13px;
    }}
    header a:hover {{ color: #fff; }}
    .page-container {{
      margin: 16px;
      box-shadow: 0 4px 16px rgba(0,0,0,0.5);
      line-height: 0;
    }}
    .page-container img {{
      display: block;
      max-width: 100%;
      height: auto;
    }}
    .page-text {{
      position: absolute;
      top: 0; left: 0;
      width: {page_width_px}px;
      height: {page_height_px}px;
      pointer-events: none;
      overflow: hidden;
    }}
    .page-wrapper {{
      position: relative;
      display: inline-block;
    }}
    .page-text span {{
      position: absolute;
      color: transparent;
      white-space: pre;
      cursor: text;
      pointer-events: auto;
      user-select: text;
    }}
  </style>
</head>
<body>
  <header>
    <span>
      {prev_link}
    </span>
    <span>Bulletin Montpezat en Quercy – Page {display_num} / {total_pages}</span>
    <span>
      {next_link}
    </span>
  </header>

  <div class="page-container">
    <div class="page-wrapper">
      <img src="data:image/png;base64,{image_b64}"
           width="{page_width_px}" height="{page_height_px}"
           alt="Page {display_num}">
      <div class="page-text">
{text_spans}
      </div>
    </div>
  </div>
</body>
</html>
"""


def color_to_css(color_int: int) -> str:
    """Convert PyMuPDF integer color to CSS hex."""
    r = (color_int >> 16) & 0xFF
    g = (color_int >> 8) & 0xFF
    b = color_int & 0xFF
    return f"#{r:02x}{g:02x}{b:02x}"


def render_page_as_png_b64(page, dpi: int) -> tuple[str, int, int]:
    """Render a PDF page to PNG and return (base64_str, width_px, height_px)."""
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    png_bytes = pix.tobytes("png")
    b64 = base64.b64encode(png_bytes).decode("ascii")
    return b64, pix.width, pix.height


def build_text_spans(page, page_width_px: int, page_height_px: int) -> str:
    """Build invisible text spans for copy/search over the rendered image."""
    pdf_w = page.rect.width
    pdf_h = page.rect.height
    scale_x = page_width_px / pdf_w
    scale_y = page_height_px / pdf_h

    lines = []
    blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]
    for block in blocks:
        if block.get("type") != 0:
            continue
        for line in block["lines"]:
            for span in line["spans"]:
                text = span["text"]
                if not text.strip():
                    continue
                x0, y0 = span["origin"]
                size = span["size"] * scale_y
                left = x0 * scale_x
                top = (y0 - span["size"]) * scale_y
                lines.append(
                    f'        <span style="left:{left:.1f}px;top:{top:.1f}px;'
                    f'font-size:{size:.1f}px">{text}</span>'
                )
    return "\n".join(lines)


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    doc = fitz.open(PDF_PATH)
    total = len(doc)
    print(f"Converting {total} pages from '{PDF_PATH}' …")

    for page_num in range(total):
        page = doc[page_num]
        img_b64, w_px, h_px = render_page_as_png_b64(page, DPI)
        text_spans = build_text_spans(page, w_px, h_px)

        prev_link = (
            f'<a href="page_{page_num - 1}.html">&larr; Page {page_num}</a>'
            if page_num > 0
            else ""
        )
        next_link = (
            f'<a href="page_{page_num + 1}.html">Page {page_num + 2} &rarr;</a>'
            if page_num < total - 1
            else ""
        )

        html = HTML_TEMPLATE.format(
            page_num=page_num,
            display_num=page_num + 1,
            total_pages=total,
            page_width_px=w_px,
            page_height_px=h_px,
            image_b64=img_b64,
            text_spans=text_spans,
            prev_link=prev_link,
            next_link=next_link,
        )

        out_path = os.path.join(OUTPUT_DIR, f"page_{page_num}.html")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"  page_{page_num}.html  ({w_px}×{h_px} px, {len(html) // 1024} KB)")

    doc.close()
    print(f"\nDone – {total} files written to '{OUTPUT_DIR}'")


if __name__ == "__main__":
    main()
