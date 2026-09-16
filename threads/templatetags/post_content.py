"""Render pasted, fenced code without treating post content as HTML."""

import re

from django import template

register = template.Library()

FENCED_CODE = re.compile(
    r"(?<!`)(?P<fence>`{3,})[ \t]*(?P<language>[\w.+#-]*)[ \t]*\n"
    r"(?P<code>.*?)(?<!`)(?P=fence)(?!`)",
    re.DOTALL,
)
BACKTICK_CODE = re.compile(r"(?<!`)(?P<ticks>`+)(?!`).*?(?<!`)(?P=ticks)(?!`)", re.DOTALL)


def split_post_content(value):
    """Keep prose, code indentation, and unmatched fences intact."""
    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
    blocks = []
    position = 0
    for match in FENCED_CODE.finditer(text):
        if match.start() > position:
            blocks.append({"kind": "text", "text": text[position:match.start()]})
        blocks.append({
            "kind": "code",
            "text": match["code"].removesuffix("\n"),
            "language": match["language"] or "Code",
        })
        position = match.end()
    if position < len(text):
        blocks.append({"kind": "text", "text": text[position:]})
    return blocks


@register.filter
def preview_code(value):
    """Replace code before preview truncation; never modify the stored post."""
    return "".join(
        "[code snippet]" if block["kind"] == "code"
        else BACKTICK_CODE.sub("[code snippet]", block["text"])
        for block in split_post_content(value)
    )


@register.inclusion_tag("threads/partials/post_content.html")
def render_post_content(value):
    # The component uses normal Django escaping for both prose and code.
    return {"blocks": split_post_content(value)}
