"""Safe, isolated-world JavaScript bridge helpers for page inspection."""

from __future__ import annotations

import json
import logging
from typing import Any, Callable

from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineScript

APPLICATION_WORLD = int(QWebEngineScript.ScriptWorldId.ApplicationWorld.value)
MAX_INSPECTED_HTML = 20_000
MAX_INSPECTED_TEXT = 4_000
logger = logging.getLogger(__name__)


def run_inspector_js(
    page: QWebEnginePage,
    source: str,
    callback: Callable[[Any], None] | None = None,
) -> None:
    """Run inspector code in Qt's isolated ApplicationWorld, if the page lives."""
    try:
        if callback is None:
            page.runJavaScript(source, APPLICATION_WORLD)
        else:
            page.runJavaScript(source, APPLICATION_WORLD, callback)
    except (RuntimeError, TypeError):
        # Old bindings may omit the world overload. Avoid silently falling back
        # into the website's MainWorld: report unavailable instead.
        if callback is not None:
            callback(None)


def path_literal(path: str | list[Any]) -> str:
    """Return a bounded JSON path literal, never executable input."""
    if isinstance(path, str):
        try:
            parsed = json.loads(path)
        except (TypeError, json.JSONDecodeError):
            parsed = []
    else:
        parsed = path
    if not isinstance(parsed, list) or len(parsed) > 512:
        parsed = []
    safe: list[int | dict[str, int]] = []
    for part in parsed:
        if isinstance(part, int) and not isinstance(part, bool) and 0 <= part < 1_000_000:
            safe.append(part)
        elif isinstance(part, dict) and part.get("shadow") is True:
            index = part.get("index")
            if isinstance(index, int) and 0 <= index < 1_000_000:
                safe.append({"shadow": True, "index": index})
    return json.dumps(safe)


def run_inspector_data(
    page: QWebEnginePage,
    source: str,
    callback: Callable[[Any], None],
) -> None:
    """Return structured JS data through JSON to avoid QVariant object loss."""
    wrapped = f"(()=>{{try{{const value=({source});return JSON.stringify(value)}}catch(error){{return JSON.stringify({{__lightmq_error:String(error).slice(0,500)}})}}}})()"
    def decode(raw: Any) -> None:
        if not isinstance(raw, str) or len(raw) > 1_500_000:
            callback(None)
            return
        try:
            callback(json.loads(raw))
        except (TypeError, json.JSONDecodeError):
            logger.debug("Inspector JavaScript returned invalid JSON")
            callback(None)
    run_inspector_js(page, wrapped, decode)


RESOLVE_HELPER = """const resolvePath=p=>{let n=document.documentElement;for(const part of p||[]){if(!n)return null;if(typeof part==='number')n=n.childNodes[part];else if(part&&part.shadow)n=n.shadowRoot?.childNodes[part.index]||null}return n instanceof Element?n:null};"""

SAFE_CSS_HELPER = r"""const lightmqSensitive=/(pass(word)?|secret|token|auth|cookie|session|credit.?card|cvv|security.?code|(^|[_-])code([_-]|$))/i;const lightmqSafeUrl=v=>{try{const u=new URL(v,location.href);u.username='';u.password='';for(const k of [...u.searchParams.keys()])if(lightmqSensitive.test(k))u.searchParams.delete(k);return u.href.slice(0,1200)}catch{return String(v).slice(0,1200)}};const lightmqSafeCss=v=>String(v).replace(/url\((['"]?)(.*?)\1\)/gi,(_,q,u)=>'url("'+lightmqSafeUrl(u)+'")');"""

SELECTED_HIGHLIGHT_SCRIPT = r"""(()=>{window.__lightmqInspectorStop?.(true);__RESOLVE__const e=resolvePath(__PATH__);if(!e)return false;let o=document.getElementById('__lightmq_inspector_overlay');if(!o){o=document.createElement('div');o.id='__lightmq_inspector_overlay';o.style.cssText='position:fixed;z-index:2147483647;pointer-events:none;box-sizing:border-box;border:2px solid #4285f4;background:rgba(66,133,244,.12);';const l=document.createElement('div');l.style.cssText='position:absolute;left:-2px;top:-25px;background:#1a73e8;color:white;font:12px sans-serif;padding:3px 6px;white-space:nowrap;max-width:60vw;overflow:hidden;text-overflow:ellipsis';o.append(l);(document.documentElement||document).append(o)}const refresh=()=>{if(!e.isConnected){o.remove();return}const r=e.getBoundingClientRect();o.style.display='block';o.style.left=Math.max(0,r.left)+'px';o.style.top=Math.max(0,r.top)+'px';o.style.width=Math.max(0,r.width)+'px';o.style.height=Math.max(0,r.height)+'px'};refresh();let label=e.tagName.toLowerCase();if(e.id)label+='#'+e.id.slice(0,80);if(e.classList?.length)label+='.'+[...e.classList].slice(0,3).join('.');o.firstChild.textContent=label+'  '+Math.round(e.getBoundingClientRect().width)+' × '+Math.round(e.getBoundingClientRect().height)+' px';window.addEventListener('scroll',refresh,true);window.addEventListener('resize',refresh,true);window.__lightmqInspectorStop=()=>{window.removeEventListener('scroll',refresh,true);window.removeEventListener('resize',refresh,true);o.remove();window.__lightmqInspectorStop=null};return true})()"""

DETAILS_SCRIPT = r"""(()=>{__RESOLVE__const e=resolvePath(__PATH__);if(!e||!e.isConnected)return {detached:true};const sensitive=/(pass(word)?|secret|token|auth|cookie|session|credit.?card|cvv|security.?code|(^|[_-])code([_-]|$))/i;const safeUrl=v=>{try{const u=new URL(v,location.href);u.username='';u.password='';for(const k of [...u.searchParams.keys()])if(sensitive.test(k))u.searchParams.delete(k);return u.href.slice(0,1200)}catch{return String(v).slice(0,1200)}};const safeCss=v=>String(v).replace(/url\((['"]?)(.*?)\1\)/gi,(_,q,u)=>'url("'+safeUrl(u)+'")');const cleanAttrs=node=>{const a={};if(!node.attributes)return a;for(const x of Array.from(node.attributes).slice(0,40)){if(x.name==='value'||sensitive.test(x.name)||sensitive.test(x.value))continue;let value=x.value;if(['href','src','action','formaction'].includes(x.name.toLowerCase()))value=safeUrl(value);a[x.name]=value.slice(0,500)}return a};const clone=e.cloneNode(true);for(const c of [clone,...clone.querySelectorAll('input,textarea,select,option')]){c.removeAttribute?.('value');c.removeAttribute?.('selected');if(c.tagName==='TEXTAREA')c.textContent='';if(c.tagName==='INPUT'&&['password','hidden'].includes((c.type||'').toLowerCase()))c.remove()}for(const c of [clone,...clone.querySelectorAll('*')])for(const a of [...(c.attributes||[])]){if(a.name==='value'||sensitive.test(a.name)||sensitive.test(a.value))c.removeAttribute(a.name);else if(['href','src','action','formaction'].includes(a.name.toLowerCase()))c.setAttribute(a.name,safeUrl(a.value))}const style=getComputedStyle(e),css={};for(let i=0;i<style.length&&i<400;i++){const k=style[i];css[k]=safeCss(style.getPropertyValue(k)).slice(0,240)}for(const k of ['margin','padding','border','border-radius'])css[k]=safeCss(style.getPropertyValue(k)).slice(0,240);const r=e.getBoundingClientRect(),px=v=>Number.parseFloat(v)||0;const box={width:r.width,height:r.height,margin:{top:px(style.marginTop),right:px(style.marginRight),bottom:px(style.marginBottom),left:px(style.marginLeft)},border:{top:px(style.borderTopWidth),right:px(style.borderRightWidth),bottom:px(style.borderBottomWidth),left:px(style.borderLeftWidth)},padding:{top:px(style.paddingTop),right:px(style.paddingRight),bottom:px(style.paddingBottom),left:px(style.paddingLeft)}};let selector=e.tagName.toLowerCase();if(e.id)selector+='#'+CSS.escape(e.id);else if(e.classList?.length)selector+='.'+[...e.classList].slice(0,4).map(CSS.escape).join('.');let unique=false;try{unique=document.querySelectorAll(selector).length===1}catch{}let xpath='';for(let n=e;n&&n.nodeType===1;n=n.parentElement){let i=1;for(let s=n.previousElementSibling;s;s=s.previousElementSibling)if(s.tagName===n.tagName)i++;xpath='/'+n.tagName.toLowerCase()+'['+i+']'+xpath}const inline={};for(const a of Array.from(e.attributes||[]))if(/^on[a-z]+$/i.test(a.name)){let code=a.value.slice(0,500);code=code.replace(/((?:api[_-]?key|token|password|secret|auth|cookie)\s*[:=]\s*['"])[^'"]*(['"])/gi,'$1[redacted]$2');inline[a.name]=code}const children=Array.from(e.children).slice(0,40).map(c=>({tag:c.tagName,id:c.id||'',class:String(c.getAttribute('class')||'').slice(0,200)}));const parent=e.parentElement?{tag: e.parentElement.tagName,id:e.parentElement.id||'',class:String(e.parentElement.getAttribute('class')||'').slice(0,200)}:null;const control=/^(INPUT|TEXTAREA|SELECT|OPTION)$/i.test(e.tagName);const text=control?'[form control text omitted]':String(clone.textContent||'').trim().slice(0,4000);const first=e.shadowRoot?.firstElementChild||e.children[0]||null;const firstChildPath=first?__PATH__.concat(first.getRootNode() instanceof ShadowRoot?{shadow:true,index:Array.prototype.indexOf.call(first.getRootNode().childNodes,first)}:Array.prototype.indexOf.call(e.childNodes,first)):null;return {tag:e.tagName,id:e.id||'',class:String(e.getAttribute('class')||''),attrs:cleanAttrs(e),text,outer:clone.outerHTML.slice(0,20000),inner:clone.innerHTML.slice(0,20000),css,box,path:__PATH__,firstChildPath,selector,selectorUnique:unique,xpath,parent,children,inline,frame:window!==window.top?'iframe':'top-level',shadow:!!e.getRootNode()?.host,openShadow:!!e.shadowRoot}})()"""

PICKER_START_SCRIPT = r"""(()=>{window.__lightmqInspectorStop?.(true);window.__lightmqPickedPath=null;let overlay=document.getElementById('__lightmq_inspector_overlay');if(!overlay){overlay=document.createElement('div');overlay.id='__lightmq_inspector_overlay';overlay.style.cssText='position:fixed;z-index:2147483647;pointer-events:none;display:none;box-sizing:border-box;border:2px solid #4285f4;background:rgba(66,133,244,.12);';const label=document.createElement('div');label.style.cssText='position:absolute;left:-2px;top:-25px;background:#1a73e8;color:white;font:12px sans-serif;padding:3px 6px;white-space:nowrap;max-width:60vw;overflow:hidden;text-overflow:ellipsis';label.className='lightmq-label';overlay.append(label);(document.documentElement||document).append(overlay)}let last=null,frame=0;const pathOf=e=>{const out=[];let n=e;while(n&&n!==document.documentElement){const p=n.parentNode;if(p instanceof ShadowRoot){out.unshift({shadow:true,index:Array.prototype.indexOf.call(p.childNodes,n)});n=p.host}else{if(!p)break;out.unshift(Array.prototype.indexOf.call(p.childNodes,n));n=p}}return out};const describe=e=>{let s=e.tagName.toLowerCase();if(e.id)s+='#'+e.id.slice(0,80);if(e.classList?.length)s+='.'+[...e.classList].slice(0,3).join('.');return s};const move=e=>{if(frame)return;frame=requestAnimationFrame(()=>{frame=0;const t=document.elementFromPoint(e.clientX,e.clientY);if(!t||t===overlay||overlay.contains(t)||t===last)return;last=t;const r=t.getBoundingClientRect();overlay.style.display='block';overlay.style.left=Math.max(0,r.left)+'px';overlay.style.top=Math.max(0,r.top)+'px';overlay.style.width=Math.max(0,r.width)+'px';overlay.style.height=Math.max(0,r.height)+'px';overlay.firstChild.textContent=describe(t)+'  '+Math.round(r.width)+' × '+Math.round(r.height)+' px'})};const click=e=>{const t=document.elementFromPoint(e.clientX,e.clientY);if(!t||t===overlay||overlay.contains(t))return;e.preventDefault();e.stopPropagation();e.stopImmediatePropagation();window.__lightmqPickedPath=pathOf(t);stop(false)};const key=e=>{if(e.key==='Escape'){e.preventDefault();window.__lightmqPickedPath={cancelled:true};stop(true)}};function stop(removeOverlay){document.removeEventListener('pointermove',move,true);document.removeEventListener('click',click,true);document.removeEventListener('keydown',key,true);window.removeEventListener('scroll',refresh,true);window.removeEventListener('resize',refresh,true);if(frame)cancelAnimationFrame(frame);frame=0;if(removeOverlay){overlay.remove();window.__lightmqInspectorStop=null}else{window.__lightmqInspectorStop=()=>{overlay.remove();window.__lightmqInspectorStop=null}}return true}function refresh(){if(last){const r=last.getBoundingClientRect();overlay.style.left=r.left+'px';overlay.style.top=r.top+'px';overlay.style.width=r.width+'px';overlay.style.height=r.height+'px'}}window.__lightmqInspectorStop=stop;document.addEventListener('pointermove',move,true);document.addEventListener('click',click,true);document.addEventListener('keydown',key,true);window.addEventListener('scroll',refresh,true);window.addEventListener('resize',refresh,true);return true})()"""

