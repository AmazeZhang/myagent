from test_web import WebBrowserTool
t = WebBrowserTool()
print(t.call('action=go_to_url url="https://example.com" session_id=testsync'))