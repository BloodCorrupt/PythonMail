# PyMail 📬

**PyMail** is a lightweight, modern desktop email client built with Python, **PyQt6**, and **WebView2**. It features fast IMAP batch fetching, rich HTML email rendering, full-page PDF email export, and secure credential storage.

---

## ✨ Features

- **⚡ Fast Batch IMAP Loading**: Fetches email headers in optimized network batches (`HEADER.FIELDS`), providing near-instant mailbox navigation even for large folders.
- **🌐 Rich HTML Email Rendering**: Powered by Edge Chromium via `qtwebview2` for pixel-perfect modern email layouts, inline images, and styling.
- **📄 Export to PDF**:
  - **Single Email Export**: Save the currently viewed email directly to a single-page or formatted PDF.
  - **Bulk Export**: Select multiple emails and batch-export them all into a target folder.
- **✉️ Compose & Send (SMTP)**: Send emails with support for `To`, `Cc`, `Bcc`, plain text/HTML formatting, and automated SSL (Port 465) or STARTTLS (Port 587) negotiation.
- **🔒 Secure Credentials**: Passwords are encrypted and managed using your operating system's native secure credential vault via `keyring`.
- **🔍 Instant Search & Filter**: Real-time filtering across sender, subject, and date.
- **🛠️ Provider Auto-Configuration**: Auto-configures server and port settings for Gmail, Outlook, and Yahoo, with automatic cleaning of spaced Google App Passwords.

---

## 🚀 Installation & Setup

### 1. Prerequisites
- Python 3.10+
- Windows OS with [Microsoft Edge WebView2 Runtime](https://developer.microsoft.com/en-us/microsoft-edge/webview2/) (preinstalled on Windows 10/11)

### 2. Clone the Repository
```bash
git clone git@github.com:BloodCorrupt/PythonMail.git
cd PythonMail
```

### 3. Create a Virtual Environment (Recommended)
```bash
python -m venv .venv
.venv\Scripts\activate
```

### 4. Install Dependencies
```bash
pip install -r requirements.txt
```

---

## 🏃 Running the Application

Launch PyMail using:
```bash
python main.py
```

### Configuring Your Account
1. When launched for the first time, the **Account Settings** dialog will open.
2. Enter your email address:
   - **Gmail**: Use your email and a generated **Google App Password** (16 characters from Google Account > Security > 2-Step Verification > App passwords).
   - Server hostnames and ports will automatically fill in for Gmail, Outlook, and Yahoo.
3. Click **OK** to connect and load your inbox.

---

## 📁 Project Structure

```
PythonMail/
├── account_dialog.py   # Account configuration dialog & provider auto-detection
├── compose_dialog.py   # Email composer dialog with SMTP sending
├── config.py           # Configuration manager with OS keyring encryption
├── imap_client.py      # High-performance batch IMAP client with auto-reconnect
├── main.py             # Main PyQt6 application window, table views & PDF export
├── requirements.txt    # Project dependencies
├── smtp_client.py      # SMTP client supporting SSL and STARTTLS
└── .gitignore          # Git exclusion rules
```

---

## 📜 License

This project is open-source and available under the [MIT License](LICENSE).
