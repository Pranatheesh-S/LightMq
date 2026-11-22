"""Safe Netscape bookmark HTML import and export helpers."""

from __future__ import annotations

from html import escape
from html.parser import HTMLParser
from pathlib import Path
from datetime import datetime, timezone


class _NetscapeParser(HTMLParser):
    """Parse the nested DL/H3/A structure used by browser bookmark exports."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.nodes: list[dict[str, object]] = []
        self._stack: list[list[dict[str, object]]] = [self.nodes]
        self._pending_folder: dict[str, object] | None = None
        self._active: tuple[str, dict[str, object]] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key.upper(): value for key, value in attrs}
        if tag.upper() == "H3":
            self._active = ("folder", {"type":"folder", "title":"", "children":[], "created_at":values.get("ADD_DATE", ""), "updated_at":values.get("LAST_MODIFIED", "")})
        elif tag.upper() == "A":
            self._active = ("bookmark", {"type":"bookmark", "title":"", "url":values.get("HREF", ""), "created_at":values.get("ADD_DATE", ""), "updated_at":values.get("LAST_MODIFIED", "")})
        elif tag.upper() == "DL" and self._pending_folder is not None:
            children=self._pending_folder["children"]
            assert isinstance(children,list)
            self._stack.append(children)
            self._pending_folder=None

    def handle_endtag(self, tag: str) -> None:
        if tag.upper() in ("H3","A") and self._active is not None:
            kind,node=self._active; self._active=None
            if kind=="folder":
                self._stack[-1].append(node); self._pending_folder=node
            else: self._stack[-1].append(node)
        elif tag.upper()=="DL" and len(self._stack)>1:
            self._stack.pop()

    def handle_data(self, data: str) -> None:
        if self._active is not None:
            self._active[1]["title"] = str(self._active[1].get("title", "")) + data


def parse_netscape_html(source: str) -> list[dict[str, object]]:
    """Parse Netscape bookmark HTML without executing or rendering its contents."""
    parser=_NetscapeParser()
    parser.feed(source)
    parser.close()
    return parser.nodes


def import_netscape_file(path: Path) -> list[dict[str, object]]:
    """Read a bookmark export as UTF-8 with replacement for malformed bytes."""
    return parse_netscape_html(path.read_text(encoding="utf-8-sig", errors="replace"))


def _render(nodes: list[dict[str, object]], depth: int = 0) -> list[str]:
    output: list[str]=[]
    indent="    "*depth
    for node in nodes:
        title=escape(str(node.get("title") or ""), quote=True)
        def date_attribute(field:str,attribute:str)->str:
            raw_date=str(node.get(field) or "")
            try:
                if raw_date.isdigit():timestamp=int(raw_date)
                else:
                    parsed=datetime.fromisoformat(raw_date.replace("Z","+00:00"))
                    timestamp=int((parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)).timestamp())
                return f' {attribute}="{timestamp}"'
            except (ValueError,OverflowError):return ""
        metadata=date_attribute("created_at","ADD_DATE")+date_attribute("updated_at","LAST_MODIFIED")
        if node.get("type")=="folder":
            output.extend([f"{indent}<DT><H3{metadata}>{title}</H3>",f"{indent}<DL><p>"])
            children=node.get("children",[])
            if isinstance(children,list): output.extend(_render(children,depth+1))
            output.append(f"{indent}</DL><p>")
        else:
            url=escape(str(node.get("url") or ""), quote=True)
            output.append(f"{indent}<DT><A HREF=\"{url}\"{metadata}>{title}</A>")
    return output


def export_netscape_html(nodes: list[dict[str, object]]) -> str:
    """Serialize a tree into interoperable Netscape-format bookmark HTML."""
    return "<!DOCTYPE NETSCAPE-Bookmark-file-1>\n<META HTTP-EQUIV=\"Content-Type\" CONTENT=\"text/html; charset=UTF-8\">\n<TITLE>Bookmarks</TITLE>\n<H1>Bookmarks</H1>\n<DL><p>\n"+"\n".join(_render(nodes,1))+"\n</DL><p>\n"


def export_netscape_file(path: Path, nodes: list[dict[str, object]]) -> None:
    """Write export atomically so an interrupted save cannot leave a partial file."""
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+".tmp")
    temporary.write_text(export_netscape_html(nodes),encoding="utf-8",newline="\n")
    temporary.replace(path)
