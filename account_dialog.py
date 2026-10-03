from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, 
    QDialogButtonBox, QCheckBox, QMessageBox
)

class AccountDialog(QDialog):
    def __init__(self, parent=None, account_data=None):
        super().__init__(parent)
        self.setWindowTitle("Account Settings")
        self.resize(300, 200)
        
        self.layout = QVBoxLayout(self)
        self.form_layout = QFormLayout()
        
        self.email_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        
        self.imap_host_input = QLineEdit()
        self.imap_port_input = QLineEdit("993")
        
        self.smtp_host_input = QLineEdit()
        self.smtp_port_input = QLineEdit("465")
        
        self.use_ssl_cb = QCheckBox("Use SSL")
        self.use_ssl_cb.setChecked(True)
        
        self.form_layout.addRow("Email Address:", self.email_input)
        self.form_layout.addRow("Password:", self.password_input)
        self.form_layout.addRow("IMAP Server:", self.imap_host_input)
        self.form_layout.addRow("IMAP Port:", self.imap_port_input)
        self.form_layout.addRow("SMTP Server:", self.smtp_host_input)
        self.form_layout.addRow("SMTP Port:", self.smtp_port_input)
        self.form_layout.addRow("", self.use_ssl_cb)
        
        self.email_input.textChanged.connect(self.on_email_changed)
        
        if account_data:
            self.email_input.setText(account_data.get('email', ''))
            self.password_input.setText(account_data.get('password', ''))
            self.imap_host_input.setText(account_data.get('imap_host', ''))
            self.imap_port_input.setText(str(account_data.get('imap_port', 993)))
            self.smtp_host_input.setText(account_data.get('smtp_host', ''))
            self.smtp_port_input.setText(str(account_data.get('smtp_port', 587)))
            self.use_ssl_cb.setChecked(account_data.get('use_ssl', True))
            
        self.layout.addLayout(self.form_layout)
        
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.layout.addWidget(self.buttons)

    def on_email_changed(self, text):
        domain = text.split('@')[-1].lower().strip() if '@' in text else ""
        if domain == "gmail.com":
            if not self.imap_host_input.text() or "gmail" in self.imap_host_input.text():
                self.imap_host_input.setText("imap.gmail.com")
                self.imap_port_input.setText("993")
                self.smtp_host_input.setText("smtp.gmail.com")
                self.smtp_port_input.setText("587")
                self.use_ssl_cb.setChecked(True)
        elif domain in ["outlook.com", "hotmail.com", "live.com"]:
            if not self.imap_host_input.text() or "outlook" in self.imap_host_input.text():
                self.imap_host_input.setText("outlook.office365.com")
                self.imap_port_input.setText("993")
                self.smtp_host_input.setText("smtp.office365.com")
                self.smtp_port_input.setText("587")
                self.use_ssl_cb.setChecked(True)
        elif domain == "yahoo.com":
            if not self.imap_host_input.text() or "yahoo" in self.imap_host_input.text():
                self.imap_host_input.setText("imap.mail.yahoo.com")
                self.imap_port_input.setText("993")
                self.smtp_host_input.setText("smtp.mail.yahoo.com")
                self.smtp_port_input.setText("465")
                self.use_ssl_cb.setChecked(True)
        
    def get_account_data(self):
        try:
            imap_port = int(self.imap_port_input.text().strip())
        except ValueError:
            imap_port = 993
            
        try:
            smtp_port = int(self.smtp_port_input.text().strip())
        except ValueError:
            smtp_port = 587
            
        pwd = self.password_input.text().strip()
        # Google App Passwords copied from Google UI often contain 4 groups of 4 chars with spaces: 'xxxx xxxx xxxx xxxx'
        if len(pwd) == 19 and pwd.count(' ') == 3:
            pwd = pwd.replace(' ', '')
            
        return {
            "email": self.email_input.text().strip(),
            "password": pwd,
            "imap_host": self.imap_host_input.text().strip(),
            "imap_port": imap_port,
            "smtp_host": self.smtp_host_input.text().strip(),
            "smtp_port": smtp_port,
            "use_ssl": self.use_ssl_cb.isChecked()
        }
