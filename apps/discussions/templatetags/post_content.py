from django import template

from common.content import BACKTICK_CODE, split_post_content

register = template.Library()


@register.filter
def preview_code(value):
    """Replace code before preview truncation; never modify the stored post."""
    return "".join(
        "[code snippet]"
        if block["kind"] == "code"
        else BACKTICK_CODE.sub("[code snippet]", block["text"])
        for block in split_post_content(value)
    )


@register.inclusion_tag("components/post_content.html")
def render_post_content(value):
    # The component uses normal Django escaping for both prose and code.
    return {"blocks": split_post_content(value)}
