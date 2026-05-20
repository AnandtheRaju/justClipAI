import json
import re
import sys
import os
import time
import requests
import mimetypes
from dotenv import load_dotenv

load_dotenv()

print("Debug: Script started")

if len(sys.argv) != 4:
    print("Usage: python generate_timestamps.py <video_file> <output_json_file> <prompt_text>")
    sys.exit(1)

video_file_name = sys.argv[1]
output_json_file = sys.argv[2]
prompt_text = sys.argv[3]

print(f"Debug: Video path = {video_file_name}")
print(f"Debug: Output JSON path = {output_json_file}")
print(f"Debug: Prompt text = {prompt_text}")

if not os.path.exists(video_file_name):
    print(f" Video file not found at path: {video_file_name}")
    sys.exit(1)

API_KEY = os.getenv("GEMINI_API_KEY")
file_size_mb = os.path.getsize(video_file_name) / (1024 * 1024)
print(f"Debug: File size: {file_size_mb:.2f} MB")


print("\nDebug: Uploading video via REST API...")
mime_type, _ = mimetypes.guess_type(video_file_name)
if not mime_type:
    mime_type = "video/mp4"


upload_url = f"https://generativelanguage.googleapis.com/upload/v1beta/files?key={API_KEY}"
headers = {
    "X-Goog-Upload-Protocol": "resumable",
    "X-Goog-Upload-Command": "start",
    "X-Goog-Upload-Header-Content-Length": str(os.path.getsize(video_file_name)),
    "X-Goog-Upload-Header-Content-Type": mime_type,
    "Content-Type": "application/json"
}

metadata = {
    "file": {
        "display_name": "dashcam_analysis"
    }
}

try:
    print("   Step 1: Initiating upload session...")
    response = requests.post(upload_url, headers=headers, json=metadata)
    
    if response.status_code not in [200, 201]:
        print(f" Failed to initiate upload: {response.status_code}")
        print(f"Response: {response.text}")
        sys.exit(1)
    
    upload_session_url = response.headers.get("X-Goog-Upload-URL")
    if not upload_session_url:
        print(" No upload URL received")
        print(f"Headers: {response.headers}")
        sys.exit(1)
    
    print(f"Upload session created")
    
   
    print("   Step 2: Uploading video data (this may take a minute)...")
    with open(video_file_name, 'rb') as f:
        video_data = f.read()
    
    upload_headers = {
        "Content-Length": str(len(video_data)),
        "X-Goog-Upload-Offset": "0",
        "X-Goog-Upload-Command": "upload, finalize"
    }
    
    upload_response = requests.post(
        upload_session_url,
        headers=upload_headers,
        data=video_data
    )
    
    if upload_response.status_code not in [200, 201]:
        print(f"Upload failed: {upload_response.status_code}")
        print(f"Response: {upload_response.text}")
        sys.exit(1)
    
    file_info = upload_response.json()
    file_uri = file_info['file']['uri']
    file_name = file_info['file']['name']
    
    print(f" Video uploaded successfully")
    print(f"   File URI: {file_uri}")
    
except Exception as e:
    print(f" Upload error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)


print("\nDebug: Waiting for video processing", end="")
get_file_url = f"https://generativelanguage.googleapis.com/v1beta/{file_name}?key={API_KEY}"
max_wait = 300
wait_time = 0

while wait_time < max_wait:
    time.sleep(3)
    wait_time += 3
    print(".", end="", flush=True)
    
    try:
        check_response = requests.get(get_file_url)
        if check_response.status_code == 200:
            file_status = check_response.json()
            state = file_status.get('state', 'UNKNOWN')
            
            if state == "ACTIVE":
                print("\n Video processing complete!")
                break
            elif state == "FAILED":
                print("\n Video processing failed")
                sys.exit(1)
    except Exception as e:
        print(f"\n Error checking status: {e}")
        break

if wait_time >= max_wait:
    print("\n Timeout waiting for processing, attempting analysis anyway...")


print("\nDebug: Analyzing video with Gemini...")

prompt = f"""{prompt_text}

Analyze the entire video and identify all occurrences.
Return ONLY a JSON array with timestamps in SECONDS.
Each detection should have "start" and "end" keys with numeric values.

Format:
[
  {{"start": 10.5, "end": 15.2}},
  {{"start": 45.0, "end": 52.3}}
]

If nothing is detected, return: []
"""

model_name = os.getenv("model_name", "gemini-2.5-flash")
generate_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={API_KEY}"
print(f"   Using model: {model_name}")

request_body = {
    "contents": [{
        "parts": [
            {"text": prompt},
            {"file_data": {
                "mime_type": mime_type,
                "file_uri": file_uri
            }}
        ]
    }],
    "generationConfig": {
        "temperature": 0.1,
        "topK": 32,
        "topP": 1
    }
}

try:
    print("   Sending analysis request (may take 30-60 seconds)...")
    gen_response = requests.post(
        generate_url,
        headers={"Content-Type": "application/json"},
        json=request_body,
        timeout=300
    )
    
    if gen_response.status_code != 200:
        print(f" Generation failed: {gen_response.status_code}")
        print(f"Response: {gen_response.text}")
        sys.exit(1)
    
    result = gen_response.json()
    
    if 'candidates' not in result or not result['candidates']:
        print(" No response generated")
        print(f"Result: {result}")
        sys.exit(1)
    
    output_text = result['candidates'][0]['content']['parts'][0]['text']
    print("Received response")
    
except Exception as e:
    print(f"Analysis error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)


print(f"\n{'='*60}")
print("Raw Gemini Output:")
print(f"{'='*60}")
print(output_text[:1000] + ('...' if len(output_text) > 1000 else ''))
print(f"{'='*60}\n")


clean_text = output_text.strip()
clean_text = re.sub(r'^```json\s*', '', clean_text, flags=re.IGNORECASE | re.MULTILINE)
clean_text = re.sub(r'^```\s*', '', clean_text, flags=re.MULTILINE)
clean_text = re.sub(r'```\s*$', '', clean_text, flags=re.MULTILINE)
clean_text = clean_text.strip()

if not clean_text.startswith('['):
    match = re.search(r'\[.*?\]', clean_text, re.DOTALL)
    if match:
        clean_text = match.group(0)

try:
    timestamps = json.loads(clean_text)
    
    if not isinstance(timestamps, list):
        raise ValueError(f"Expected list, got {type(timestamps).__name__}")
    
   
    valid = []
    for item in timestamps:
        if isinstance(item, dict) and "start" in item and "end" in item:
            try:
                start = float(item["start"])
                end = float(item["end"])
                if start >= 0 and end > start:
                    valid.append({"start": start, "end": end})
            except (ValueError, TypeError):
                pass
    
    # Save results
    with open(output_json_file, "w", encoding="utf-8") as f:
        json.dump(valid, f, indent=2)
    
    print(f"{'='*60}")
    print(f" SUCCESS!")
    print(f"{'='*60}")
    print(f"Output saved to: {output_json_file}")
    print(f"Total detections: {len(valid)}")
    
    if valid:
        print(f"\nDetected occurrences:")
        for i, ts in enumerate(valid[:10], 1):
            print(f"  {i}. {ts['start']:.1f}s - {ts['end']:.1f}s")
        if len(valid) > 10:
            print(f"  ... and {len(valid) - 10} more")
    else:
        print("\nNo occurrences detected")
    
    print(f"\n{'='*60}")
    
except json.JSONDecodeError as e:
    print(f" JSON Parse Error: {e}")
    with open("error.txt", "w") as f:
        f.write(f"Original:\n{output_text}\n\nCleaned:\n{clean_text}")
    sys.exit(1)














