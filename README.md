# Travel Concierge Agent

An intelligent, multi-modal travel planning agent built with the **Google Agent Development Kit (ADK)**, powered by **Gemini 2.5 Flash**, **Imagen 3**, **Gemini Omni**, **Vertex AI Memory Bank**, and **Google Cloud Platform (GCP)** services.

![Travel Concierge Agent Demo](demo.gif)

---

## 🌟 Overview

The **Travel Concierge Agent** helps users discover destinations, plan multi-day itineraries, estimate travel budgets, search curated destination databases, generate scenic destination photos and videos, look up nearby attractions via Google Maps, and manage personal travel preferences across sessions.

---

## 🛠️ Implemented Features & Architecture

This repository implements the following production features and Google Cloud integrations:

### 🧠 Core Intelligence & Long-Term Memory
* **Gemini 2.5 Flash (`gemini-2.5-flash`)**: Primary ReAct reasoning engine handling natural language travel planning, itinerary generation, and tool selection.
* **Vertex AI Memory Bank (`PreloadMemoryTool` & Callbacks)**: Persists user travel preferences, dietary restrictions, budget targets, and past trips across session boundaries.
* **Agent Engine Sandbox Code Executor (`AgentEngineSandboxCodeExecutor`)**: Executes Python code in a secure sandbox to perform precise currency math, budget totals, and date calculations.

### 🖼️ Multi-Modal Media Generation
* **Imagen 3 (`imagen-3.0-generate-002`)**: Generates high-resolution destination photographs (`generate_destination_image`) on-demand.
* **Gemini Omni Video Model (`gemini-omni-flash-preview`)**: Generates short video previews (`generate_destination_video`) of travel spots in the `global` region.
* **Google Cloud Storage Integration**: Uploads generated media directly from memory to a public GCS bucket (`travel-concierge-media-6346f35a`), returning shareable HTTPS URLs and saving assets to Playground Artifacts.

### 🗄️ Database & Spatial Services
* **Google Cloud Firestore Database (`destinations-db`)**: Stores and queries curated destination records (`search_destinations`, `add_destination`).
* **Google Maps Geocoding API (`geocode_address`)**: Converts addresses and landmark names into geographic latitude/longitude coordinates.
* **Google Places API New (`find_nearby_places`)**: Finds nearby restaurants, lodging, points of interest, and attractions for any destination.

### 🎨 Rich UI & Utilities
* **A2UI (Agent to User Interface)**: Uses `A2uiSchemaManager` and `BasicCatalog` to emit interactive display cards (tables, summary cards, row layouts) rendered natively by the frontend.
* **Live Travel Tools**: Fetches current currency exchange rates (`get_live_exchange_rate`), weather conditions (`get_weather`), and local time zones (`get_current_time`).

---

## 📌 Planned Features (Not Yet Implemented)

* **Flight Booking & GDS Engine**: *Planned, not yet implemented* (requires GDS/airline API integration).
* **Real-time Hotel Checkout & Payments**: *Planned, not yet implemented* (requires merchant gateway integration).

---

## 🚀 Setup & Local Running Instructions

### Prerequisites
* Python 3.10+
* Google Cloud SDK (`gcloud`) authenticated with access to Vertex AI, Firestore, and Cloud Storage.
* `uv` or `pip` package manager.

### 1. Install Dependencies
```bash
# Using uv (recommended):
uv sync

# Or using pip:
pip install -e .
```

### 2. Set Environment Variables
```bash
export GOOGLE_CLOUD_PROJECT="<your-gcp-project-id>"
export GOOGLE_CLOUD_LOCATION="us-east1"
export GOOGLE_GENAI_USE_VERTEXAI="true"
export GOOGLE_MAPS_API_KEY="<your-google-maps-api-key>"
```

### 3. Seed Firestore Database (Optional)
```bash
uv run python seed_db.py
```

### 4. Run Agent Development Playground
Launch the local ADK Web development server to interact with the agent:
```bash
uv run agents-cli playground
```

### 5. Run the Custom Frontend Proxy
To run the custom FastAPI chat frontend locally:
```bash
cd frontend
pip install -r requirements.txt
export AGENT_ENGINE_RESOURCE_NAME="projects/<PROJECT_ID>/locations/us-east1/reasoningEngines/<ENGINE_ID>"
export AGENT_DIRECTORY="app"
python main.py
```

---

## 📄 License
Apache License 2.0
