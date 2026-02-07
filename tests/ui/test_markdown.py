"""Tests for the markdown-it mailto display plugin."""

from markdown_it import MarkdownIt

from ganban.model.node import Node
from ganban.ui.emoji import emoji_for_email
from ganban.ui.markdown import ganban_parser_factory, mailto_display_plugin


def _inline_children(md, source):
    """Parse source and return children of the first inline token."""
    tokens = md.parse(source)
    for t in tokens:
        if t.type == "inline" and t.children:
            return t.children
    return []


def _text_tokens(md, source):
    """Parse source and return text tokens from the first inline token."""
    return [c for c in _inline_children(md, source) if c.type == "text"]


def test_known_user_replaced():
    """Mailto link text is replaced with emoji + display name from meta.users."""
    meta = Node(users={"Alice": {"emoji": "🤖", "emails": ["alice@example.com"]}})
    md = MarkdownIt("gfm-like")
    md.use(mailto_display_plugin, meta, None)
    texts = _text_tokens(md, "[alice](mailto:alice@example.com)")
    assert texts[0].content == "🤖 Alice"


def test_known_user_no_custom_emoji():
    """Known user without custom emoji gets hash-based emoji."""
    meta = Node(users={"Bob": {"emails": ["bob@example.com"]}})
    md = MarkdownIt("gfm-like")
    md.use(mailto_display_plugin, meta, None)
    texts = _text_tokens(md, "[bob](mailto:bob@example.com)")
    assert texts[0].content == f"{emoji_for_email('bob@example.com')} Bob"


def test_committer_fallback():
    """Email found in git committers uses committer name + hash emoji."""
    meta = Node()
    committers = ["Bobby Marley <bob@reggae.org>"]
    md = MarkdownIt("gfm-like")
    md.use(mailto_display_plugin, meta, committers)
    texts = _text_tokens(md, "[Bobby](mailto:bob@reggae.org)")
    assert texts[0].content == f"{emoji_for_email('bob@reggae.org')} Bobby Marley"


def test_meta_users_override_committers():
    """meta.users takes priority over git committers."""
    meta = Node(users={"Bob": {"emoji": "🎸", "emails": ["bob@reggae.org"]}})
    committers = ["Bobby Marley <bob@reggae.org>"]
    md = MarkdownIt("gfm-like")
    md.use(mailto_display_plugin, meta, committers)
    texts = _text_tokens(md, "[Bobby](mailto:bob@reggae.org)")
    assert texts[0].content == "🎸 Bob"


def test_unknown_preserves_link_text():
    """Unknown email preserves the original link text with hash emoji."""
    meta = Node()
    md = MarkdownIt("gfm-like")
    md.use(mailto_display_plugin, meta, None)
    texts = _text_tokens(md, "[Bobby](mailto:unknown@example.com)")
    assert texts[0].content == f"{emoji_for_email('unknown@example.com')} Bobby"


def test_non_mailto_links_untouched():
    """Non-mailto links are left as-is."""
    meta = Node(users={"Alice": {"emoji": "🤖", "emails": ["alice@example.com"]}})
    md = MarkdownIt("gfm-like")
    md.use(mailto_display_plugin, meta, None)
    texts = _text_tokens(md, "[click here](https://example.com)")
    assert texts[0].content == "click here"


def test_no_meta_skips_plugin():
    """Factory with no meta produces a parser without the plugin."""
    factory = ganban_parser_factory(None)
    md = factory()
    texts = _text_tokens(md, "[alice](mailto:alice@example.com)")
    assert texts[0].content == "alice"


def test_factory_creates_working_parser():
    """Factory with meta produces a parser that applies the mailto plugin."""
    meta = Node(users={"Alice": {"emoji": "🎉", "emails": ["alice@example.com"]}})
    factory = ganban_parser_factory(meta)
    md = factory()
    texts = _text_tokens(md, "[alice](mailto:alice@example.com)")
    assert texts[0].content == "🎉 Alice"


def test_factory_with_committers():
    """Factory passes committers through to the plugin."""
    meta = Node()
    committers = ["Charlie Brown <charlie@peanuts.com>"]
    factory = ganban_parser_factory(meta, committers)
    md = factory()
    texts = _text_tokens(md, "[Chuck](mailto:charlie@peanuts.com)")
    assert texts[0].content == f"{emoji_for_email('charlie@peanuts.com')} Charlie Brown"
