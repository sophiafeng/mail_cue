from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
import base64
import email
from email.header import decode_header

def get_gmail_service(credentials):
    return build('gmail', 'v1', credentials=credentials)

def fetch_emails(service, num_emails=10):
    results = service.users().messages().list(userId='me', maxResults=num_emails).execute()
    messages = results.get('messages', [])

    emails = []
    for message in messages:
        msg = service.users().messages().get(userId='me', id=message['id'], format='raw').execute()
        msg_str = base64.urlsafe_b64decode(msg['raw'].encode('ASCII'))
        email_message = email.message_from_bytes(msg_str)
        emails.append(email_message)

    return emails

def parse_email(email_message):
    # Extract relevant information from the email
    subject = decode_header(email_message["Subject"])[0][0]
    sender = email_message["From"]
    date = email_message["Date"]

    body = ""
    if email_message.is_multipart():
        for part in email_message.walk():
            if part.get_content_type() == "text/plain":
                body = part.get_payload(decode=True).decode()
                break
    else:
        body = email_message.get_payload(decode=True).decode()

    return {
        "subject": subject,
        "sender": sender,
        "date": date,
        "body": body
    }

# Usage example
if __name__ == "__main__":
    credentials = Credentials.from_authorized_user_file('path/to/token.json')
    service = get_gmail_service(credentials)
    emails = fetch_emails(service)
    
    for email_message in emails:
        parsed_email = parse_email(email_message)
        print(f"Subject: {parsed_email['subject']}")
        print(f"From: {parsed_email['sender']}")
        print(f"Date: {parsed_email['date']}")
        print(f"Body: {parsed_email['body'][:100]}...")  # Print first 100 characters of the body
        print("---")