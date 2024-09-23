"""
Google Mail reader.

The original code is: https://github.com/run-llama/llama_index/blob/main/llama-index-integrations/readers/llama-index-readers-google/llama_index/readers/google/gmail/base.py

Modifications made to create a cleaner document, and add metadata for filtering (to, from, subject, etc.)
"""

import base64
from typing import Any, List, Optional

from llama_index.core.readers.base import BaseReader
from llama_index.core.schema import Document
from pydantic import BaseModel
from gmail_auth import get_gmail_service


class CustomGmailReader(BaseReader, BaseModel):
    """Gmail reader.

    Reads emails

    Args:
        max_results (int): Defaults to 10.
        query (str): Gmail query. Defaults to None.
        service (Any): Gmail service. Defaults to None.
        results_per_page (Optional[int]): Max number of results per page. Defaults to 10.
        use_iterative_parser (bool): Use iterative parser. Defaults to False.
    """

    query: str = None
    use_iterative_parser: bool = False
    max_results: int = 10
    service: Any
    results_per_page: Optional[int]

    def load_data(self) -> List[Document]:
        """Load emails from the user's account."""

        if not self.service:
            self.service = get_gmail_service()

        messages = self.search_messages()

        results = []
        for message in messages:
            text = message.pop("body")
            metadata = message

            results.append(Document(text=text, metadata=metadata or {}))

        return results

    def search_messages(self):
        query = self.query

        max_results = self.max_results
        if self.results_per_page:
            max_results = self.results_per_page

        results = (
            self.service.users()
            .messages()
            .list(userId="me", q=query, maxResults=int(max_results))
            .execute()
        )
        messages = results.get("messages", [])

        if len(messages) < self.max_results:
            # paginate if there are more results
            while "nextPageToken" in results:
                page_token = results["nextPageToken"]
                results = (
                    self.service.users()
                    .messages()
                    .list(
                        userId="me",
                        q=query,
                        pageToken=page_token,
                        maxResults=int(max_results),
                    )
                    .execute()
                )
                messages.extend(results["messages"])
                if len(messages) >= self.max_results:
                    break

        result = []
        try:
            for message in messages:
                message_data = self.get_message_data(message)
                if not message_data:
                    continue
                result.append(message_data)
        except Exception as e:
            raise Exception("Can't get message data" + str(e))

        return result

    def get_message_data(self, message):
        message_id = message["id"]
        message_data = (
            self.service.users()
            .messages()
            .get(userId="me", id=message_id, format="full")
            .execute()
        )

        headers = {header['name'].lower(): header['value'] for header in message_data['payload']['headers']}

        body = self.extract_message_body(message_data)

        return {
            "id": message_data["id"],
            "threadId": message_data["threadId"],
            "snippet": message_data.get("snippet", ""),
            "internalDate": message_data.get("internalDate", ""),
            "body": body,
            "from": headers.get('from', ""),
            "to": headers.get('to', ""),
            "subject": headers.get('subject', ""),
            "date": headers.get('date', ""),
        }

    def extract_message_body(self, message_data):
        def get_text(payload):
            if 'body' in payload:
                data = payload['body'].get('data')
                if data:
                    return base64.urlsafe_b64decode(data).decode('utf-8', errors='replace')
            return ''

        def find_plain_text(payload):
            if payload.get('mimeType') == 'text/plain':
                return get_text(payload)
            if 'parts' in payload:
                for part in payload['parts']:
                    text = find_plain_text(part)
                    if text:
                        return text
            return ''

        body = find_plain_text(message_data['payload'])
        return body if body else ""


if __name__ == "__main__":
    reader = CustomGmailReader(query="from:me after:2023-01-01")
    print(reader.load_data())