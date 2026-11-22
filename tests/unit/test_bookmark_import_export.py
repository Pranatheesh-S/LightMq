"""Netscape bookmark HTML import/export round-trip tests."""

from browser.features.bookmarks.bookmark_import_export import export_netscape_html,parse_netscape_html


def test_nested_bookmark_html_roundtrip_and_escaping():
    tree=[{"type":"folder","title":"Dev & Tools","children":[
        {"type":"bookmark","title":"Python <Docs>","url":"https://docs.python.org/?a=1&b=2"},
        {"type":"folder","title":"Qt","children":[{"type":"bookmark","title":"Qt Docs","url":"https://doc.qt.io/"}]},
    ]}]
    html=export_netscape_html(tree)
    parsed=parse_netscape_html(html)
    assert parsed[0]["title"]==tree[0]["title"]
    assert parsed[0]["children"][0]["title"]==tree[0]["children"][0]["title"]
    assert parsed[0]["children"][0]["url"]==tree[0]["children"][0]["url"]
    assert parsed[0]["children"][1]["children"][0]["url"]=="https://doc.qt.io/"


def test_import_ignores_unsupported_schemes():
    parsed=parse_netscape_html('<DL><p><DT><A HREF="javascript:alert(1)">unsafe</A></DL>')
    assert parsed[0]["url"]=="javascript:alert(1)"
