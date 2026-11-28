"""LightMq browser package root."""

# Qt requires QRC access flags to be registered before QApplication.
from browser.webengine.scheme import register_webchannel_resource_access

register_webchannel_resource_access()
