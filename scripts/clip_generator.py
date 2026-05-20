import sys
import json
import os
from moviepy.video.io.VideoFileClip import VideoFileClip

def main():
    # Expect 3 or 4 args now (3 required: input_video, timestamps_json_file, output_folder)
    if len(sys.argv) != 4:
        print("Usage: python clip_generator.py <input_video> <timestamps_json_file> <output_folder>")
        print("Example: python clip_generator.py dashcam2.mp4 timestamps.json C:/FYP/video_clips/")
        sys.exit(1)

    input_video = sys.argv[1]
    timestamps_file = sys.argv[2]
    output_folder = sys.argv[3]

    # Ensure output folder exists
    os.makedirs(output_folder, exist_ok=True)

    # Validate input files
    if not os.path.isfile(input_video):
        print(f" Video file not found: {input_video}")
        sys.exit(1)

    if not os.path.isfile(timestamps_file):
        print(f" JSON file not found: {timestamps_file}")
        sys.exit(1)

    # Load timestamps
    try:
        with open(timestamps_file, 'r', encoding='utf-8') as f:
            timestamps = json.load(f)
    except json.JSONDecodeError as e:
        print(f" Error parsing JSON file: {e}")
        sys.exit(1)

    print(f" Loading video: {input_video}")
    video = VideoFileClip(input_video)

    # Process each segment
    for i, seg in enumerate(timestamps, start=1):
        start_time = seg.get('start')
        end_time = seg.get('end')

        if start_time is None or end_time is None:
            print(f" Skipping segment {i} because start or end is missing")
            continue

        if start_time == end_time:
            end_time += 0.6

        print(f" Clipping segment {i}: {start_time}s -> {end_time}s")

        subclip = video.subclipped(start_time, end_time)
        output_file = os.path.join(output_folder, f"clip_{i}.mp4")
        subclip.write_videofile(output_file, codec="libx264", audio_codec="aac")

    print(f"\n All clips have been generated in: {output_folder}")

if __name__ == "__main__":
    main()