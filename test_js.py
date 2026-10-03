from qtpy.QtWidgets import QApplication
from qtwebview2 import QtWebView2Widget
from qtpy.QtCore import QTimer
import sys

app = QApplication([])
w = QtWebView2Widget()
w.load_html('<html><body style="height: 1500px;">test</body></html>')
w.show()

def evaluate():
    try:
        core = w._webview.CoreWebView2
        task = core.ExecuteScriptAsync("document.documentElement.scrollHeight.toString()")
        def on_comp(t):
            print("SCRIPT RES:", t.Result)
            app.quit()
        import System
        action = System.Action[System.Threading.Tasks.Task[System.String]](on_comp)
        task.ContinueWith(action)
    except Exception as e:
        print("ERR:", e)
        app.quit()

QTimer.singleShot(2000, evaluate)
app.exec_()
