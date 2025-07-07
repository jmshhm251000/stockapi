import pandas as pd
from llama_index.llms.ollama import Ollama
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.core import VectorStoreIndex
from llama_index.core.llms import ChatMessage
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
import chromadb
import os
import uuid
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core import SimpleDirectoryReader, Document
from llama_index.core.retrievers import VectorIndexRetriever
from llama_index.llms.llama_cpp import LlamaCPP


def process_row_sync_csv(row, sllm):
    prompt = (
        f"Here is the content of the section:\n\n{row.content}\n\n"
        "Provide a summary (a single paragraph) of the content."
    )
    response = sllm.chat([ChatMessage(role="user", content=prompt)])
    summary = response.message.content

    metadata = {
        key: getattr(row, key)
        for key in row._fields
        if key != "content"
    }

    metadata["summary"] = summary

    return Document(
        text=row.content,
        metadata=metadata
    )


def process_sync():
    # add documents to List of docs
    documents = SimpleDirectoryReader(input_files=["data/BUFFET.pdf", "data/ownman.pdf"]).load_data()

    df = pd.read_csv("data/annual_meeting_transcript.csv")
    letter_df = pd.read_csv("data/special letter from buffett.csv")

    docs = []
    
    sub_llm = Ollama(model="llama3.2", request_timeout=120.0, json_mode=True, ollama_additional_kwargs={ "max_tokens": 4096 })

    for doc in tqdm(documents, desc="Summarizing PDF Documents"):
        prompt = (
            f"Here is the content of the section:\n\n{doc.text}\n\n"
            "Provide a summary (a single paragraph) of the content."
        )
        response = sub_llm.chat([ChatMessage(role="user", content=prompt)])
        summary = response.message.content
        doc.metadata["summary"] = summary
        doc.metadata["title"] = "An Owner's Manual By Warren E. Buffett"


    for current_df in [df, letter_df]:
        with ThreadPoolExecutor(max_workers=16) as executor:
            futures = [executor.submit(process_row_sync_csv, row, sub_llm) for row in current_df.itertuples(index=False)]
            for future in tqdm(as_completed(futures), total=len(futures), desc="Processing Rows"):
                docs.append(future.result())

    docs.extend(documents)

    return docs


def construct_db_llm():
    embedding_model = OllamaEmbedding(model_name="nomic-embed-text", base_url="http://localhost:11434", embed_batch_size=16)
    chroma_client = chromadb.PersistentClient(path=os.path.join(os.getcwd(), "buffett_db"))
    chroma_collection = chroma_client.get_or_create_collection(name="Warren_Buffett")

    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)

    if chroma_collection.count() == 0:
        docs = process_sync()

        texts = [doc.text for doc in docs]
        embeddings = embedding_model.get_text_embedding_batch(texts)

        # Prepare metadata and unique IDs
        metadatas = [doc.metadata for doc in docs]
        ids = [str(uuid.uuid4()) for _ in docs]

        # Add documents to the Chroma collection
        chroma_collection.add(
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids
        )

    index = VectorStoreIndex.from_vector_store(embed_model=embedding_model, vector_store=vector_store)

    retriever = VectorIndexRetriever(index=index, similarity_top_k=5)

    llm = LlamaCPP(
        model_path="D:\\Dev\\Cpp\\my_app\\model\\DeepSeek-R1-Distill-Llama-8B-Q4_K_M.gguf",
        model_kwargs={
            "n_gpu_layers": 30,       # push most layers to GPU (your 3080 has ~10 GB usable VRAM)
            "n_ctx": 32768,           # safe high-context size that fits in RAM/GPU
            "n_threads": 12,          # ~number of physical CPU threads
            "n_batch": 512,           # adjust based on prompt length
            "main_gpu": 0,            # ensure it uses your main GPU
        },
        temperature=0.1,
        max_new_tokens=1024,
        context_window=32768,
        verbose=False,
    )

    return embedding_model, retriever, llm