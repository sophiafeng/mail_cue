import chainlit as cl
from gmail_auth import get_gmail_service
from email_parser import fetch_emails, parse_email

@cl.on_chat_start
async def start():
    # This will open a browser window for authentication
    service = get_gmail_service()
    cl.user_session.set("gmail_service", service)

@cl.on_message
async def on_message(message: cl.Message):
    service = cl.user_session.get("gmail_service")
    emails = fetch_emails(service)
    
    response = "Here are your latest emails:\n\n"
    for email in emails[:5]:  # Show only the first 5 emails
        parsed = parse_email(email)
        response += f"Subject: {parsed['subject']}\n"
        response += f"From: {parsed['sender']}\n"
        response += f"Date: {parsed['date']}\n\n"

    await cl.Message(content=response).send()