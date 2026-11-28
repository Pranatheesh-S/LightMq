import json

from browser.devtools.inspector_bridge import APPLICATION_WORLD, path_literal


def test_application_world_and_path_validation():
    assert APPLICATION_WORLD > 0
    assert json.loads(path_literal("[1, 2, {\"shadow\": true, \"index\": 3}]")) == [1, 2, {"shadow": True, "index": 3}]
    assert json.loads(path_literal("window.alert(1)")) == []
    assert json.loads(path_literal("[true, -1, 999999999, {\"shadow\":true,\"index\":2}]")) == [{"shadow": True, "index": 2}]
