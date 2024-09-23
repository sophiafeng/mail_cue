from gmail_auth import get_gmail_service
from email_parser import fetch_emails, parse_email

def main():
    print("Authenticating with Gmail...")
    service = get_gmail_service()
    
    print("Fetching emails...")
    emails = fetch_emails(service)
    
    print(f"Found {len(emails)} emails. Displaying the first 5:")
    for email in emails[:5]:
        parsed_email = parse_email(email)
        print(f"\nSubject: {parsed_email['subject']}")
        print(f"From: {parsed_email['sender']}")
        print(f"Date: {parsed_email['date']}")
        print(f"Body preview: {parsed_email['body'][:100]}...")
        print("-" * 50)

if __name__ == "__main__":
    main()