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
from openai import AsyncOpenAI

from email_actions import generate_email_reply
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



MAX_TOKENS = 8000  # Leave some buffer for the response

async def truncate_message_history(message_history):
    client = AsyncOpenAI()
    truncated_history = []
    current_tokens = 0

    for message in reversed(message_history):
        tokens = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": message["content"]}],
            max_tokens=1  # We only need the token count, not a real completion
        )
        message_tokens = tokens.usage.prompt_tokens

        if current_tokens + message_tokens > MAX_TOKENS:
            break

        truncated_history.insert(0, message)
        current_tokens += message_tokens

    return truncated_history

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
        print(f"ID: {doc.metadata.get('id', 'N/A')}")
        print(f"Thread ID: {doc.metadata.get('threadId', 'N/A')}")
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

async def generate_query(message_history):
    truncated_history = await truncate_message_history(message_history)
    filled_prompt = QUERY_SELECTION_PROMPT.format(
        history="\n".join([f"{m['role']}: {m['content']}" for m in truncated_history]),
        current_date=datetime.now().strftime("%Y-%m-%d"),
        latest_message=truncated_history[-1]["content"] if truncated_history else ""
    )
    print("\n\n-----------------Filled Prompt:-----------------")
    print(filled_prompt)

    response = await client.chat.completions.create(messages=[{"role": "system", "content": filled_prompt}], **gen_kwargs)
    assessment_output = response.choices[0].message.content.strip()
    print("Assessment Output: \n\n", assessment_output)
    return assessment_output

@cl.on_message
async def on_message(message: cl.Message):
    # Add the user message to the message history
    message_history = cl.user_session.get("message_history", [])
    if not message_history or message_history[0].get("role") != "system":
        message_history.insert(0, {"role": "system", "content": SYSTEM_PROMPT})
    message_history.append({"role": "user", "content": message.content})

    # Check if the query engine is loaded
    global query_engine
    if query_engine is None:
        await cl.Message(content="Email data is not loaded yet. Please wait or restart the application.").send()
        return

    # Assess the message and get the query
    query = await generate_query(message_history)
    print("\n\n-----------------Query:-----------------")
    print(query)

    # If the query is not empty, run it through the query engine
    if query:
        email_query_response = query_engine.query(query)
        print("\n\n-----------------Email Query Response:-----------------")
        print(email_query_response)
        await cl.Message(content=str(email_query_response)).send()    
    else:  # If the query is empty, get a response from OpenAI
        print("No query suitable for the user's question. Generating a response from OpenAI.")
        
        # Prepare the messages for the OpenAI API
        openai_messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": message.content}
        ]
        
        try:
            response = await client.chat.completions.create(
                messages=openai_messages,
                **gen_kwargs
            )
            
            ai_response = response.choices[0].message.content.strip()
            await cl.Message(content=ai_response).send()

            # Check if the AI response contains a function call
            function_call = None
            try:
                # Parse the AI response as JSON
                response_json = json.loads(ai_response)
                if "function_name" in response_json and response_json["function_name"] == "generate_email_reply":
                    generate_email_reply(response_json["parameters"]["id"])
                    function_call = response_json
            except json.JSONDecodeError:
                 # If it's not valid JSON, treat it as a normal message
                message_history.append({"role": "assistant", "content": response.content})
                print("BREAK LOOP: No JSON found in response message. Breaking out of loop.")

            if function_call:
                # Extract the function call details
                function_name = function_call["function_name"]
                rationale = function_call["rationale"]
                email_id = function_call["parameters"]["id"]

                # Log the function call
                print(f"Function call detected: {function_name}")
                print(f"Rationale: {rationale}")
                print(f"Email ID: {email_id}")

                await cl.Message(content=f"Function '{function_name}' called with email ID: {email_id}. Rationale: {rationale}").send()


            
            # Add the AI response to the message history
            message_history.append({"role": "assistant", "content": ai_response})
            cl.user_session.set("message_history", message_history)
        except Exception as e:
            error_message = f"An error occurred while generating a response: {str(e)}"
            print(error_message)
            await cl.Message(content=error_message).send()
