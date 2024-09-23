import chainlit as cl
from custom_gmail_reader import CustomGmailReader
from llama_index.core.retrievers import VectorIndexRetriever
from llama_index.core.query_engine import RetrieverQueryEngine
from llama_index.core import VectorStoreIndex

# Global variables to store the query engine
query_engine = None
    
@cl.on_chat_start
async def start():
    global query_engine

    # Instantiate the CustomGmailReader
    loader = CustomGmailReader(
        query="",
        max_results=10,
        results_per_page=10,
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

    # Create query engine
    query_engine = RetrieverQueryEngine(retriever=retriever)

    await cl.Message(content="Email data loaded. You can now ask questions about your emails.").send()

@cl.on_message
async def on_message(message: cl.Message):
    global query_engine

    if query_engine is None:
        await cl.Message(content="Email data is not loaded yet. Please wait or restart the application.").send()
        return

    response = query_engine.query(message.content)

    await cl.Message(content=str(response)).send()


    await cl.Message(content=response).send()