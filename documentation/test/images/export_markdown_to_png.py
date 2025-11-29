import base64
import re
from pathlib import Path

import markdown
from odf.draw import Frame, Image
from odf.opendocument import OpenDocumentText
from odf.style import ParagraphProperties, Style
from odf.text import A, BookmarkEnd, BookmarkStart, H, P, Span
from PIL import Image as PIL_IMAGE
from playwright.sync_api import sync_playwright

# Pip installs
# pip install markdown odfpy

# Post document conversions:
# libreoffice --headless --convert-to docx all_tests.odt

IMAGE_MD_PATTERN = re.compile(
    r"!\[(?P<alt>[^\]]*)\]\((?P<path>\.\./\.\./supporting_images/[^)]+)\)",
    re.IGNORECASE,
)

# Load CSS from export_format.css (same folder)
BASE_DIR = Path(__file__).parent
CSS_FILE_REST = BASE_DIR / "export_format_rest.css"
CSS_FILE_TM = BASE_DIR / "export_format_tm.css"

CUSTOM_CSS_REST = CSS_FILE_REST.read_text(encoding="utf-8")
CUSTOM_CSS_TM = CSS_FILE_TM.read_text(encoding="utf-8")


# Detect category based on file prefix
def get_category_from_filename(filename: str) -> str:
    filename = filename.upper()

    if filename.startswith("UT-"):
        return "UT"
    if filename.startswith("MAT-"):
        return "MAT"
    if filename.startswith("UAT-"):
        return "UAT"
    if filename.startswith("ST-"):
        return "ST"
    if filename.startswith("TRACEABILITY_MATRIX"):
        return "TRACEABILITY_MATRIX"

    raise ValueError(f"Unknown category for filename: {filename}")


# Detect css category based on category from filename
def get_css_for_category(category):
    if category == "TRACEABILITY_MATRIX":
        return CUSTOM_CSS_TM
    return CUSTOM_CSS_REST


# Detect pixel density based on category from filename
def get_pixel_for_category(category):
    if category == "TRACEABILITY_MATRIX":
        return "1850px"
    return "1200px"


# Build output path based on detected category
def map_output_path(md_path: Path) -> Path:
    category = get_category_from_filename(md_path.name)
    out_base = BASE_DIR / category
    return out_base / md_path.with_suffix(".png").name


def inline_supporting_images(markdown_text: str, md_path: Path) -> str:
    """Replace ../../supporting_images/... markdown images with base64 <img> tags."""

    def repl(match: re.Match) -> str:
        alt = match.group("alt")
        rel_path = match.group("path")

        img_file = (md_path.parent / rel_path).resolve()
        if not img_file.is_file():
            # If the file is missing, keep original markdown
            return match.group(0)

        # Infer MIME type from extension
        ext = img_file.suffix.lower()
        if ext == ".png":
            mime = "image/png"
        elif ext in (".jpg", ".jpeg"):
            mime = "image/jpeg"
        elif ext == ".gif":
            mime = "image/gif"
        else:
            # Unknown type; keep original markdown
            return match.group(0)

        data = img_file.read_bytes()
        b64 = base64.b64encode(data).decode("ascii")
        data_uri = f"data:{mime};base64,{b64}"

        return f'<img alt="{alt}" src="{data_uri}"/>'

    return IMAGE_MD_PATTERN.sub(repl, markdown_text)


# Convert Markdown → PNG
def convert_markdown_to_png(md_path: Path, out_path: Path):
    raw_md = md_path.read_text(encoding="utf-8")

    # Inline any ../../supporting_images/... references as base64 <img> tags
    md_processed = inline_supporting_images(raw_md, md_path)

    html_body = markdown.markdown(
        md_processed,
        extensions=["fenced_code", "tables", "toc"],
    )

    category = get_category_from_filename(md_path.name)
    css_block = get_css_for_category(category)
    pixel_value = get_pixel_for_category(category)

    html = f"""
    <html>
        <head>
            <meta charset="utf-8"/>
            <style>{css_block}</style>
        </head>
        <body>{html_body}</body>
    </html>
    """

    out_path.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(
            viewport={"width": 1400, "height": 2000},
            device_scale_factor=2,
        )
        page.set_content(html, wait_until="networkidle")
        page.evaluate(f'document.body.style.width = "{pixel_value}";')
        page.screenshot(path=str(out_path), full_page=True)
        browser.close()


# Recursively process ALL .md files under ../test/
def export_all_markdowns():
    test_root = BASE_DIR.parent

    for md_file in test_root.rglob("*.md"):
        out_path = map_output_path(md_file)
        print(f"Exporting:\n  {md_file}\n→ {out_path}\n")
        convert_markdown_to_png(md_file, out_path)


def build_odt_from_pngs():
    CATEGORY_ORDER = {
        "MAT": 1,
        "ST": 2,
        "UT": 3,
        "UAT": 4,
        "TRACEABILITY_MATRIX": 5,
    }

    def sort_key(path: Path):
        fname = path.name.upper()
        for prefix in CATEGORY_ORDER:
            if fname.startswith(prefix + "-"):
                return (CATEGORY_ORDER[prefix], fname)
        return (999, fname)

    # Helper functions
    def get_markdown_title(png_path: Path) -> str:
        md_name = png_path.with_suffix(".md").name.upper()

        if md_name.startswith(("MAT-", "UAT-")):
            md_path = BASE_DIR.parent / "acceptance" / png_path.with_suffix(".md").name
        elif md_name.startswith("UT-"):
            md_path = BASE_DIR.parent / "unit" / png_path.with_suffix(".md").name
        elif md_name.startswith("ST-"):
            md_path = BASE_DIR.parent / "system" / png_path.with_suffix(".md").name
        elif md_name.startswith("TRACEABILITY_MATRIX"):
            md_path = BASE_DIR.parent / png_path.with_suffix(".md").name
        else:
            raise Exception(f"Unknown prefix in filename: {png_path}")

        # read non-empty stripped lines
        lines = [ln.strip() for ln in md_path.read_text(encoding="utf-8").splitlines() if ln.strip()]

        if not lines:
            return png_path.stem

        test_id = None
        test_name = None

        for line in lines:
            lower = line.lower()

            # Extract Test ID
            if lower.startswith("**test id:**"):
                test_id = line.split(":", 1)[1].strip().replace("**", "")
                continue

            # Extract Test Case Name
            if lower.startswith("**test case name:**"):
                test_name = line.split(":", 1)[1].strip().replace("**", "")
                break

        # Combine into "ID - Name"
        return f"{test_id} - {test_name}"

    def make_github_link(png_path: Path) -> str:
        md_name = png_path.with_suffix(".md").name.upper()

        if md_name.startswith(("MAT-", "UAT-")):
            subdir = "acceptance"
        elif md_name.startswith("UT-"):
            subdir = "unit"
        elif md_name.startswith("ST-"):
            subdir = "system"
        elif md_name.startswith("TRACEABILITY_MATRIX"):
            subdir = ""
        else:
            raise Exception(f"Unknown prefix in filename: {png_path}")

        base = "https://github.com/vampireLibrarianMonk/my-python-buddy/tree/llm-integration/"

        if subdir:
            return f"{base}documentation/test/{subdir}/{png_path.with_suffix('.md').name}"
        else:
            return f"{base}documentation/test/{png_path.with_suffix('.md').name}"

    # Collect sorted PNGs
    png_files = sorted(
        [p for p in BASE_DIR.rglob("*.png") if "_part" not in p.stem.lower()],
        key=sort_key,
    )

    # Create document
    odt = OpenDocumentText()

    # Page break style for each test case
    page_break_style = Style(name="PageBreak", family="paragraph")
    page_break_style.addElement(ParagraphProperties(breakbefore="page"))
    odt.styles.addElement(page_break_style)

    # Table of Contents Section
    toc_header = H(outlinelevel=1, text="Table of Contents")
    odt.text.addElement(toc_header)

    # Create an indented paragraph style for TOC entries
    toc_style = Style(name="TOCEntry", family="paragraph")
    toc_style.addElement(ParagraphProperties(marginleft="0.8cm"))
    odt.styles.addElement(toc_style)

    # Get the last slot for the enumeration that starts at 1
    tm_slot = len(png_files)

    for idx, png in enumerate(png_files, start=1):
        if idx == tm_slot:  # traceability matrix handling
            title = "Traceability Matrix: "
            git_link = make_github_link(png)
        else:
            title = get_markdown_title(png)
            git_link = make_github_link(png)

        toc_entry = P(stylename=toc_style)
        toc_entry.addElement(Span(text=f"{idx}. {title} - "))
        toc_entry.addElement(A(href=git_link, text="[GitHub]"))
        toc_entry.addElement(Span(text=" | "))
        toc_entry.addElement(A(href=f"#{png.stem}", text="[Image]"))
        toc_style.addElement(ParagraphProperties(marginleft="0.8cm", marginbottom="0.15cm"))
        odt.text.addElement(toc_entry)

    # Divider before screenshots
    screenshot_header = H(outlinelevel=1, text="Test Specification Screenshots")
    odt.text.addElement(screenshot_header)

    # Insert each test case page
    for idx, png in enumerate(png_files, start=1):
        if idx == tm_slot:  # traceability matrix handling
            # Open original TM image
            im = PIL_IMAGE.open(png)
            w, h = im.size
            mid = h // 2  # horizontal split

            # Top half
            top_im = im.crop((0, 0, w, mid))
            top_path = png.with_name(png.stem + "_part1.png")
            top_im.save(top_path)

            # Bottom half
            bottom_im = im.crop((0, mid, w, h))
            bottom_path = png.with_name(png.stem + "_part2.png")
            bottom_im.save(bottom_path)

            # First half: keeps bookmark name for TOC
            internal1 = odt.addPicture(str(top_path))
            frame1 = Frame(width="18cm", height="24cm", anchortype="paragraph")
            frame1.addElement(Image(href=internal1))

            img_p1 = P(stylename=page_break_style)
            img_p1.addElement(BookmarkStart(name=png.stem))
            img_p1.addElement(frame1)
            img_p1.addElement(BookmarkEnd(name=png.stem))
            odt.text.addElement(img_p1)

            # Second half: just another page right after
            internal2 = odt.addPicture(str(bottom_path))
            frame2 = Frame(width="18cm", height="24cm", anchortype="paragraph")
            frame2.addElement(Image(href=internal2))

            img_p2 = P(stylename=page_break_style)
            img_p2.addElement(frame2)
            odt.text.addElement(img_p2)

            # Skip normal single-image handling for this PNG
            continue

        internal = odt.addPicture(str(png))

        # Create the frame that contains the image
        frame = Frame(width="18cm", height="24cm", anchortype="paragraph")
        frame.addElement(Image(href=internal))

        # Image paragraph with bookmark and page break
        img_p = P(stylename=page_break_style)
        img_p.addElement(BookmarkStart(name=png.stem))
        img_p.addElement(frame)
        img_p.addElement(BookmarkEnd(name=png.stem))

        # Add the full paragraph
        odt.text.addElement(img_p)

    # Save file
    output_file = BASE_DIR / "all_tests.odt"
    odt.save(str(output_file))
    print("Created ODT:", output_file)


if __name__ == "__main__":
    export_all_markdowns()
    build_odt_from_pngs()
