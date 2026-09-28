# ruff: noqa
import base64
import datetime
import json
import os
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from google import genai
from google.cloud import firestore, storage
from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import App
from google.adk.code_executors import AgentEngineSandboxCodeExecutor
from google.adk.models import Gemini
from google.adk.tools import ToolContext
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.genai import types

from a2ui.schema.manager import A2uiSchemaManager
from a2ui.basic_catalog.provider import BasicCatalog
from app.a2ui_utils import a2ui_callback

load_dotenv()

# Hardcoded GCP Project ID per instructions
FIRESTORE_PROJECT = "qwiklabs-gcp-01-6346f35ae90a"
FIRESTORE_DATABASE = "destinations-db"

# Hardcoded GCS Bucket Name per instructions
GCS_BUCKET_NAME = "travel-concierge-media-6346f35a"

# Google Maps API key loaded from environment
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")

# Load Agent Engine resource name from deployment_metadata.json if available
AGENT_ENGINE_RESOURCE_NAME = None
metadata_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "deployment_metadata.json")
if os.path.exists(metadata_path):
    try:
        with open(metadata_path, "r") as f:
            metadata = json.load(f)
            AGENT_ENGINE_RESOURCE_NAME = metadata.get("remote_agent_runtime_id")
    except Exception as e:
        print(f"Warning: Could not read deployment_metadata.json: {e}")

# Initialize Agent Platform sandbox code executor
code_executor = AgentEngineSandboxCodeExecutor(
    agent_engine_resource_name=AGENT_ENGINE_RESOURCE_NAME
)


schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

a2ui_instruction = schema_manager.generate_system_prompt(
    role_description="You are Travel Concierge, a helpful AI travel assistant.",
    workflow_description="Analyze the request and return structured UI when appropriate.",
    ui_description=(
        "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows. "
        "Never nest a Card inside a Card. "
        "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use "
        "Table or Heading (unsupported), or Buttons, actions, or forms (they do "
        "nothing in adk web). "
        "You may include one Image component, but only when you have a public https "
        "URL for the image (for example the URL an image tool returns after uploading "
        "to a public bucket). Set the Image url to that exact https link, for example "
        "{\"Image\": {\"url\": {\"literalString\": \"https://...\"}}}. Never point an "
        "Image at a bare filename, an artifact name, or a non-http(s) path. If you do "
        "not have a public URL, add a short Text line noting the image instead. "
        "No markdown in text; use the usageHint property ('h1', 'h2', 'body') for "
        "headings and emphasis. "
        "Output ONLY the raw A2UI JSON array — no prose, and never wrap it in "
        "<a2a_datapart_json> tags or 'kind'/'data'/'metadata' objects. "
        "You remember the user's stated preferences, travel interests, dietary restrictions, and all user allergies across sessions using Memory Bank. "
        "Always check and respect all recalled user allergies and dietary restrictions when making dining, food, accommodation, or activity recommendations. "
        "You can execute Python code safely using your code execution capabilities to perform calculations and data analysis. "
        "Use `generate_destination_image` to generate travel destination photographs and save them to Cloud Storage. "
        "Use `generate_destination_video` to generate short video previews of travel destination spots using Gemini Omni (gemini-omni-flash-preview) in the global region. "
        "Use `geocode_address` to convert addresses into coordinates using Google Maps Geocoding API. "
        "Use `find_nearby_places` to find nearby restaurants, attractions, or lodging using Google Places API (New). "
        "Use `get_destination_info` to fetch background details for travel destinations. "
        "Use your Firestore tools (`search_destinations`, `add_destination`) to browse and add destination recommendations. "
        "Use `get_live_exchange_rate` to convert travel budgets into local destination currencies. "
        "Use `get_weather` and `get_current_time` to answer travel planning queries."
    ),
    include_schema=True,
    include_examples=True,
)


async def generate_memories_callback(callback_context: CallbackContext):
    """Callback to extract and save session memories to Memory Bank at turn completion."""
    await callback_context.add_session_to_memory()
    return None


def generate_destination_image(
    prompt: str,
    filename: str = "destination_spot.jpg",
    tool_context: ToolContext = None,
) -> str:
    """Generate an image for a travel destination spot using gemini-3.1-flash-lite-image in the global region.

    Saves the generated image as an artifact for Playground display, uploads the image bytes directly to Cloud Storage,
    and returns its public https URL.

    Args:
        prompt: Detailed description of the travel destination image to generate.
        filename: Optional filename for saving the image asset (e.g. 'kyoto_bamboo.jpg').

    Returns:
        The public HTTPS URL of the uploaded image in Cloud Storage.
    """
    client = genai.Client(vertexai=True, project=FIRESTORE_PROJECT, location="global")
    response = client.models.generate_content(
        model="gemini-3.1-flash-lite-image",
        contents=f"High quality scenic travel photograph of {prompt}",
        config=types.GenerateContentConfig(
            response_modalities=["TEXT", "IMAGE"],
        ),
    )

    image_part = None
    image_bytes = None
    for candidate in response.candidates:
        if candidate.content and candidate.content.parts:
            for part in candidate.content.parts:
                if part.inline_data and part.inline_data.data:
                    image_part = part
                    image_bytes = part.inline_data.data
                    break
        if image_bytes:
            break

    if not image_bytes:
        return f"Failed to generate image for prompt: '{prompt}'"

    if not filename.endswith(".jpg") and not filename.endswith(".png"):
        filename = f"{filename}.jpg"

    # 1. Save artifact if tool_context is provided so it appears in Playground Artifacts
    if tool_context:
        try:
            tool_context.save_artifact(filename=filename, artifact=image_part)
        except Exception as e:
            print(f"Warning: unable to save artifact: {e}")

    # 2. Upload image bytes directly to public Cloud Storage bucket
    try:
        storage_client = storage.Client(project=FIRESTORE_PROJECT)
        bucket = storage_client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(filename)
        blob.upload_from_string(image_bytes, content_type="image/jpeg")
        public_url = f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{filename}"
        return public_url
    except Exception as e:
        return f"Image generated, but failed to upload to Cloud Storage: {e}"


def generate_destination_video(
    prompt: str,
    filename: str = "destination_video.mp4",
    tool_context: ToolContext = None,
) -> str:
    """Generate a short video for a travel destination spot using Google's Omni model (gemini-omni-flash-preview) in the global region.

    Saves the generated video as an artifact for Playground display, uploads the video bytes directly to Cloud Storage,
    and returns its public https URL.

    Args:
        prompt: Detailed description of the travel destination video scene to generate.
        filename: Optional filename for saving the video asset (e.g. 'kyoto_bamboo.mp4').

    Returns:
        The public HTTPS URL of the uploaded video in Cloud Storage.
    """
    client = genai.Client(vertexai=True, project=FIRESTORE_PROJECT, location="global")
    video_bytes = None

    try:
        interaction = client.interactions.create(
            model="gemini-omni-flash-preview",
            input=f"Scenic travel video of {prompt}",
            response_format={"type": "video"},
        )
        if hasattr(interaction, "output_video") and interaction.output_video and getattr(interaction.output_video, "data", None):
            raw_data = interaction.output_video.data
            video_bytes = base64.b64decode(raw_data) if isinstance(raw_data, str) else raw_data
        elif hasattr(interaction, "outputs") and interaction.outputs:
            for out in interaction.outputs:
                if hasattr(out, "data") and out.data:
                    raw_data = out.data
                    video_bytes = base64.b64decode(raw_data) if isinstance(raw_data, str) else raw_data
                    break
    except Exception as e:
        print(f"Error calling gemini-omni-flash-preview: {e}")

    if not video_bytes:
        return f"Failed to generate video for prompt: '{prompt}'"

    if not filename.endswith(".mp4"):
        filename = f"{filename}.mp4"

    video_part = types.Part.from_bytes(data=video_bytes, mime_type="video/mp4")

    # 1. Save artifact if tool_context is provided so it appears in Playground Artifacts
    if tool_context:
        try:
            tool_context.save_artifact(filename=filename, artifact=video_part)
        except Exception as e:
            print(f"Warning: unable to save video artifact: {e}")

    # 2. Upload video bytes directly to public Cloud Storage bucket
    try:
        storage_client = storage.Client(project=FIRESTORE_PROJECT)
        bucket = storage_client.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(filename)
        blob.upload_from_string(video_bytes, content_type="video/mp4")
        public_url = f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{filename}"
        return public_url
    except Exception as e:
        return f"Video generated, but failed to upload to Cloud Storage: {e}"


def geocode_address(address: str) -> dict:
    """Turn a street address or landmark string into geographic coordinates using Google Maps Geocoding API.

    Args:
        address: The street address or landmark query (e.g. '1600 Amphitheatre Pkwy, Mountain View, CA' or 'Kyoto Station').

    Returns:
        A dictionary containing key fields: name, address, and location (latitude, longitude).
    """
    key = os.getenv("GOOGLE_MAPS_API_KEY", "")
    if not key or key == "PASTE_KEY_HERE":
        return {
            "error": "GOOGLE_MAPS_API_KEY is not set or contains placeholder. Please set a valid key in .env."
        }

    url = f"https://maps.googleapis.com/maps/api/geocode/json?address={urllib.parse.quote(address)}&key={key}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "TravelConciergeAgent/1.0"})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            if data.get("status") == "OK" and data.get("results"):
                res = data["results"][0]
                loc = res.get("geometry", {}).get("location", {})
                return {
                    "name": address,
                    "address": res.get("formatted_address", address),
                    "location": {
                        "latitude": loc.get("lat"),
                        "longitude": loc.get("lng"),
                    },
                }
            return {"error": f"Geocoding API status '{data.get('status')}': {data.get('error_message', 'No results found')}"}
    except Exception as e:
        return {"error": f"Failed to call Geocoding API: {e}"}


def find_nearby_places(
    latitude: float,
    longitude: float,
    place_type: str = "restaurant",
    radius_meters: float = 1000.0,
) -> list[dict]:
    """Find nearby places of a given type around a coordinate point using Google Places API (New).

    Args:
        latitude: Latitude of the center search point (e.g. 35.0115).
        longitude: Longitude of the center search point (e.g. 135.7681).
        place_type: Place type filter (e.g. 'restaurant', 'tourist_attraction', 'cafe', 'lodging').
        radius_meters: Search circle radius in meters (max 50000.0, default 1000.0).

    Returns:
        A list of dictionaries containing key fields: name, address, location.
    """
    key = os.getenv("GOOGLE_MAPS_API_KEY", "")
    if not key or key == "PASTE_KEY_HERE":
        return [{
            "error": "GOOGLE_MAPS_API_KEY is not set or contains placeholder. Please set a valid key in .env."
        }]

    url = "https://places.googleapis.com/v1/places:searchNearby"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": key,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.location",
    }
    body = {
        "includedTypes": [place_type],
        "maxResultCount": 5,
        "locationRestriction": {
            "circle": {
                "center": {"latitude": latitude, "longitude": longitude},
                "radius": radius_meters,
            }
        },
    }

    try:
        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            places = data.get("places", [])
            results = []
            for p in places:
                display = p.get("displayName", {}).get("text", "")
                addr = p.get("formattedAddress", "")
                loc = p.get("location", {})
                results.append({
                    "name": display,
                    "address": addr,
                    "location": {
                        "latitude": loc.get("latitude"),
                        "longitude": loc.get("longitude"),
                    },
                })
            return results
    except Exception as e:
        return [{"error": f"Failed to call Places API (New): {e}"}]


def search_destinations(city: str = None, category: str = None, max_budget: float = None) -> list[dict]:
    """Search travel destinations in the catalog stored in Firestore.

    Args:
        city: Optional city or location filter (e.g. 'Kyoto', 'Amalfi', 'Banff').
        category: Optional category filter (e.g. 'Culture & Nature', 'Coastline & Romance', 'Adventure & Wildlife').
        max_budget: Optional maximum estimated daily budget in USD.

    Returns:
        List of destination dictionaries matching the query parameters.
    """
    db = firestore.Client(project=FIRESTORE_PROJECT, database=FIRESTORE_DATABASE)
    docs = db.collection("destinations").stream()

    results = []
    for doc in docs:
        data = doc.to_dict()
        if city and city.lower() not in data.get("city", "").lower() and city.lower() not in data.get("name", "").lower():
            continue
        if category and category.lower() not in data.get("category", "").lower():
            continue
        if max_budget is not None and data.get("estimated_daily_budget_usd", 0.0) > max_budget:
            continue
        results.append(data)

    return results


def add_destination(
    name: str,
    city: str,
    country: str,
    category: str,
    description: str,
    estimated_daily_budget_usd: float,
    best_season: str = "Year-round",
    rating: float = 4.8,
) -> str:
    """Add a new travel destination spot to the Firestore catalog.

    Args:
        name: Name of the landmark or spot.
        city: City where the spot is located.
        country: Country where the spot is located.
        category: Travel category (e.g. 'Culture & Nature', 'Food & Dining', 'Adventure').
        description: A compelling description of the attraction.
        estimated_daily_budget_usd: Estimated daily budget required in USD.
        best_season: Best season to visit.
        rating: Rating out of 5.0.

    Returns:
        A success confirmation message with the generated destination ID.
    """
    db = firestore.Client(project=FIRESTORE_PROJECT, database=FIRESTORE_DATABASE)
    doc_ref = db.collection("destinations").document()

    item = {
        "id": doc_ref.id,
        "name": name,
        "city": city,
        "country": country,
        "category": category,
        "description": description,
        "estimated_daily_budget_usd": estimated_daily_budget_usd,
        "best_season": best_season,
        "rating": rating,
    }
    doc_ref.set(item)
    return f"Successfully added '{name}' in {city}, {country} (ID: {doc_ref.id}) to the destinations catalog."


def get_destination_info(destination_name: str) -> str:
    """Fetch real-time encyclopedic travel background and summary information for a destination spot or city.

    Args:
        destination_name: Name of the city, landmark, or attraction (e.g., 'Kyoto', 'Amalfi Coast', 'Colosseum').

    Returns:
        A summary string containing official background information.
    """
    formatted_title = destination_name.strip().replace(" ", "_")
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(formatted_title)}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "TravelConciergeAgent/1.0"})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            title = data.get("title", destination_name)
            extract = data.get("extract")
            if extract:
                return f"Summary for {title}: {extract}"
            return f"No summary extract available for '{destination_name}'."
    except Exception as e:
        return f"Unable to fetch info for '{destination_name}': {e}"


def get_live_exchange_rate(base_currency: str = "USD", target_currency: str = "JPY") -> str:
    """Fetch live currency exchange rates from an open public exchange rate API.

    Args:
        base_currency: The source 3-letter currency code (e.g. 'USD', 'EUR', 'GBP').
        target_currency: The target 3-letter currency code (e.g. 'JPY', 'EUR', 'CAD').

    Returns:
        A string summarizing the current exchange rate and converted value.
    """
    base = base_currency.upper()
    target = target_currency.upper()
    url = f"https://open.er-api.com/v6/latest/{base}"

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            rates = data.get("rates", {})
            if target in rates:
                rate = rates[target]
                return f"1 {base} = {rate:.2f} {target} (Live Rate). Example: 100 {base} = {100 * rate:.2f} {target}."
            return f"Currency '{target}' not found in exchange rate response for {base}."
    except Exception as e:
        return f"Unable to fetch live exchange rate: {e}"


def get_weather(query: str) -> str:
    """Simulates getting information on weather.

    Args:
        query: A string containing the location to get weather information for.

    Returns:
        A string with the simulated weather information for the queried location.
    """
    if "kyoto" in query.lower():
        return "It's 68°F (20°C), sunny with mild autumn breeze in Kyoto."
    elif "amalfi" in query.lower():
        return "It's 75°F (24°C), clear skies along the Amalfi Coast."
    elif "banff" in query.lower():
        return "It's 55°F (13°C), crisp and clear in Banff."
    elif "sf" in query.lower() or "san francisco" in query.lower():
        return "It's 60°F and foggy in San Francisco."
    return f"Weather for {query}: 72°F and pleasant."


def get_current_time(query: str) -> str:
    """Simulates getting the current time for a location query.

    Args:
        query: The name of the city or location to get the current time for.

    Returns:
        A string with the current time information.
    """
    if "kyoto" in query.lower() or "japan" in query.lower():
        tz_identifier = "Asia/Tokyo"
    elif "amalfi" in query.lower() or "italy" in query.lower():
        tz_identifier = "Europe/Rome"
    elif "banff" in query.lower() or "canada" in query.lower():
        tz_identifier = "America/Edmonton"
    elif "sf" in query.lower() or "san francisco" in query.lower():
        tz_identifier = "America/Los_Angeles"
    else:
        tz_identifier = "UTC"

    tz = ZoneInfo(tz_identifier)
    now = datetime.datetime.now(tz)
    return f"Current time for {query}: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}"


root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model="gemini-2.5-flash",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    code_executor=code_executor,
    instruction=a2ui_instruction,
    tools=[
        PreloadMemoryTool(),
        generate_destination_image,
        generate_destination_video,
        geocode_address,
        find_nearby_places,
        get_destination_info,
        search_destinations,
        add_destination,
        get_live_exchange_rate,
        get_weather,
        get_current_time,
    ],
    after_agent_callback=generate_memories_callback,
    after_model_callback=a2ui_callback,
)

app = App(
    root_agent=root_agent,
    name="app",
)
