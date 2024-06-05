from typing import List

from openparse.pdf import Pdf
from openparse.schemas import Bbox, LineElement, TextElement, TextSpan


def flags_decomposer(flags: int) -> str:
    """Make font flags human readable."""
    l = []
    if flags & 2**0:
        l.append("superscript")
    if flags & 2**1:
        l.append("italic")
    if flags & 2**2:
        l.append("serifed")
    else:
        l.append("sans")
    if flags & 2**3:
        l.append("monospaced")
    else:
        l.append("proportional")
    if flags & 2**4:
        l.append("bold")
    return ", ".join(l)


def is_bold(flags) -> bool:
    return bool(flags & 2**4)


def is_italic(flags) -> bool:
    return bool(flags & 2**1)


def _lines_from_ocr_output(lines: dict, error_margin: float = 0) -> List[LineElement]:
    """
    Creates LineElement objects from given lines, combining overlapping ones.
    """
    combined: List[LineElement] = []

    for line in lines:
        bbox = line["bbox"]
        spans = [
            TextSpan(
                text=span["text"],
                is_bold=is_bold(span["flags"]),
                is_italic=is_italic(span["flags"]),
                size=span["size"],
            )
            for span in line["spans"]
        ]

        line_element = LineElement(bbox=bbox, spans=tuple(spans))
        for i, other in enumerate(combined):
            overlaps = line_element.overlaps(other, error_margin=error_margin)
            similar_height = line_element.is_at_similar_height(
                other, error_margin=error_margin
            )

            if overlaps and similar_height:
                combined[i] = line_element.combine(other)
                break
        else:
            combined.append(line_element)

    return combined


def ingest(
    doc: Pdf,
) -> List[TextElement]:
    """Parses text elements from a given pdf document."""
    elements = []
    pdoc = doc.to_pymupdf_doc()
    for page_num, page in enumerate(pdoc):
        page_ocr = page.get_textpage()
        # page_ocr = page.get_textpage_ocr(flags=0, full=False)
        page_nodes= page.get_text("dict", textpage=page_ocr, sort=True)["blocks"]
        for node in page_nodes:
            if node["type"] != 0:
                continue

            lines = _lines_from_ocr_output(node["lines"])

            # Flip y-coordinates to match the top-left origin system
            fy0 = page.rect.height - node["bbox"][3]
            fy1 = page.rect.height - node["bbox"][1]

            # Calculate some stats about the lines
            def calc_line_height(line):
                return line.bbox[3]-line.bbox[1]


            line_heights = [calc_line_height(line) for line in lines]
            line_gaps = [lines[i+1].bbox[1] - lines[i].bbox[3] for i in range(len(lines)-1)]

            EOS_MARKS = [".", "!", "?", "#"]
            MARKDOWN_HEADERS = ['**', "##"]

            def should_add_newline(text):
                if not text:
                    return False
                if text[-1] in EOS_MARKS:
                    return True
                if text[-2:] in MARKDOWN_HEADERS:
                    return True
                return False

            text = ""
            for line in lines:

                if text and should_add_newline(text):
                    text += "\n" + line.text
                else:
                    text += " " + line.text
                text = text.strip()


            elements.append(
                TextElement(
                    bbox=Bbox(
                        x0=node["bbox"][0],
                        y0=fy0,
                        x1=node["bbox"][2],
                        y1=fy1,
                        page=page_num,
                        page_width=page.rect.width,
                        page_height=page.rect.height,
                    ),
                    text=text,
                    lines=tuple(lines),
                )
            )
    return elements
