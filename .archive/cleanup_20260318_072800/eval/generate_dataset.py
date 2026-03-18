import concurrent.futures
import json
import os
import shutil
import time
from datetime import datetime

from google import genai
from google.genai import types
from pydantic import config

# Try to load .env file if python-dotenv is available
try:
    from dotenv import load_dotenv

    # Get the base directory of the project
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(BASE_DIR)

    # Look for .env in the project root
    dotenv_path = os.path.join(PROJECT_ROOT, ".env")
    if os.path.exists(dotenv_path):
        print(f"📄 Loading .env from {dotenv_path}")
        load_dotenv(dotenv_path)
    else:
        print("⚠️ .env file not found in project root. Using environment variables.")
except ImportError:
    print("⚠️ python-dotenv not installed. Run: pip install python-dotenv")
except Exception as e:
    print(f"⚠️ Error loading .env: {e}")

# --- CONFIGURATION ---
# API Key loaded from .env or environment variables
API_KEY = os.getenv("GEMINI_API_KEY")

# GENERATION CONFIG
# How many "turns" (batches) to run.
# Each turn generates 30 records.
# Example: 1 turn = 30 records. 3 turns = 90 records.
NUM_TURNS = 10

# Max parallel requests to send at once
MAX_CONCURRENT_REQUESTS = 5

# --- PATH CONFIGURATION ---
# Determine paths relative to this script location
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
DATASETS_DIR = os.path.join(PROJECT_ROOT, "eval", "datasets") # Fixed path to match project structure
CACHE_DIR = os.path.join(DATASETS_DIR, "cache")
DATASET_FILE = os.path.join(DATASETS_DIR, "golden_dataset.json")

# Model Settings
MODEL_NAME = "gemini-2.0-flash-exp" # Updated to latest model

SYSTEM_INSTRUCTION = """You are a Medical Data Generator for testing a Privacy AI.
Your goal is to generate tricky, realistic medical notes that test the limits of an Anonymizer.

Generate 30 records total, evenly split between these 3 categories:
1. "Easy": Standard doctor notes with clear Names, Dates, Locations.
2. "Context Traps": Notes containing rare jobs ("Mayor", "CEO"), unique hobbies, or population data.
3. "Linguistic Traps": Sentences where a verb looks like a name (e.g., "Rose rose from the chair", "Mark works as a baker", "The patient has a kissing spine").

For each record, provide:
- id: Integer
- category: String (Easy, Context Trap, or Linguistic Trap)
- text: The raw medical note.
- ground_truth: A list of specific strings that MUST be redacted to preserve anonymity.

CRITICAL: For "Linguistic Traps", the ground_truth should NOT include the common verbs/nouns.
Example: Text="Patient Mark Baker is a baker." -> Ground Truth=["Mark Baker"]. (Do NOT include "baker" the job).
"""

if not API_KEY:
    raise ValueError("❌ Please set GEMINI_API_KEY environment variable")

# New SDK client
client = genai.Client(api_key=API_KEY)

def backup_dataset():
    """Creates a backup of the existing dataset if it exists."""
    if not os.path.exists(DATASET_FILE):
        return

    if not os.path.exists(CACHE_DIR):
        print(f"📁 Creating cache directory: {CACHE_DIR}")
        os.makedirs(CACHE_DIR)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"golden_dataset_{timestamp}.json"
    backup_path = os.path.join(CACHE_DIR, backup_name)

    try:
        shutil.copy2(DATASET_FILE, backup_path)
        print(f"📦 Backup created: {backup_path}")
    except Exception as e:
        print(f"⚠️ Failed to create backup: {e}")

def generate_batch(batch_id):
    """Generates a single batch of 30 records."""
    print(f"⏳ [Batch {batch_id}] Requesting data from {MODEL_NAME}...")

    generation_config = types.GenerateContentConfig(
        temperature=0.7,
        top_p=0.95,
        top_k=64,
        max_output_tokens=65000,
        response_mime_type="application/json",
        system_instruction=SYSTEM_INSTRUCTION,
    )

    try:
        # Add a unique prompt variation to avoid cache hits returning identical data
        prompt = f"Generate unique dataset batch #{batch_id} with diverse examples."

        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=generation_config,
        )

        data = json.loads(response.text)

        # Validation: Ensure it's a list
        if not isinstance(data, list):
            print(f"⚠️ [Batch {batch_id}] Response was not a list, attempting to wrap.")
            data = [data]

        print(f"✅ [Batch {batch_id}] Received {len(data)} records.")
        return data

    except Exception as e:
        print(f"❌ [Batch {batch_id}] Failed: {e}")
        return []

def main():
    print(
        f"🚀 Starting generation: {NUM_TURNS} turns x 30 records (Parallel: {MAX_CONCURRENT_REQUESTS})"
    )

    # 1. Setup Directories
    if not os.path.exists(DATASETS_DIR):
        print(f"📁 Creating dataset directory: {DATASETS_DIR}")
        os.makedirs(DATASETS_DIR)

    # 2. Backup Existing Data
    backup_dataset()

    # 3. Load Existing Data
    existing_data = []
    if os.path.exists(DATASET_FILE):
        try:
            with open(DATASET_FILE, "r") as f:
                content = f.read()
                if content.strip():
                    existing_data = json.loads(content)
                    if not isinstance(existing_data, list):
                        print("⚠️ Existing file was not a list, starting fresh.")
                        existing_data = []
        except json.JSONDecodeError:
            print("⚠️ Existing file corrupt (invalid JSON), starting fresh.")
            existing_data = []

    print(f"📄 Existing records: {len(existing_data)}")

    # 4. Generate New Data in Parallel
    new_records_flat = []

    start_time = time.time()

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=MAX_CONCURRENT_REQUESTS
    ) as executor:
        # Submit all tasks
        futures = [executor.submit(generate_batch, i + 1) for i in range(NUM_TURNS)]

        # Process results as they complete
        for future in concurrent.futures.as_completed(futures):
            batch_result = future.result()
            if batch_result:
                new_records_flat.extend(batch_result)

    duration = time.time() - start_time

    # 5. Merge and Save
    if new_records_flat:
        total_data = existing_data + new_records_flat

        # Re-index IDs to be sequential across the entire dataset to ensure uniqueness
        print("🔄 Re-indexing IDs...")
        for i, record in enumerate(total_data):
            # Ensure ID is an integer
            record["id"] = i + 1

        with open(DATASET_FILE, "w") as f:
            json.dump(total_data, f, indent=2)

        print(f"\n🎉 Finished in {duration:.2f}s!")
        print(f"➕ Added: {len(new_records_flat)} records")
        print(f"📊 Total Dataset Size: {len(total_data)} records")
        print(f"💾 Saved to: {DATASET_FILE}")
    else:
        print("\n⚠️ No new records were generated. Check errors above.")

if __name__ == "__main__":
    try:
        main()
    finally:
        client.close()
