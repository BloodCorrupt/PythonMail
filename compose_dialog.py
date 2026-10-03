from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, 
    QTextEdit, QPushButton, QMessageBox
)
from PyQt6.QtCore import pyqtSignal, QThread
from smtp_client import SMTPClient

class SendEmailThread(QThread):
    finished = pyqtSignal(bool, str)

    def __init__(self, client, to_addr, subject, body, cc="", bcc=""):
        super().__init__()
        self.client = client
        self.to_addr = to_addr
        self.subject = subject
        self.body = body
        self.cc = cc
        self.bcc = bcc

    def run(self):
        success, msg = self.client.send_email(
            self.to_addr, self.subject, self.body, self.cc, self.bcc
        )
        self.finished.emit(success, msg)

class ComposeDialog(QDialog):
    def __init__(self, parent=None, account_data=None):
        super().__init__(parent)
        self.setWindowTitle("Compose Email")
        self.resize(600, 500)
        
        self.account_data = account_data
        
        self.layout = QVBoxLayout(self)
        
        self.form_layout = QFormLayout()
        
        self.to_input = QLineEdit()
        self.cc_input = QLineEdit()
        self.bcc_input = QLineEdit()
        self.subject_input = QLineEdit()
        
        self.form_layout.addRow("To:", self.to_input)
        self.form_layout.addRow("Cc:", self.cc_input)
        self.form_layout.addRow("Bcc:", self.bcc_input)
        self.form_layout.addRow("Subject:", self.subject_input)
        
        self.layout.addLayout(self.form_layout)
        
        self.body_input = QTextEdit()
        self.layout.addWidget(self.body_input)
        
        self.button_layout = QHBoxLayout()
        self.send_button = QPushButton("Send")
        self.send_button.clicked.connect(self.send_email)
        
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        
        self.button_layout.addStretch()
        self.button_layout.addWidget(self.send_button)
        self.button_layout.addWidget(self.cancel_button)
        
        self.layout.addLayout(self.button_layout)
        
    def send_email(self):
        if not self.account_data:
            QMessageBox.warning(self, "Error", "No account configured.")
            return
            
        if not self.to_input.text():
            QMessageBox.warning(self, "Error", "Please enter a recipient.")
            return
            
        self.send_button.setEnabled(False)
        self.send_button.setText("Sending...")
        
        # Use SMTP settings. Fallback to common SMTP ports if not set
        # But we need SMTP host/port in account data, let's assume they are the same host or user adds it
        # Wait, the account_dialog didn't ask for SMTP. Let's assume standard ports for demo
        # A full app would ask for SMTP host and port
        smtp_host = self.account_data.get('smtp_host', self.account_data.get('imap_host').replace('imap', 'smtp'))
        smtp_port = self.account_data.get('smtp_port', 465 if self.account_data.get('use_ssl') else 587)
        
        client = SMTPClient(
            host=smtp_host,
            port=smtp_port,
            username=self.account_data['email'],
            password=self.account_data['password'],
            use_ssl=self.account_data.get('use_ssl', True)
        )
        
        self.send_thread = SendEmailThread(
            client,
            self.to_input.text(),
            self.subject_input.text(),
            self.body_input.toPlainText(),
            self.cc_input.text(),
            self.bcc_input.text()
        )
        self.send_thread.finished.connect(self.on_send_finished)
        self.send_thread.start()
        
    def on_send_finished(self, success, msg):
        self.send_button.setEnabled(True)
        self.send_button.setText("Send")
        
        if success:
            QMessageBox.information(self, "Success", "Email sent successfully!")
            self.accept()
        else:
            QMessageBox.critical(self, "Error", f"Failed to send email:\n{msg}")
