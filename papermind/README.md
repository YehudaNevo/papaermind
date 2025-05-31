# PaperMind

PaperMind is a Retrieval Augmented Generation (RAG) application designed to allow users to chat with their PDF documents. It uses Large Language Models (LLMs) and embedding techniques to provide answers based on the content of the supplied PDFs. This version is a lean-start variant using OpenAI models, with a Next.js frontend.

## Features

*   **PDF Processing:** Chunks PDF documents based on headings and content structure.
*   **Vector Embeddings:** Generates embeddings for text chunks using OpenAI's `text-embedding-3-small`.
*   **Vector Store:** Stores and retrieves text chunks using ChromaDB.
*   **LLM Integration:** Uses OpenAI's `gpt-4o` for generating answers based on retrieved context.
*   **Streaming Responses:** Provides real-time streaming of answers to the user.
*   **Web Interface:** A Next.js frontend for uploading PDFs (future), asking questions, and viewing answers.
*   **Modular Design:** Provider interface for easy swapping of LLM/embedding backends (e.g., for Groq).

## Directory Structure

```
papermind/
├── agents/                 # Core logic for PDF processing, embedding, and RAG graph
│   ├── __init__.py
│   ├── chunk_pdf.py        # PDF text extraction and chunking logic
│   ├── embed_index.py      # Embedding chunks and indexing in ChromaDB
│   └── ask_graph.py        # LangGraph definition for the RAG pipeline
├── data/                   # Directory for storing data
│   └── pdfs/               # Default location for input PDF files
├── frontend/               # Next.js frontend application
│   ├── app/                # Next.js app router components
│   │   ├── globals.css
│   │   ├── layout.tsx      # Root layout
│   │   ├── page.tsx        # Main chat interface page
│   │   └── rag/
│   │       └── route.ts    # API route for frontend to backend communication
│   ├── next-env.d.ts
│   ├── next.config.mjs
│   ├── package.json
│   ├── postcss.config.js
│   ├── tailwind.config.ts
│   └── tsconfig.json
├── store/                  # ChromaDB vector store location and other persisted data
│   └── processed_checksums.json # Stores checksums of processed PDFs
├── tests/                  # Test utilities
│   ├── __init__.py
│   └── create_dummy.py     # Utility to create a dummy PDF for testing
├── .env                    # Environment variable configuration (needs to be created by user)
├── main.py                 # FastAPI backend server and CLI entry point
├── pyproject.toml          # Python project metadata and dependencies (Poetry)
├── README.md               # This file
└── requirements.txt        # Python dependencies for pip users
```

## Setup and Installation

### Prerequisites

*   **Python:** Version 3.9 or higher.
*   **Poetry (recommended for Python):** For managing Python dependencies. Install from [official Poetry website](https://python-poetry.org/docs/#installation).
*   **Node.js:** Version 18.x or higher (for the Next.js frontend).
*   **npm or yarn:** For managing frontend dependencies.

### Backend Setup

1.  **Clone the Repository:**
    ```bash
    git clone <repository_url>
    cd papermind
    ```

2.  **Create and Configure `.env` file:**
    Navigate to the `papermind` directory. Copy the example environment variables or create a new `.env` file (`papermind/.env`) and add your OpenAI API key:
    ```env
    OPENAI_API_KEY="YOUR_OPENAI_API_KEY_HERE"
    BACKEND_URL="http://127.0.0.1:8000"
    ```
    Replace `"YOUR_OPENAI_API_KEY_HERE"` with your actual OpenAI API key.

3.  **Install Python Dependencies:**

    *   **Using Poetry (recommended):**
        ```bash
        poetry install
        ```
        This will create a virtual environment and install all dependencies from `pyproject.toml`. To activate the virtual environment, run `poetry shell`.

    *   **Using pip and `requirements.txt`:**
        If you prefer not to use Poetry, you can create a virtual environment manually and install dependencies using `pip`:
        ```bash
        python -m venv .venv
        source .venv/bin/activate  # On Windows: .venv\Scripts\activate
        pip install -r requirements.txt
        ```

### Frontend Setup

1.  **Navigate to Frontend Directory:**
    ```bash
    cd frontend
    ```

2.  **Install Node.js Dependencies:**
    ```bash
    npm install
    # or
    # yarn install
    ```

## Running the Application

### 1. Index PDF Documents

Before you can ask questions, you need to process and index your PDF files.

1.  Place your PDF files into the `papermind/data/pdfs/` directory.
2.  From the root `papermind` directory, run the indexing command:
    *   If using Poetry:
        ```bash
        poetry run python main.py index --path ./data/pdfs/
        ```
    *   If using a manual virtual environment (ensure it's activated):
        ```bash
        python main.py index --path ./data/pdfs/
        ```
    You can omit `--path` to use the default `papermind/data/pdfs/` directory.
    The first time you run this, if `papermind/data/pdfs/` is empty, a `dummy.pdf` might be created for testing.

### 2. Start the Backend Server

The backend is a FastAPI application.

*   If using Poetry:
    ```bash
    poetry run python main.py serve --host 127.0.0.1 --port 8000
    ```
*   If using a manual virtual environment:
    ```bash
    python main.py serve --host 127.0.0.1 --port 8000
    ```
The server will start, typically on `http://127.0.0.1:8000`.

### 3. Start the Frontend Development Server

In a new terminal, navigate to the `papermind/frontend/` directory and run:

```bash
npm run dev
# or
# yarn dev
```
The frontend will typically start on `http://localhost:3000`. Open this URL in your browser to use PaperMind.

## Module Explanations

### `papermind/providers.py`

*   **Purpose:** Defines interfaces (`Embedder`, `Chat`) for embedding and chat model services and provides concrete implementations. This allows for easy swapping of service providers (e.g., OpenAI, Groq).
*   **Key Components:**
    *   `Embedder` (Protocol): Defines an `embed` method for generating text embeddings.
    *   `Chat` (Protocol): Defines a `stream` method for interacting with chat models.
    *   `OpenAIEmbedder`: Implements `Embedder` using OpenAI's API (`text-embedding-3-small`).
    *   `OpenAIChat`: Implements `Chat` using OpenAI's API (`gpt-4o`), supporting streaming.
    *   Instantiated `embedder` and `chat` objects are exported for use throughout the application.

### `papermind/agents/chunk_pdf.py`

*   **Purpose:** Responsible for extracting text from PDF files and splitting it into manageable chunks.
*   **Key Components:**
    *   `detect_chunks(path: str) -> List[Dict]`:
        *   Opens a PDF using `fitz` (PyMuPDF).
        *   Iterates through pages and their text blocks.
        *   Uses a regular expression (`H_TAG`) and font size analysis (comparing current line's font size to previous or a page default) to identify potential headings.
        *   Creates chunks, where each chunk is a dictionary containing `header`, `body` (text under the header), and `page` number.
        *   Body text is stripped of leading/trailing whitespace.

### `papermind/agents/embed_index.py`

*   **Purpose:** Handles the embedding of text chunks and their storage and retrieval from a ChromaDB vector database.
*   **Key Components:**
    *   `upsert(pdf_path: str)` (async):
        *   Takes a PDF file path as input.
        *   Calculates an MD5 checksum of the PDF file. If the checksum exists in `papermind/store/processed_checksums.json`, processing for this PDF is skipped.
        *   Calls `detect_chunks` to get text chunks from the PDF.
        *   Batches chunks (e.g., 100 per batch) and calls the `embedder.embed()` method from `providers.py` to get vector embeddings for `header + " " + body` of each chunk.
        *   Adds each chunk's text (`json.dumps(chunk)`), embedding, and metadata (`header`, `page`) to a ChromaDB collection named "chunks". The database is stored in `papermind/store/`.
        *   Updates `processed_checksums.json` with the new PDF's checksum upon successful processing.

### `papermind/agents/ask_graph.py`

*   **Purpose:** Defines the core RAG (Retrieval Augmented Generation) pipeline using LangGraph.
*   **Key Components:**
    *   `GraphState` (TypedDict): Defines the state passed between nodes in the graph (`query`, `documents`).
    *   `retrieve_node(state: GraphState)` (async):
        *   Takes the user's query from the state.
        *   Generates an embedding for the query using the global `embedder`.
        *   Queries the ChromaDB "chunks" collection for the top `k` most similar chunks, including their documents and metadatas.
        *   Updates the graph state with the retrieved `documents`.
    *   `generate_node(state: GraphState)` (async generator):
        *   Receives the user's query and retrieved documents from the state.
        *   Constructs a context for the LLM using these documents, including page numbers and headers for citation.
        *   Calls the global `chat.stream()` method from `providers.py` to get a streamed response from the LLM.
        *   Yields content parts from the stream, stripping leading whitespace and ensuring parts are not None.
    *   `workflow` (StateGraph): A LangGraph `StateGraph` instance.
        *   Nodes: `retriever` (calls `retrieve_node`) and `generator` (calls `generate_node`).
        *   Edges: Defines the flow from `retriever` to `generator`.
    *   `rag_app`: The compiled LangGraph application, ready to process queries.

### `papermind/main.py` (Backend Server and CLI)

*   **Purpose:** Serves as the main entry point for the backend application. It provides a FastAPI web server for the RAG API and a command-line interface (CLI) for tasks like indexing.
*   **Key Components:**
    *   **FastAPI App (`app`):**
        *   `/rag_stream` (GET endpoint):
            *   Accepts a query parameter `q`.
            *   Uses the compiled `rag_app` from `ask_graph.py` to process the query and get a streamed response.
            *   Streams the response back to the client using Server-Sent Events (SSE) format (`data: {token}\n\n`).
    *   **CLI (using `argparse`):**
        *   `index` command:
            *   Takes an optional `--path` argument for the directory containing PDFs (defaults to `papermind/data/pdfs/`).
            *   Iterates through PDF files in the specified directory and calls `embed_index.upsert()` for each.
            *   Uses the `create_dummy_pdf_for_testing` utility if the target PDF directory is empty on first run.
        *   `serve` command:
            *   Takes optional `--host` and `--port` arguments.
            *   Starts the Uvicorn server to run the FastAPI application.
            *   Checks if the ChromaDB collection is empty and attempts to index a dummy PDF if so, to ensure the app is usable on first launch.
    *   Loads environment variables from `.env` using `python-dotenv`.
    *   Imports `create_dummy_pdf_for_testing` from `papermind.tests.create_dummy`.

### `papermind/frontend/` (Frontend Overview)

*   **Purpose:** Provides the user interface for PaperMind.
*   **Technology:** Built with Next.js (React framework) and TypeScript. Styled with Tailwind CSS.
*   **Key Parts:**
    *   `app/`: Uses the Next.js App Router.
    *   `package.json`: Defines dependencies (`next`, `react`, `tailwindcss`, etc.) and scripts (`dev`, `build`, `start`).

### `papermind/frontend/app/rag/route.ts`

*   **Purpose:** A Next.js API Route that acts as a proxy between the frontend client and the Python FastAPI backend.
*   **Functionality:**
    *   Receives a query `q` from the frontend via a GET request.
    *   Forwards this query to the backend's `/rag_stream` endpoint (URL configurable via `BACKEND_URL` env var, defaults to `http://127.0.0.1:8000`).
    *   Streams the response from the backend directly back to the frontend client as `text/event-stream`.

### `papermind/frontend/app/page.tsx`

*   **Purpose:** The main page of the PaperMind application where users interact with the RAG system.
*   **Functionality (`'use client'` component):**
    *   Displays an input field for the user to type their query.
    *   On form submission:
        *   Sends the query to the `/rag` Next.js API route (which then calls the backend).
        *   Receives the streaming response.
        *   Dynamically updates the page to display the incoming tokens from the LLM in a `<pre>` tag, preserving formatting.
    *   Handles loading states and displays errors if they occur during the process.

### Environment Variables (`papermind/.env`)

*   **Purpose:** To store configuration and sensitive data outside of the codebase.
*   **Key Variables:**
    *   `OPENAI_API_KEY`: **Required.** Your API key for OpenAI services.
    *   `BACKEND_URL`: The URL where the Python FastAPI backend is running. Used by the Next.js frontend. Defaults to `http://127.0.0.1:8000`.
    *   `CHROMA_DB_PATH` (Optional): Can be used to specify a custom path for the ChromaDB store (defaults to `papermind/store`).

### `papermind/tests/create_dummy.py`

*   **Purpose:** A utility script to generate a dummy PDF file (`dummy.pdf`) with sample hierarchical content.
*   **Functionality:**
    *   Uses `PyMuPDF (fitz)` to create a PDF with distinct chapters, sections, and varied text.
    *   This helps in testing the PDF parsing, chunking, and indexing pipeline without requiring users to immediately provide their own PDFs.
    *   Includes a fallback to create a simple `.txt` file if `PyMuPDF` encounters issues during PDF creation (e.g., if system dependencies for `fitz` are missing).

## Future Enhancements

*   **Groq Integration:** Swap out OpenAI providers for Groq.
*   **Dockerization:** Package the backend, vector store, and frontend into Docker containers for easier deployment using `docker-compose`.
*   **Improved Chunking:** More sophisticated heading detection and semantic chunking strategies.
*   **Reranking:** Add a reranking step after retrieval to improve context quality.
*   **Notifications Agent:** Implement an agent for background tasks or notifications.
*   **Fine-tuned Models:** Support for using locally hosted or fine-tuned embedding/LLM models.
*   **Frontend PDF Upload:** Allow users to upload PDFs directly through the web interface.
*   **Citation UX:** Enhance citation display (e.g., clickable icons linking to specific page context).
