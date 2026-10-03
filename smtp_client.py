import smtplib
from email.message import EmailMessage

class SMTPClient:
    def __init__(self, host, port, username, password, use_ssl=True):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.use_ssl = use_ssl

    def send_email(self, to_address, subject, body, cc="", bcc=""):
        try:
            msg = EmailMessage()
            msg.set_content(body)
            msg['Subject'] = subject
            msg['From'] = self.username
            msg['To'] = to_address
            if cc:
                msg['Cc'] = cc
            if bcc:
                msg['Bcc'] = bcc

            import ssl
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE

            # Port 465 is implicit SSL; Port 587 / 25 uses STARTTLS
            if self.port == 465 or (self.use_ssl and self.port != 587):
                server = smtplib.SMTP_SSL(self.host, self.port, context=context)
            else:
                server = smtplib.SMTP(self.host, self.port)
                if self.use_ssl or self.port == 587:
                    server.starttls(context=context)
            
            server.login(self.username, self.password)
            server.send_message(msg)
            server.quit()
            
            return True, "Email sent successfully"
        except Exception as e:
            return False, str(e)
