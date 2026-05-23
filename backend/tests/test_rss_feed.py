"""Tests for RSS feed parsing — Phase 4 Track F.

Covers: feedparser integration with mock feed data.
"""
import pytest

import feedparser


SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <link>https://example.com</link>
    <description>A test RSS feed</description>
    <item>
      <title>Article One</title>
      <link>https://example.com/article-1</link>
      <guid>https://example.com/article-1</guid>
      <pubDate>Mon, 15 Jan 2025 10:00:00 GMT</pubDate>
      <description>First article description.</description>
    </item>
    <item>
      <title>Article Two</title>
      <link>https://example.com/article-2</link>
      <guid>https://example.com/article-2</guid>
      <pubDate>Tue, 16 Jan 2025 10:00:00 GMT</pubDate>
      <description>Second article description.</description>
    </item>
  </channel>
</rss>
"""

SAMPLE_ATOM = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Atom Feed</title>
  <entry>
    <title>Entry One</title>
    <link href="https://example.com/entry-1"/>
    <id>urn:uuid:entry-1</id>
    <summary>Summary of entry one.</summary>
  </entry>
</feed>
"""


class TestFeedParserRSS:
    """Test feedparser with RSS 2.0 format."""

    def test_parse_title(self):
        feed = feedparser.parse(SAMPLE_RSS)
        assert feed.feed.title == "Test Feed"

    def test_parse_items_count(self):
        feed = feedparser.parse(SAMPLE_RSS)
        assert len(feed.entries) == 2

    def test_item_has_title(self):
        feed = feedparser.parse(SAMPLE_RSS)
        assert feed.entries[0].title == "Article One"

    def test_item_has_link(self):
        feed = feedparser.parse(SAMPLE_RSS)
        assert feed.entries[0].link == "https://example.com/article-1"

    def test_item_has_guid(self):
        feed = feedparser.parse(SAMPLE_RSS)
        assert feed.entries[0].id == "https://example.com/article-1"

    def test_empty_feed(self):
        empty_rss = """<?xml version="1.0"?><rss version="2.0"><channel><title>Empty</title></channel></rss>"""
        feed = feedparser.parse(empty_rss)
        assert len(feed.entries) == 0


class TestFeedParserAtom:
    """Test feedparser with Atom format."""

    def test_parse_atom_title(self):
        feed = feedparser.parse(SAMPLE_ATOM)
        assert feed.feed.title == "Atom Feed"

    def test_parse_atom_entries(self):
        feed = feedparser.parse(SAMPLE_ATOM)
        assert len(feed.entries) == 1
        assert feed.entries[0].title == "Entry One"


class TestSeenItemDedup:
    """Test the seen-item deduplication logic used in RSS polling."""

    def test_new_items_detected(self):
        feed = feedparser.parse(SAMPLE_RSS)
        seen_guids: set[str] = set()
        new_items = [e for e in feed.entries if e.id not in seen_guids]
        assert len(new_items) == 2

    def test_duplicate_items_skipped(self):
        feed = feedparser.parse(SAMPLE_RSS)
        seen_guids = {"https://example.com/article-1"}
        new_items = [e for e in feed.entries if e.id not in seen_guids]
        assert len(new_items) == 1
        assert new_items[0].title == "Article Two"

    def test_all_seen_returns_empty(self):
        feed = feedparser.parse(SAMPLE_RSS)
        seen_guids = {e.id for e in feed.entries}
        new_items = [e for e in feed.entries if e.id not in seen_guids]
        assert len(new_items) == 0
