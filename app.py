import asyncio
import chainlit as cl
import json
import openai
import os

from custom_gmail_reader import CustomGmailReader
from datetime import datetime
from dotenv import load_dotenv
from langfuse.llama_index import LlamaIndexCallbackHandler
from llama_index.core import VectorStoreIndex
from llama_index.core import Settings
from llama_index.core.callbacks import CallbackManager
from llama_index.core.query_engine import RetrieverQueryEngine
from llama_index.core.retrievers import VectorIndexRetriever

from prompts import QUERY_SELECTION_PROMPT, SYSTEM_PROMPT

load_dotenv()

runpod_api_key = os.getenv("RUNPOD_API_KEY")
openai_api_key = os.getenv("OPENAI_API_KEY")
configurations = {
    "mistral_7B_instruct": {
        "endpoint_url": os.getenv("MISTRAL_7B_INSTRUCT_ENDPOINT"),
        "api_key": runpod_api_key,
        "model": "mistralai/Mistral-7B-Instruct-v0.3"
    },
    "mistral_7B": {
        "endpoint_url": os.getenv("MISTRAL_7B_ENDPOINT"),
        "api_key": runpod_api_key,
        "model": "mistralai/Mistral-7B-v0.1"
    },
    "openai_gpt-4": {
        "endpoint_url": os.getenv("OPENAI_ENDPOINT"),
        "api_key": openai_api_key,
        "model": "gpt-4"
    }
}

# Choose configuration
config_key = "openai_gpt-4"
# config_key = "mistral_7B_instruct"
# config_key = "mistral_7B"

# Get selected configuration
config = configurations[config_key]
client = openai.AsyncClient(api_key=config["api_key"], base_url=config["endpoint_url"])

gen_kwargs = {
    "model": config["model"],
    "temperature": 0.3,
    "max_tokens": 500
}

langfuse_callback_handler = LlamaIndexCallbackHandler()
Settings.callback_manager = CallbackManager([langfuse_callback_handler])

if not langfuse_callback_handler.auth_check():
    print("Authentication failed. Please check your credentials.")
    exit(1)


# Global variables to store the query engine
query_engine = None

@cl.on_chat_start
async def start():
    global query_engine
    global calendar_documents
    global order_update_documents
    global newsletter_summary_documents
    global follow_up_documents

    # Instantiate the CustomGmailReader
    loader = CustomGmailReader(
        query="",
        max_results=2,
        results_per_page=2,
        service=None
    )   

    # Load emails
    documents = loader.load_data()

    # Print email information
    print("\n\n\n\n\n\n\n START OF DOCUMENTS -------------------------------")
    print(f"Number of documents: {len(documents)}\n")
    for i, doc in enumerate(documents[:20]):
        print(f"\n*****Document {i+1}:*****")
        print(f"To: {doc.metadata.get('to', 'N/A')}")
        print(f"From: {doc.metadata.get('from', 'N/A')}")
        print(f"Subject: {doc.metadata.get('subject', 'N/A')}")
        print(f"Date: {doc.metadata.get('date', 'N/A')}")
        print(f"Content snippet: {doc.text[:1000]}...")
        print("=" * 50)
    print("\n\n\n\n\n\n\n END OF DOCUMENTS -------------------------------\n\n\n\n\n\n\n")        

    # Create index
    index = VectorStoreIndex.from_documents(documents)

    # Create retriever
    retriever = VectorIndexRetriever(index=index)

    # # Create query engine
    query_engine = RetrieverQueryEngine(retriever=retriever)

    await cl.Message(content="Email data loaded. You can now ask questions about your emails.").send()


def get_latest_user_message(message_history):
    # Iterate through the message history in reverse to find the last user message
    for message in reversed(message_history):
        if message['role'] == 'user':
            return message['content']
    return None

async def assess_message(message_history):
    latest_message = get_latest_user_message(message_history)
    print("\n\n-----------------Latest Message:-----------------")
    print(latest_message)

    # Remove the original prompt from the message history for assessment
    filtered_history = [msg for msg in message_history if msg['role'] != 'system']

    # Generate the assessment prompt
    filled_prompt = QUERY_SELECTION_PROMPT.format(history=filtered_history, current_date=datetime.now().strftime("%Y-%m-%d"), latest_message=latest_message)
    print("\n\n-----------------Filled Prompt:-----------------")
    print(filled_prompt)

    response = await client.chat.completions.create(messages=[{"role": "system", "content": filled_prompt}], **gen_kwargs)
    assessment_output = response.choices[0].message.content.strip()
    print("Assessment Output: \n\n", assessment_output)
    return assessment_output

@cl.on_message
async def on_message(message: cl.Message):
    global query_engine

    if query_engine is None:
        await cl.Message(content="Email data is not loaded yet. Please wait or restart the application.").send()
        return

    # Add the user message to the message history
    message_history = cl.user_session.get("message_history", [])
    if not message_history or message_history[0].get("role") != "system":
        message_history.insert(0, {"role": "system", "content": SYSTEM_PROMPT})
    message_history.append({"role": "user", "content": message.content})

    query = await assess_message(message_history)
    print("\n\n-----------------Query:-----------------")
    print(query)

    email_query_response = query_engine.query(query)
    print("\n\n-----------------Email Query Response:-----------------")
    print(email_query_response)
    await cl.Message(content=str(email_query_response)).send()

    # Add the email query response to the message history   
    message_history.append({"role": "assistant", "content": email_query_response})
    cl.user_session.set("message_history", message_history)
