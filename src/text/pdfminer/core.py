from typing import List

from src.schemas import TextElement, LineElement, Bbox, TextSpan

from typing import List, Any, Iterable
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer, LTChar, LTTextLine
from pydantic import BaseModel, model_validator


class CharElement(BaseModel):
    text: str
    fontname: str
    size: float

    @property
    def is_bold(self) -> bool:
        return "Bold" in self.fontname or "bold" in self.fontname

    @property
    def is_italic(self) -> bool:
        return "Italic" in self.fontname or "italic" in self.fontname

    @model_validator(mode="before")
    @classmethod
    def round_size(cls, data: Any) -> Any:
        data["size"] = round(data["size"], 2)
        return data


def extract_chars(text_line: LTTextLine) -> List[CharElement]:
    return [
        CharElement(text=char.get_text(), fontname=char.fontname, size=char.size)
        for char in text_line
        if isinstance(char, LTChar)
    ]


def group_chars_into_spans(chars: Iterable[CharElement]) -> List[TextSpan]:
    spans = []
    current_text = ""
    current_style = (False, False, 0.0)

    for char in chars:
        char_style = (char.is_bold, char.is_italic, char.size)
        # If the current character is a space, compress multiple spaces and continue loop.
        if char.text.isspace():
            if not current_text.endswith(" "):
                current_text += " "
            continue

        # If style changes and there's accumulated text, add it to spans.
        if char_style != current_style and current_text:
            # Ensure there is at most one space at the end of the text.
            spans.append(
                TextSpan(
                    text=current_text.rstrip()
                    + (" " if current_text.endswith(" ") else ""),
                    is_bold=current_style[0],
                    is_italic=current_style[1],
                    size=current_style[2],
                )
            )
            current_text = char.text
        else:
            current_text += char.text
        current_style = char_style

    # After the loop, add any remaining text as a new span.
    if current_text:
        spans.append(
            TextSpan(
                text=current_text.rstrip()
                + (" " if current_text.endswith(" ") else ""),
                is_bold=current_style[0],
                is_italic=current_style[1],
                size=current_style[2],
            )
        )
    return spans


def create_line_element(text_line: LTTextLine) -> LineElement:
    """Create a LineElement from a text line."""
    chars = extract_chars(text_line)
    spans = group_chars_into_spans(chars)
    bbox = (text_line.x0, text_line.y0, text_line.x1, text_line.y1)
    return LineElement(bbox=bbox, spans=spans)


def get_bbox(lines: List[LineElement]) -> tuple[float, float, float, float]:
    """Get the bounding box of a list of LineElements."""
    x0 = min(line.bbox[0] for line in lines)
    y0 = min(line.bbox[1] for line in lines)
    x1 = max(line.bbox[2] for line in lines)
    y1 = max(line.bbox[3] for line in lines)
    return x0, y0, x1, y1


def ingest(file_path: str) -> List[TextElement]:
    """Parse PDF and return a list of LineElement objects."""
    elements = []
    for page_num, page_layout in enumerate(extract_pages(file_path)):
        page_width = page_layout.width
        page_height = page_layout.height
        for element in page_layout:
            if isinstance(element, LTTextContainer):
                lines = []
                for text_line in element:
                    if isinstance(text_line, LTTextLine):
                        lines.append(create_line_element(text_line))

                bbox = get_bbox(lines)
                elements.append(
                    TextElement(
                        bbox=Bbox(
                            x0=bbox[0],
                            y0=bbox[1],
                            x1=bbox[2],
                            y1=bbox[3],
                            page=page_num,
                            page_width=page_width,
                            page_height=page_height,
                        ),
                        text="\n".join(line.text for line in lines),
                        lines=lines,
                    )
                )

    return elements
