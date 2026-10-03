import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QSplitter, QTreeView,
    QTableView, QVBoxLayout, QWidget, QMenuBar, QMenu,
    QMessageBox, QHeaderView, QFileDialog, QLineEdit,
    QPushButton, QHBoxLayout, QLabel
)
from qtwebview2 import QtWebView2Widget
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSortFilterProxyModel
from PyQt6.QtGui import QStandardItemModel, QStandardItem

import config
from account_dialog import AccountDialog
from compose_dialog import ComposeDialog
from imap_client import IMAPClient

try:
    import clr  # type: ignore
    import System  # type: ignore
except ImportError:
    System = None  # type: ignore

class MailFetcherThread(QThread):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, client, folder, limit=50, offset=0):
        super().__init__()
        self.client = client
        self.folder = folder
        self.limit = limit
        self.offset = offset

    def run(self):
        try:
            data = self.client.get_emails(self.folder, limit=self.limit, offset=self.offset)
            data["folder"] = self.folder
            data["offset"] = self.offset
            self.finished.emit(data)
        except Exception as e:
            self.error.emit(str(e))

class MailContentThread(QThread):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, client, folder, email_id):
        super().__init__()
        self.client = client
        self.folder = folder
        self.email_id = email_id

    def run(self):
        try:
            content = self.client.get_email_content(self.folder, self.email_id)
            self.finished.emit(content or {})
        except Exception as e:
            self.error.emit(str(e))

class PyMailWindow(QMainWindow):
    js_eval_completed = pyqtSignal(str, str)
    pdf_export_completed = pyqtSignal(bool, str)
    check_ready_completed = pyqtSignal(str, str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyMail - Email Client")
        self.resize(1024, 768)

        self.conf = config.load_config()
        self.imap_client = None
        self.current_folder = "INBOX"
        self.total_emails = 0

        self.setup_ui()
        self.setup_menu()
        
        self.js_eval_completed.connect(self._do_pdf_export)
        self.pdf_export_completed.connect(self._on_pdf_done)
        self.check_ready_completed.connect(self._on_check_ready)
        
        self.check_ready_attempts = 0
        
        self.export_queue = []
        self.export_dir = ""
        self.is_bulk_exporting = False
        self.current_bulk_filepath = ""
        
        # UI Setup
        self.folder_model = QStandardItemModel()
        self.folder_tree.setModel(self.folder_model)
        
        self.message_model = QStandardItemModel(0, 3)
        self.message_model.setHorizontalHeaderLabels(["Subject", "From", "Date"])
        
        self.proxy_model = QSortFilterProxyModel()
        self.proxy_model.setSourceModel(self.message_model)
        self.proxy_model.setFilterKeyColumn(-1)
        self.proxy_model.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        
        self.message_list.setModel(self.proxy_model)
        self.message_list.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        
        # Connections
        self.folder_tree.selectionModel().selectionChanged.connect(self.on_folder_selected)
        self.message_list.selectionModel().selectionChanged.connect(self.on_message_selected)
        
        self.init_account()

    def setup_ui(self):
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        self.folder_tree = QTreeView()
        self.folder_tree.setHeaderHidden(True)
        self.folder_tree.setEditTriggers(QTreeView.EditTrigger.NoEditTriggers)
        main_splitter.addWidget(self.folder_tree)
        
        right_splitter = QSplitter(Qt.Orientation.Vertical)
        
        search_layout = QHBoxLayout()
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search emails...")
        self.search_bar.textChanged.connect(self.on_search_changed)
        
        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.clicked.connect(self.on_select_all)
        
        self.clear_sel_btn = QPushButton("Clear")
        self.clear_sel_btn.clicked.connect(self.on_clear_selection)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh_current_folder)
        
        search_layout.addWidget(self.search_bar)
        search_layout.addWidget(self.select_all_btn)
        search_layout.addWidget(self.clear_sel_btn)
        search_layout.addWidget(self.refresh_btn)
        
        self.message_list = QTableView()
        self.message_list.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.message_list.setSelectionMode(QTableView.SelectionMode.ExtendedSelection)
        self.message_list.verticalHeader().setVisible(False)
        self.message_list.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        
        # Bottom controls below message list for pagination/status
        bottom_bar_layout = QHBoxLayout()
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #888; font-size: 11px;")
        
        self.load_more_btn = QPushButton("Load More (+50)")
        self.load_more_btn.setEnabled(False)
        self.load_more_btn.clicked.connect(self.load_more_emails)
        
        bottom_bar_layout.addWidget(self.status_label)
        bottom_bar_layout.addStretch()
        bottom_bar_layout.addWidget(self.load_more_btn)

        self.message_viewer = QtWebView2Widget()
        
        list_container = QWidget()
        list_layout = QVBoxLayout(list_container)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.addLayout(search_layout)
        list_layout.addWidget(self.message_list)
        list_layout.addLayout(bottom_bar_layout)
        
        right_splitter.addWidget(list_container)
        right_splitter.addWidget(self.message_viewer)
        right_splitter.setSizes([250, 500])
        
        main_splitter.addWidget(right_splitter)
        main_splitter.setSizes([200, 800])
        
        central_widget = QWidget()
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(main_splitter)
        self.setCentralWidget(central_widget)

    def setup_menu(self):
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("File")
        
        new_msg_action = file_menu.addAction("New Message")
        new_msg_action.setShortcut("Ctrl+N")
        new_msg_action.triggered.connect(self.open_compose)
        
        export_pdf_action = file_menu.addAction("Export Email to PDF")
        export_pdf_action.triggered.connect(self.export_to_pdf)
        
        bulk_export_pdf_action = file_menu.addAction("Bulk Export Selected to PDF...")
        bulk_export_pdf_action.triggered.connect(self.start_bulk_export)
        
        file_menu.addSeparator()
        
        settings_action = file_menu.addAction("Account Settings...")
        settings_action.triggered.connect(self.open_settings)
        
        file_menu.addSeparator()
        
        exit_action = file_menu.addAction("Exit")
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)

    def open_compose(self):
        acc_data = self.conf['accounts'][0] if self.conf['accounts'] else None
        dialog = ComposeDialog(self, acc_data)
        dialog.exec()

    def open_settings(self):
        acc_data = self.conf['accounts'][0] if self.conf['accounts'] else None
        dialog = AccountDialog(self, acc_data)
        if dialog.exec():
            new_data = dialog.get_account_data()
            if self.conf['accounts']:
                self.conf['accounts'][0] = new_data
            else:
                self.conf['accounts'].append(new_data)
            config.save_config(self.conf)
            self.init_account()

    def init_account(self):
        if not self.conf['accounts']:
            self.open_settings()
            return
            
        acc = self.conf['accounts'][0]
        if self.imap_client:
            self.imap_client.disconnect()
            
        self.imap_client = IMAPClient(
            host=acc['imap_host'],
            port=acc['imap_port'],
            username=acc['email'],
            password=acc['password'],
            use_ssl=acc['use_ssl']
        )
        
        success, msg = self.imap_client.connect()
        if success:
            self.load_folders()
        else:
            QMessageBox.critical(self, "Connection Error", f"Failed to connect to IMAP server:\n{msg}")

    def load_folders(self):
        self.folder_model.clear()
        folders = self.imap_client.get_folders()
        
        root = self.folder_model.invisibleRootItem()
        inbox_item = None
        first_selectable_item = None

        for f in folders:
            item = QStandardItem(f['name'])
            item.setData(f['selectable'], Qt.ItemDataRole.UserRole)
            if not f['selectable']:
                item.setSelectable(False)
                item.setEnabled(False)
                font = item.font()
                font.setItalic(True)
                item.setFont(font)
            else:
                if first_selectable_item is None:
                    first_selectable_item = item
                if f['name'].upper() == "INBOX":
                    inbox_item = item
            root.appendRow(item)
            
        self.setWindowTitle(f"PyMail - {self.conf['accounts'][0]['email']}")
        
        target_item = inbox_item or first_selectable_item
        if target_item:
            from PyQt6.QtCore import QItemSelectionModel
            index = self.folder_model.indexFromItem(target_item)
            self.folder_tree.selectionModel().select(index, QItemSelectionModel.SelectionFlag.ClearAndSelect)

    def on_folder_selected(self, selected, deselected):
        indexes = selected.indexes()
        if indexes:
            item = self.folder_model.itemFromIndex(indexes[0])
            if item.data(Qt.ItemDataRole.UserRole) is False:
                return

            self.current_folder = item.text()
            self.message_model.removeRows(0, self.message_model.rowCount())
            self.message_viewer.load_html("")
            self.setWindowTitle(f"PyMail - Loading {self.current_folder}...")
            self.status_label.setText(f"Loading {self.current_folder}...")
            self.load_more_btn.setEnabled(False)
            
            # Fast batch fetch (latest 50 emails)
            self.fetch_thread = MailFetcherThread(self.imap_client, self.current_folder, limit=50, offset=0)
            self.fetch_thread.finished.connect(self.populate_messages)
            self.fetch_thread.error.connect(self.show_error)
            self.fetch_thread.start()

    def refresh_current_folder(self):
        if not self.current_folder:
            return
        self.status_label.setText(f"Refreshing {self.current_folder}...")
        self.load_more_btn.setEnabled(False)
        self.fetch_thread = MailFetcherThread(self.imap_client, self.current_folder, limit=50, offset=0)
        self.fetch_thread.finished.connect(self.populate_messages)
        self.fetch_thread.error.connect(self.show_error)
        self.fetch_thread.start()

    def load_more_emails(self):
        loaded_count = self.message_model.rowCount()
        if loaded_count >= self.total_emails:
            return
        self.load_more_btn.setEnabled(False)
        self.status_label.setText(f"Loading more from {self.current_folder}...")
        self.fetch_thread = MailFetcherThread(self.imap_client, self.current_folder, limit=50, offset=loaded_count)
        self.fetch_thread.finished.connect(self.populate_messages)
        self.fetch_thread.error.connect(self.show_error)
        self.fetch_thread.start()

    def populate_messages(self, data):
        folder = data.get("folder", self.current_folder)
        if folder != self.current_folder:
            return
            
        emails = data.get("emails", [])
        self.total_emails = data.get("total", 0)
        offset = data.get("offset", 0)
        
        if offset == 0:
            self.message_model.removeRows(0, self.message_model.rowCount())
            
        for em in emails:
            sub = QStandardItem(em.get('subject', '(No Subject)'))
            # Store email ID in UserRole of the first column
            sub.setData(em['id'], Qt.ItemDataRole.UserRole) 
            sub.setCheckable(True)
            sub.setCheckState(Qt.CheckState.Unchecked)
            
            frm = QStandardItem(em.get('from', ''))
            dt = QStandardItem(em.get('date', ''))
            
            is_read = em.get('is_read', True)
            if not is_read:
                font = sub.font()
                font.setBold(True)
                sub.setFont(font)
                frm.setFont(font)
                dt.setFont(font)
                
            self.message_model.appendRow([sub, frm, dt])
            
        loaded_count = self.message_model.rowCount()
        acc_email = self.conf['accounts'][0]['email'] if self.conf['accounts'] else ""
        self.setWindowTitle(f"PyMail - {acc_email}")
        self.status_label.setText(f"{self.current_folder}: showing {loaded_count} of {self.total_emails} emails")
        self.load_more_btn.setEnabled(loaded_count < self.total_emails)
        self.refresh_btn.setEnabled(True)

    def on_search_changed(self, text):
        self.proxy_model.setFilterRegularExpression(text)

    def on_select_all(self):
        for row in range(self.proxy_model.rowCount()):
            source_index = self.proxy_model.mapToSource(self.proxy_model.index(row, 0))
            item = self.message_model.itemFromIndex(source_index)
            item.setCheckState(Qt.CheckState.Checked)
            
    def on_clear_selection(self):
        for row in range(self.message_model.rowCount()):
            item = self.message_model.item(row, 0)
            item.setCheckState(Qt.CheckState.Unchecked)

    def on_message_selected(self, selected, deselected):
        if self.is_bulk_exporting:
            return
            
        indexes = self.message_list.selectionModel().selectedRows()
        if indexes:
            row = indexes[0].row()
            source_index = self.proxy_model.mapToSource(self.proxy_model.index(row, 0))
            subject_item = self.message_model.itemFromIndex(source_index)
            
            frm_item = self.message_model.item(source_index.row(), 1)
            dt_item = self.message_model.item(source_index.row(), 2)
            font = subject_item.font()
            font.setBold(False)
            subject_item.setFont(font)
            if frm_item: frm_item.setFont(font)
            if dt_item: dt_item.setFont(font)
            
            email_id = subject_item.data(Qt.ItemDataRole.UserRole)
            
            self.message_viewer.load_html("Loading...")
            
            self.content_thread = MailContentThread(self.imap_client, self.current_folder, email_id)
            self.content_thread.finished.connect(self.display_email_content)
            self.content_thread.error.connect(self.show_error)
            self.content_thread.start()
            
    def display_email_content(self, content):
        headers = content.get("headers", {})
        header_html = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; padding: 20px 20px 0 20px; background-color: #ffffff; max-width: 800px; margin: 0 auto;">
            <h2 style="margin: 0 0 15px 0; font-size: 20px; color: #202124;">{headers.get('subject', '')}</h2>
            <div style="display: flex; align-items: flex-start; margin-bottom: 20px;">
                <div style="width: 40px; height: 40px; border-radius: 50%; background-color: #e0e0e0; display: flex; align-items: center; justify-content: center; margin-right: 15px; flex-shrink: 0; overflow: hidden;">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="#757575">
                        <path d="M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z"/>
                    </svg>
                </div>
                <div style="font-size: 13px; line-height: 1.4; color: #5f6368; width: 100%;">
                    <table style="border-collapse: collapse; width: 100%;">
                        <tr><td style="width: 50px; font-weight: 500;">From</td><td style="color: #202124;">{headers.get('from', '')}</td></tr>
                        <tr><td style="font-weight: 500;">To</td><td>{headers.get('to', '')}</td></tr>
                        {'<tr><td style="font-weight: 500;">Cc</td><td>' + headers.get('cc', '') + '</td></tr>' if headers.get('cc') else ''}
                        <tr><td style="font-weight: 500;">Date</td><td>{headers.get('date', '')}</td></tr>
                    </table>
                </div>
            </div>
        </div>
        """
        
        if content.get("html"):
            body = content["html"]
            if "<body" in body.lower():
                import re
                full_html = re.sub(r'(<body[^>]*>)', r'\1' + header_html, body, flags=re.IGNORECASE)
            else:
                full_html = header_html + body
            
            self.current_html = full_html
            self.message_viewer.load_html(full_html)
        elif content.get("text"):
            text = content["text"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            full_html = header_html + f"<pre style='white-space: pre-wrap; font-family: sans-serif;'>{text}</pre>"
            self.current_html = full_html
            self.message_viewer.load_html(full_html)
        else:
            self.current_html = ""
            self.message_viewer.load_html("No content or failed to parse.")

    def export_to_pdf(self):
        if self.is_bulk_exporting:
            return
            
        if not hasattr(self, 'current_html') or not self.current_html:
            QMessageBox.warning(self, "Export PDF", "No email content to export.")
            return
            
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Email as PDF", "", "PDF Files (*.pdf)")
        if file_path:
            QMessageBox.information(self, "Export PDF", "Email PDF export started. It will be saved shortly.")
            self.trigger_pdf_eval(file_path)

    def trigger_pdf_eval_when_ready(self, filepath):
        try:
            webview = getattr(self.message_viewer, '_webview', None)
            if not webview or not getattr(webview, 'CoreWebView2', None):
                raise Exception("WebView2 core is not initialized yet.")
                
            core_wv2 = webview.CoreWebView2
            
            js_check = """
            (function() {
                var imgs = document.images;
                for (var i = 0; i < imgs.length; i++) {
                    if (!imgs[i].complete) return 'not_ready';
                }
                return 'ready';
            })();
            """
            
            task_check = core_wv2.ExecuteScriptAsync(js_check)
            def on_check(t_check):
                try:
                    res = t_check.Result.strip('"')
                    self.check_ready_completed.emit(res, filepath)
                except Exception as e:
                    self.pdf_export_completed.emit(False, str(e))
            
            action_check = System.Action[System.Threading.Tasks.Task[System.String]](on_check)
            task_check.ContinueWith(action_check)
        except Exception as e:
            self.pdf_export_completed.emit(False, str(e))

    def _on_check_ready(self, status, filepath):
        if status == 'ready' or self.check_ready_attempts >= 10:
            self.check_ready_attempts = 0
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(200, lambda: self.trigger_pdf_eval(filepath))
        else:
            self.check_ready_attempts += 1
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(500, lambda: self.trigger_pdf_eval_when_ready(filepath))

    def trigger_pdf_eval(self, filepath):
        try:
            webview = getattr(self.message_viewer, '_webview', None)
            if not webview or not getattr(webview, 'CoreWebView2', None):
                raise Exception("WebView2 core is not initialized yet.")
            
            core_wv2 = webview.CoreWebView2
            js_code = "Math.max(document.body.scrollHeight, document.documentElement.scrollHeight).toString()"
            task_js = core_wv2.ExecuteScriptAsync(js_code)
            
            def on_js_completed(t_js):
                try:
                    res = t_js.Result.strip('"')
                    self.js_eval_completed.emit(res, filepath)
                except Exception as e:
                    self.pdf_export_completed.emit(False, str(e))
            
            action_js = System.Action[System.Threading.Tasks.Task[System.String]](on_js_completed)
            task_js.ContinueWith(action_js)
        except Exception as e:
            self.pdf_export_completed.emit(False, str(e))

    def _do_pdf_export(self, height_str, file_path):
        try:
            webview = getattr(self.message_viewer, '_webview', None)
            core_wv2 = webview.CoreWebView2
            height_px = float(height_str)
            height_inches = (height_px / 96.0) + 1.0
            
            print_settings = core_wv2.Environment.CreatePrintSettings()
            print_settings.MarginTop = 0
            print_settings.MarginBottom = 0
            print_settings.MarginLeft = 0
            print_settings.MarginRight = 0
            print_settings.ShouldPrintBackgrounds = True
            print_settings.PageHeight = max(11.0, height_inches)
            
            task_pdf = core_wv2.PrintToPdfAsync(file_path, print_settings)
            
            def on_pdf_completed(t_pdf):
                if t_pdf.IsFaulted:
                    self.pdf_export_completed.emit(False, str(t_pdf.Exception))
                else:
                    self.pdf_export_completed.emit(True, "Email successfully exported to PDF.")
                    
            action_pdf = System.Action[System.Threading.Tasks.Task[System.Boolean]](on_pdf_completed)
            task_pdf.ContinueWith(action_pdf)
        except Exception as e:
            self.pdf_export_completed.emit(False, str(e))

    def _on_pdf_done(self, success, msg):
        if not success:
            if not self.is_bulk_exporting:
                QMessageBox.critical(self, "Export PDF Error", msg)
            else:
                print("Bulk export item failed:", msg)
                self.process_next_export()
        else:
            print("Export complete:", msg)
            if self.is_bulk_exporting:
                self.process_next_export()
                
    def start_bulk_export(self):
        self.export_queue = []
        for row in range(self.message_model.rowCount()):
            item = self.message_model.item(row, 0)
            if item.checkState() == Qt.CheckState.Checked:
                email_id = item.data(Qt.ItemDataRole.UserRole)
                self.export_queue.append(email_id)
                
        if not self.export_queue:
            QMessageBox.warning(self, "Bulk Export", "Please check one or more emails to export.")
            return
            
        dir_path = QFileDialog.getExistingDirectory(self, "Select Export Directory")
        if not dir_path:
            return
            
        self.export_dir = dir_path
        
        self.is_bulk_exporting = True
        self.search_bar.setEnabled(False)
        self.select_all_btn.setEnabled(False)
        self.clear_sel_btn.setEnabled(False)
        self.message_list.setEnabled(False)
        self.setWindowTitle(f"PyMail - Bulk Exporting {len(self.export_queue)} emails...")
        
        self.process_next_export()

    def process_next_export(self):
        if not self.export_queue:
            self.is_bulk_exporting = False
            self.search_bar.setEnabled(True)
            self.select_all_btn.setEnabled(True)
            self.clear_sel_btn.setEnabled(True)
            self.message_list.setEnabled(True)
            self.setWindowTitle(f"PyMail - {self.conf['accounts'][0]['email']}")
            QMessageBox.information(self, "Bulk Export", "Bulk export completed successfully.")
            return
            
        email_id = self.export_queue.pop(0)
        self.message_viewer.load_html("Loading for export...")
        
        self.content_thread = MailContentThread(self.imap_client, self.current_folder, email_id)
        self.content_thread.finished.connect(self.display_email_for_bulk)
        self.content_thread.error.connect(self.show_error)
        self.content_thread.start()

    def display_email_for_bulk(self, content):
        self.display_email_content(content)
        
        headers = content.get("headers", {})
        
        to_email = headers.get('to', 'unknown_recipient')
        import re, os
        email_match = re.search(r'<([^>]+)>', to_email)
        if email_match:
            to_email = email_match.group(1)
            
        safe_to = "".join([c for c in to_email if c.isalnum() or c in ['@', '.', '_', '-']]).strip()
        if not safe_to:
            safe_to = "unknown"
            
        subject = headers.get('subject', 'No Subject')
        safe_subject = "".join([c for c in subject if c.isalnum() or c in [' ', '-', '_']]).strip()
        safe_subject = safe_subject[:100] if safe_subject else "No Subject"
        
        base_filename = f"{safe_to} - {safe_subject}"
        safe_filename = f"{base_filename}.pdf"
        filepath = os.path.join(self.export_dir, safe_filename)
        
        counter = 1
        while os.path.exists(filepath):
            safe_filename = f"{base_filename} ({counter}).pdf"
            filepath = os.path.join(self.export_dir, safe_filename)
            counter += 1
            
        self.current_bulk_filepath = filepath
        
        # Wait until rendering and all images are fully loaded before calculating height
        self.check_ready_attempts = 0
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(500, lambda: self.trigger_pdf_eval_when_ready(self.current_bulk_filepath))

    def show_error(self, msg):
        QMessageBox.warning(self, "Error", msg)
        self.setWindowTitle(f"PyMail - {self.conf['accounts'][0]['email']}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = PyMailWindow()
    window.show()
    sys.exit(app.exec())
