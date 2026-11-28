"""Exercise picker selection and CSS mutation against a synthetic local page."""

import sys

from PySide6.QtCore import QEventLoop, QTimer, QUrl
from PySide6.QtWidgets import QApplication

from browser.devtools.inspector_bridge import RESOLVE_HELPER, run_inspector_data, run_inspector_js
from browser.ui.main_window import MainWindow

app = QApplication.instance() or QApplication(sys.argv)


def wait_for(callback_start, timeout_ms=8000):
    loop = QEventLoop()
    timer = QTimer(); timer.setSingleShot(True); timer.timeout.connect(loop.quit)
    callback_start(loop.quit); timer.start(timeout_ms); loop.exec(); timer.stop()


def wait_until_js(page, source):
    loop = QEventLoop(); timer = QTimer(); timer.setSingleShot(True); timer.timeout.connect(loop.quit)
    reached = []
    def query():
        def received(value):
            if value:
                reached.append(True); loop.quit()
            else:
                QTimer.singleShot(40, query)
        run_inspector_js(page, source, received)
    query(); timer.start(8000); loop.exec(); timer.stop()
    assert reached, f"timed out waiting for JavaScript condition: {source}"


def wait_until(predicate, timeout_ms=8000):
    loop = QEventLoop(); timer = QTimer(); timer.setSingleShot(True); timer.timeout.connect(loop.quit)
    poll = QTimer(); poll.setInterval(20); poll.timeout.connect(lambda: loop.quit() if predicate() else None)
    poll.start(); timer.start(timeout_ms); loop.exec(); poll.stop(); timer.stop()
    assert predicate(), "timed out waiting for inspector state"


def test_picker_returns_redacted_html_and_computed_css():
    window = MainWindow(initial_url="about:blank", is_private=True)
    window.show()
    view = window.web_view
    view.setHtml("""<!doctype html><html><head><style>.primary{background-color:blue;color:white;padding:12px;--test-url:url(https://fixture.invalid/image?token=css-secret)}</style></head><body><div id='wrapper'><button id='login-button' class='primary'>Login</button></div><input id='pw' type='password' value='secret-value'><textarea id='private-note'>textarea-secret</textarea><a id='secret-link' href='/download?token=html-secret' data-access-token='attribute-secret'>Link</a></body></html>""", QUrl("https://fixture.invalid/"))
    wait_until_js(view.page(), "!!document.querySelector('#login-button')")
    probe = []
    wait_for(lambda done: run_inspector_js(view.page(), "1+2", lambda value: (probe.append(value), done())))
    assert probe == [3], f"isolated JavaScript callback returned {probe!r}"

    dom = window.devtools_panel.dom
    selected = []
    dom.element_selected.connect(lambda path, data: selected.append((path, data)) if data else None)
    dom.set_page(view.page())
    dom.start_picker()
    run_inspector_js(view.page(), "(()=>{const b=document.querySelector('#login-button'),r=b.getBoundingClientRect();b.dispatchEvent(new PointerEvent('pointermove',{bubbles:true,clientX:r.left+2,clientY:r.top+2}))})()")
    wait_until_js(view.page(), "document.getElementById('__lightmq_inspector_overlay')?.style.display==='block'")
    run_inspector_js(view.page(), "(()=>{const b=document.querySelector('#login-button'),r=b.getBoundingClientRect();b.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,clientX:r.left+2,clientY:r.top+2}))})()")
    loop = QEventLoop(); timer = QTimer(); timer.setSingleShot(True); timer.timeout.connect(loop.quit)
    poll = QTimer(); poll.setInterval(10)
    poll.timeout.connect(lambda: loop.quit() if dom._selected_data else None)
    poll.start(); timer.start(8000); loop.exec(); poll.stop(); timer.stop()
    data = dom._selected_data
    assert "tag" in data, f"{dom.status.text()} :: {data} :: {selected}"
    assert data["tag"] == "BUTTON"
    assert data["id"] == "login-button"
    assert data["class"] == "primary"
    assert "Login" in data["text"]
    assert "secret-value" not in data["outer"]
    assert "html-secret" not in data["outer"]
    assert "attribute-secret" not in data["outer"]
    assert all("css-secret" not in str(value) for value in data["css"].values())
    assert "background-color" in data["css"]
    assert data["css"]["background-color"] == "rgb(0, 0, 255)"
    assert data["css"]["color"] == "rgb(255, 255, 255)"
    assert data["css"]["padding"] == "12px"
    assert "addEventListener()" in window.devtools_panel.javascript.limitation.text()
    assert "No event listeners or source locations are inferred" in window.devtools_panel.javascript.limitation.text()
    assert window.devtools_panel.css.box_diagram.objectName() == "boxModelDiagram"

    dom.select_path([1])
    wait_until(lambda: dom._selected_data.get("tag") == "BODY")
    assert "textarea-secret" not in dom._selected_data["text"]
    assert "textarea-secret" not in dom._selected_data["outer"]
    dom.select_path([1, 0, 0])
    wait_until(lambda: dom._selected_data.get("id") == "login-button")

    dom.select_parent()
    wait_until(lambda: dom._selected_data.get("id") == "wrapper")
    wait_until_js(view.page(), "document.getElementById('__lightmq_inspector_overlay')?.firstChild?.textContent.includes('div#wrapper')")
    dom.select_first_child()
    wait_until(lambda: dom._selected_data.get("id") == "login-button")
    dom.copy_detail("selector")
    assert QApplication.clipboard().text() == "button#login-button"

    dom.text_edit.setText("Sign in"); dom.apply_text_edit()
    wait_until_js(view.page(), "document.querySelector('#login-button')?.textContent==='Sign in'")
    dom.reset_html_edits()
    wait_until_js(view.page(), "document.querySelector('#login-button')?.textContent==='Login'")

    css = window.devtools_panel.css
    css.set_selection(dom._selected_path, data)
    css.property_name.setText("background-color"); css.property_value.setText("red")
    css.apply_edit()
    result = []
    wait_for(lambda done: run_inspector_js(view.page(), f"{RESOLVE_HELPER}getComputedStyle(resolvePath([1,0,0])).backgroundColor", lambda value: (result.append(value), done())))
    assert result and result[0] == "rgb(255, 0, 0)"
    css.undo_edit()
    state = []
    wait_for(lambda done: run_inspector_data(view.page(), f"(()=>{{{RESOLVE_HELPER}const e=resolvePath([1,0,0]);return {{color:getComputedStyle(e).backgroundColor,inline:e.style.getPropertyValue('background-color'),edits:window.__lightmqCssEdits?.length||0,redo:window.__lightmqCssRedo?.length||0}}}})()", lambda value: (state.append(value), done())))
    assert state and state[0]["color"] == "rgb(0, 0, 255)", f"undo state: {state} / {css.status.text()}"
    css.redo_edit()
    state = []
    wait_for(lambda done: run_inspector_data(view.page(), f"(()=>{{{RESOLVE_HELPER}const e=resolvePath([1,0,0]);return {{color:getComputedStyle(e).backgroundColor,inline:e.style.getPropertyValue('background-color'),edits:window.__lightmqCssEdits?.length||0,redo:window.__lightmqCssRedo?.length||0}}}})()", lambda value: (state.append(value), done())))
    assert state and state[0]["color"] == "rgb(255, 0, 0)", f"redo state: {state} / {css.status.text()}"
    css.reset_edits()
    state = []
    wait_for(lambda done: run_inspector_data(view.page(), f"(()=>{{{RESOLVE_HELPER}const e=resolvePath([1,0,0]);return {{color:getComputedStyle(e).backgroundColor,inline:e.style.getPropertyValue('background-color'),edits:window.__lightmqCssEdits?.length||0,redo:window.__lightmqCssRedo?.length||0}}}})()", lambda value: (state.append(value), done())))
    assert state and state[0]["color"] == "rgb(0, 0, 255)", f"reset state: {state} / {css.status.text()}"

    dom.start_picker()
    delay = QEventLoop(); QTimer.singleShot(350, delay.quit); delay.exec()
    assert dom.picker_active, "restarting the picker must not reuse the previous selected path"
    run_inspector_js(view.page(), "document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true,cancelable:true}))")
    wait_until(lambda: not dom.picker_active)
    wait_until_js(view.page(), "!document.getElementById('__lightmq_inspector_overlay')")

    dom.select_path([1, 0, 0])
    wait_until(lambda: dom._selected_data.get("id") == "login-button")
    css.property_name.setText("background-color"); css.property_value.setText("red"); css.apply_edit()
    state = []
    wait_for(lambda done: run_inspector_data(view.page(), f"(()=>{{{RESOLVE_HELPER}const e=resolvePath([1,0,0]);return {{color:getComputedStyle(e).backgroundColor,inline:e.style.getPropertyValue('background-color'),edits:window.__lightmqCssEdits?.length||0}}}})()", lambda value: (state.append(value), done())))
    assert state and state[0]["color"] == "rgb(255, 0, 0)", f"post-picker CSS edit: {state} / {css.status.text()} / {css.path}"
    window.devtools_manager.close()
    state = []
    wait_for(lambda done: run_inspector_data(view.page(), f"(()=>{{{RESOLVE_HELPER}const e=resolvePath([1,0,0]);return {{color:getComputedStyle(e).backgroundColor,overlay:!!document.getElementById('__lightmq_inspector_overlay'),edits:window.__lightmqCssEdits?.length||0}}}})()", lambda value: (state.append(value), done())))
    assert state and state[0]["color"] == "rgb(0, 0, 255)" and not state[0]["overlay"], f"close cleanup: {state} / {css.status.text()}"
    window.close()
