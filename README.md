# Video Media Encoder Server

## Overview

This project is a **high-performance video encoding server** built with Python, leveraging **FFmpeg** for video processing. It supports **AWS S3 for cloud storage** and **MongoDB for tracking encoding jobs**. The server includes a **JSON-RPC API** to monitor encoding progress in real-time.

## Features

- **High-speed video encoding** using FFmpeg.
- **Cloud integration** with AWS S3 for input/output storage.
- **Real-time status tracking** via a JSON-RPC API.
- **Multi-threaded processing** for efficiency.
- **Automatic cleanup** of processed files to save storage.
- **Flexible output formats** with configurable codecs.

## Project Structure

```
📂 VideoEncoderServer
 ├── main.py  # Core server logic and FFmpeg integration
 ├── requirements.txt  # Dependencies
 ├── dockerfile # Script to build a minimal image
 ├── README.md  # This file
 ├── LICENSE # Legalise
 └── .env  # Environment variables (not included in repo)
```

## Setup & Installation

### Use docker build

## or

### Prerequisites

Ensure you have the following installed:

- Python 3.8+
- FFmpeg
- MongoDB instance

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Environment Configuration

Create a `.env` file with the following:

```ini
AWS_SDK_ACCESS_KEY=your_access_key
AWS_SDK_SECRET_KEY=your_secret_key
S3_BUCKET_IN=your_input_bucket
S3_BUCKET_OUT=your_output_bucket
DB_HOST=mongodb://your_db_host
DB_NAME=your_db_name
DB_TABLE_FILES=your_collection
OBJECT_NAME=input_video.mp4
OUTPUT_FORMAT=mp4
OUTPUT_EXT=.mp4
VIDEO_CODEC=libx264
AUDIO_CODEC=aac
```

### Run the Server

```bash
python main.py
```

The server will start and listen for encoding jobs.

## API Usage

The server provides a JSON-RPC API for checking encoding status.

### Get Encoding Status

#### Request

```json
{
    "jsonrpc": "2.0",
    "method": "get_status",
    "id": 1
}
```

#### Example Response

```json
{
    "jsonrpc": "2.0",
    "result": {"framesProcessed": 120, "totalFrames": 500},
    "id": 1
}
```

## How It Works

1. The server retrieves a video file from **AWS S3**.
2. **FFmpeg** processes the file according to the specified format and codecs.
3. The output is streamed to **AWS S3** for storage.
4. **MongoDB** updates the encoding job status in real-time.
5. Users can query the server to check progress.
6. Once completed, the input file is automatically deleted.

## License

This project is licensed under the **MIT License**.

