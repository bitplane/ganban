"""Tests for the markdown-it plugins."""

from markdown_it import MarkdownIt

from ganban.model.node import ListNode, Node
from ganban.ui.emoji import emoji_for_email
from ganban.ui.markdown import card_ref_plugin, ganban_parser_factory, mailto_display_plugin


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


def _make_board(*cards):
    """Build a board with numbered cards. Each card is a (id, title) tuple."""
    board = Node()
    cards_ln = ListNode()
    for card_id, title in cards:
        sections = ListNode()
        sections[title] = ""
        cards_ln[card_id] = Node(sections=sections, meta={}, file_path=f".all/{card_id}.md")
    board.cards = cards_ln
    return board


# --- mailto_display_plugin tests ---


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
    """Factory with no board produces a parser without plugins."""
    factory = ganban_parser_factory(None)
    md = factory()
    texts = _text_tokens(md, "[alice](mailto:alice@example.com)")
    assert texts[0].content == "alice"


def test_factory_creates_working_parser():
    """Factory with board produces a parser that applies the mailto plugin."""
    board = Node(meta={"users": {"Alice": {"emoji": "🎉", "emails": ["alice@example.com"]}}})
    board.cards = ListNode()
    factory = ganban_parser_factory(board)
    md = factory()
    texts = _text_tokens(md, "[alice](mailto:alice@example.com)")
    assert texts[0].content == "🎉 Alice"


def test_factory_with_committers():
    """Factory passes committers through to the plugin."""
    board = Node(meta={}, git={"committers": ["Charlie Brown <charlie@peanuts.com>"]})
    board.cards = ListNode()
    factory = ganban_parser_factory(board)
    md = factory()
    texts = _text_tokens(md, "[Chuck](mailto:charlie@peanuts.com)")
    assert texts[0].content == f"{emoji_for_email('charlie@peanuts.com')} Charlie Brown"


# --- card_ref_plugin tests ---


def test_card_ref_replaced():
    """#NNN in text is replaced with a link showing card title."""
    board = _make_board(("038", "ID parser"))
    md = MarkdownIt("gfm-like")
    md.use(card_ref_plugin, board)
    children = _inline_children(md, "see #38 for details")
    types = [c.type for c in children]
    assert types == ["text", "link_open", "text", "link_close", "text"]
    assert children[0].content == "see "
    assert children[1].attrGet("href") == "card:038"
    assert children[2].content == "#038 ID parser"
    assert children[4].content == " for details"


def test_card_ref_multiple():
    """Multiple #NNN refs in one line are all replaced."""
    board = _make_board(("001", "First"), ("002", "Second"))
    md = MarkdownIt("gfm-like")
    md.use(card_ref_plugin, board)
    children = _inline_children(md, "#1 and #2")
    link_opens = [c for c in children if c.type == "link_open"]
    assert len(link_opens) == 2
    assert link_opens[0].attrGet("href") == "card:001"
    assert link_opens[1].attrGet("href") == "card:002"


def test_card_ref_missing_card():
    """#NNN where the card doesn't exist is left as plain text."""
    board = _make_board(("001", "First"))
    md = MarkdownIt("gfm-like")
    md.use(card_ref_plugin, board)
    children = _inline_children(md, "see #999")
    texts = [c for c in children if c.type == "text"]
    assert len(texts) == 1
    assert texts[0].content == "see #999"


def test_card_ref_zero_padding():
    """#38 matches card 038 with zero-padding."""
    board = _make_board(("038", "Padded card"))
    md = MarkdownIt("gfm-like")
    md.use(card_ref_plugin, board)
    children = _inline_children(md, "#38")
    link_opens = [c for c in children if c.type == "link_open"]
    assert len(link_opens) == 1
    assert link_opens[0].attrGet("href") == "card:038"
    link_text = [c for c in children if c.type == "text" and c.content.startswith("#")]
    assert link_text[0].content == "#038 Padded card"


def test_card_ref_extra_leading_zeros():
    """#00038 matches card 038 after stripping excess zeros."""
    board = _make_board(("038", "Padded card"))
    md = MarkdownIt("gfm-like")
    md.use(card_ref_plugin, board)
    children = _inline_children(md, "see #00038")
    link_opens = [c for c in children if c.type == "link_open"]
    assert len(link_opens) == 1
    assert link_opens[0].attrGet("href") == "card:038"


def test_card_ref_inside_link_not_processed():
    """#NNN inside an existing link is not double-processed."""
    board = _make_board(("001", "First"))
    md = MarkdownIt("gfm-like")
    md.use(card_ref_plugin, board)
    children = _inline_children(md, "[see #1](https://example.com)")
    # The text inside the link should remain unchanged
    link_texts = [c for c in children if c.type == "text"]
    assert any("see #1" in t.content for t in link_texts)
    # Should not have a nested card link
    link_opens = [c for c in children if c.type == "link_open"]
    assert len(link_opens) == 1
    assert link_opens[0].attrGet("href") == "https://example.com"


def test_card_ref_no_refs_untouched():
    """Text with no refs is untouched."""
    board = _make_board(("001", "First"))
    md = MarkdownIt("gfm-like")
    md.use(card_ref_plugin, board)
    children = _inline_children(md, "just some text")
    assert len(children) == 1
    assert children[0].type == "text"
    assert children[0].content == "just some text"


def test_card_ref_self_reference():
    """A card mentioning its own ID works fine."""
    board = _make_board(("042", "Self ref card"))
    md = MarkdownIt("gfm-like")
    md.use(card_ref_plugin, board)
    children = _inline_children(md, "this is #42")
    link_opens = [c for c in children if c.type == "link_open"]
    assert len(link_opens) == 1
    assert link_opens[0].attrGet("href") == "card:042"


def test_card_ref_factory_integration():
    """Factory produces a parser with card_ref_plugin enabled."""
    board = _make_board(("007", "Bond card"))
    board.meta = {}
    factory = ganban_parser_factory(board)
    md = factory()
    children = _inline_children(md, "see #7")
    link_opens = [c for c in children if c.type == "link_open"]
    assert len(link_opens) == 1
    assert link_opens[0].attrGet("href") == "card:007"
    link_text = [c for c in children if c.type == "text" and c.content.startswith("#")]
    assert link_text[0].content == "#007 Bond card"


def test_card_ref_no_cards():
    """Board with no cards doesn't crash."""
    board = Node()
    md = MarkdownIt("gfm-like")
    md.use(card_ref_plugin, board)
    children = _inline_children(md, "see #1")
    assert len(children) == 1
    assert children[0].content == "see #1"
