import imaplib
import email
from email.header import decode_header
import ssl
import re

def decode_mime_words(header_val):
    if not header_val:
        return ""
    try:
        parts = decode_header(header_val)
        decoded_str = []
        for part, encoding in parts:
            if isinstance(part, bytes):
                if encoding:
                    try:
                        decoded_str.append(part.decode(encoding, errors='replace'))
                    except (LookupError, UnicodeDecodeError):
                        decoded_str.append(part.decode('utf-8', errors='replace'))
                else:
                    decoded_str.append(part.decode('utf-8', errors='replace'))
            else:
                decoded_str.append(str(part))
        return "".join(decoded_str)
    except Exception:
        return str(header_val)


class IMAPClient:
    def __init__(self, host, port, username, password, use_ssl=True):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.use_ssl = use_ssl
        self.mail = None

    def connect(self):
        try:
            self.disconnect()
            if self.use_ssl:
                context = ssl.create_default_context()
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
                self.mail = imaplib.IMAP4_SSL(self.host, self.port, ssl_context=context)
            else:
                self.mail = imaplib.IMAP4(self.host, self.port)
            
            self.mail.login(self.username, self.password)
            return True, "Connected successfully"
        except Exception as e:
            self.mail = None
            return False, str(e)

    def is_connected(self):
        if not self.mail:
            return False
        try:
            status, _ = self.mail.noop()
            return status == 'OK'
        except Exception:
            return False

    def ensure_connected(self):
        if not self.is_connected():
            success, msg = self.connect()
            if not success:
                raise Exception(f"IMAP connection failed: {msg}")

    def disconnect(self):
        if self.mail:
            try:
                self.mail.logout()
            except Exception:
                pass
            self.mail = None

    def get_folders(self):
        self.ensure_connected()
        status, folders = self.mail.list()
        if status != 'OK' or not folders:
            return []
        
        folder_list = []
        pattern = re.compile(r'\((?P<flags>.*?)\)\s+"(?P<delimiter>.*?)"\s+(?P<name>.*)$')
        
        for folder_bytes in folders:
            if not folder_bytes:
                continue
            folder_str = folder_bytes.decode('utf-8', errors='ignore')
            m = pattern.search(folder_str)
            if m:
                flags = [f.strip() for f in m.group('flags').split()]
                name = m.group('name').strip(' "\'')
                is_selectable = '\\Noselect' not in flags
                folder_list.append({
                    "name": name,
                    "selectable": is_selectable,
                    "flags": flags
                })
            else:
                parts = folder_str.split('""')
                if len(parts) == 1:
                    parts = folder_str.split('"/"')
                name = parts[-1].strip(' "\'')
                folder_list.append({
                    "name": name,
                    "selectable": True,
                    "flags": []
                })
        return folder_list

    def get_emails(self, folder="INBOX", limit=50, offset=0):
        self.ensure_connected()
        
        # Select folder (imaplib will quote if necessary)
        status, _ = self.mail.select(folder, readonly=True)
        if status != 'OK':
            return {"emails": [], "total": 0}
        
        # Search for all email sequence numbers
        status, messages = self.mail.search(None, 'ALL')
        if status != 'OK' or not messages or not messages[0]:
            return {"emails": [], "total": 0}
            
        email_ids = messages[0].split()
        total_count = len(email_ids)
        if total_count == 0:
            return {"emails": [], "total": 0}
            
        # Slice latest IDs based on limit and offset
        if limit is not None:
            end_idx = total_count - offset
            start_idx = max(0, end_idx - limit)
            if start_idx >= end_idx or end_idx <= 0:
                return {"emails": [], "total": total_count}
            selected_ids = email_ids[start_idx:end_idx]
        else:
            selected_ids = email_ids
            
        selected_ids.reverse()  # Newest first
        
        # Batch fetch in chunks of 50 to optimize network round-trips
        chunk_size = 50
        email_data = []
        
        for i in range(0, len(selected_ids), chunk_size):
            chunk = selected_ids[i:i + chunk_size]
            id_bytes = b','.join(chunk)
            
            status, msg_data = self.mail.fetch(id_bytes, '(FLAGS BODY.PEEK[HEADER.FIELDS (SUBJECT FROM DATE TO CC)])')
            if status == 'OK':
                chunk_dict = {}
                for item in msg_data:
                    if isinstance(item, tuple) and len(item) == 2:
                        meta_part, header_bytes = item
                        m = re.match(rb'^(\d+)', meta_part.strip())
                        seq_id = m.group(1).decode() if m else ""
                        is_read = b'\\Seen' in meta_part
                        
                        msg = email.message_from_bytes(header_bytes)
                        
                        subject = decode_mime_words(msg.get("Subject", "")) or "(No Subject)"
                        sender = decode_mime_words(msg.get("From", ""))
                        date_str = decode_mime_words(msg.get("Date", ""))
                        
                        chunk_dict[seq_id] = {
                            "id": seq_id,
                            "subject": subject,
                            "from": sender,
                            "date": date_str,
                            "is_read": is_read
                        }
                # Maintain newest-first ordering
                for e_id in chunk:
                    e_id_str = e_id.decode()
                    if e_id_str in chunk_dict:
                        email_data.append(chunk_dict[e_id_str])
                        
        return {"emails": email_data, "total": total_count}
        
    def get_email_content(self, folder, email_id):
        self.ensure_connected()
            
        status, _ = self.mail.select(folder, readonly=True)
        if status != 'OK':
            return None
            
        status, msg_data = self.mail.fetch(email_id, '(RFC822)')
        if status != 'OK' or not msg_data:
            return None
            
        for response_part in msg_data:
            if isinstance(response_part, tuple) and len(response_part) == 2:
                msg = email.message_from_bytes(response_part[1])
                
                msg_details = {
                    "subject": decode_mime_words(msg.get("Subject", "")) or "(No Subject)",
                    "from": decode_mime_words(msg.get("From", "")),
                    "to": decode_mime_words(msg.get("To", "")),
                    "cc": decode_mime_words(msg.get("Cc", "")),
                    "date": decode_mime_words(msg.get("Date", ""))
                }
                
                body_text = ""
                body_html = ""
                
                if msg.is_multipart():
                    for part in msg.walk():
                        content_type = part.get_content_type()
                        content_disposition = str(part.get("Content-Disposition") or "")
                        
                        if "attachment" not in content_disposition:
                            payload = part.get_payload(decode=True)
                            if payload:
                                charset = part.get_content_charset() or 'utf-8'
                                try:
                                    decoded_payload = payload.decode(charset, errors='replace')
                                except (LookupError, UnicodeDecodeError):
                                    decoded_payload = payload.decode('utf-8', errors='replace')
                                    
                                if content_type == "text/plain":
                                    body_text += decoded_payload
                                elif content_type == "text/html":
                                    body_html += decoded_payload
                else:
                    content_type = msg.get_content_type()
                    payload = msg.get_payload(decode=True)
                    if payload:
                        charset = msg.get_content_charset() or 'utf-8'
                        try:
                            decoded_payload = payload.decode(charset, errors='replace')
                        except (LookupError, UnicodeDecodeError):
                            decoded_payload = payload.decode('utf-8', errors='replace')
                            
                        if content_type == "text/plain":
                            body_text = decoded_payload
                        elif content_type == "text/html":
                            body_html = decoded_payload
                
                return {
                    "text": body_text,
                    "html": body_html,
                    "headers": msg_details
                }
        return None
