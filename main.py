import os
import re
import sys
import atexit
import requests
import platform
import threading

# Cloud stuff
import boto3
from smart_open import open as s3_open

# Encoder stuff
import ffmpeg

# Database
from pymongo import MongoClient

# RPC stuff
from werkzeug.wrappers import Request, Response
from wsgiref.simple_server import make_server

from jsonrpc import JSONRPCResponseManager, dispatcher

# Adjust for speed or resource usage
file_chunk_size = 16384


def get_os():
    return platform.system()


def debug_print(line) -> None:
    try:
        env = os.environ.get('NODE_ENV', None)

        if env == 'development':
            print(line)

        if get_os() == "Linux":
            print(line)
        elif os.name == "posix" and sys.platform.startswith("linux"):
            print(line)

    except KeyError:
        pass


access_key = os.environ['AWS_SDK_ACCESS_KEY']
secret_key = os.environ['AWS_SDK_SECRET_KEY']

s3 = boto3.client('s3',
                  aws_access_key_id=access_key,
                  aws_secret_access_key=secret_key)

# This is our S3 Bucket name
bucket_in_name = os.environ.get('S3_BUCKET_IN')
bucket_out_name = os.environ.get('S3_BUCKET_OUT')

# Info about the video file
input_object_name = os.environ.get('OBJECT_NAME')
output_object_format = os.environ.get('OUTPUT_FORMAT')
output_object_ext = os.environ.get('OUTPUT_EXT')

client = MongoClient(os.environ.get('DB_HOST'))
db = client[os.environ['DB_NAME']]
collection = db[os.environ['DB_TABLE_FILES']]

# Encode status
total_frames = 1
status = [0, 0]
status_lock = threading.Lock()


def get_status():
    status_lock.acquire()
    global status
    result = {'framesProcessed': status[0], 'totalFrames': total_frames}
    status_lock.release()
    return result


@Request.application
def application(request):
    # Dispatcher is dictionary {<method_name>: callable}
    dispatcher["get_status"] = get_status

    response = JSONRPCResponseManager.handle(
        request.data, dispatcher)
    return Response(response.json, mimetype='application/json')


def setup_path():
    path_list = os.environ['PATH'].split(os.pathsep)

    new_path = os.path.abspath('./ffmpeg')

    if new_path not in path_list:
        path_list.append(new_path)
        os.environ['PATH'] = os.pathsep.join(path_list)


def read_stdout(process) -> None:
    stream = process.stdout
    with s3_open(f's3://{access_key}:{secret_key}@{bucket_out_name}/{input_object_name}', 'wb') as s3_out:
        while process.poll() is None:
            bytes_peek = stream.peek(file_chunk_size)
            bytes_read = stream.read(len(bytes_peek))
            s3_out.write(bytes_read)


def extract_frame_fps(log_line):
    match = re.search(r'frame=\s*(\d+).*?fps=\s*(\d+)', log_line)
    if match:
        frame = int(match.group(1))
        fps = int(match.group(2))
        return frame, fps
    return 0, 0


def read_stderr(process) -> None:
    stream = process.stderr

    while process.poll() is None:
        bytes_peek = stream.peek(4096)
        bytes_read = stream.read(len(bytes_peek))

        log_line = bytes_read.decode('utf-8')
        frame, fps = extract_frame_fps(log_line)

        if frame > 0:
            status_lock.acquire()
            global status
            status = [frame, fps]
            status_lock.release()

        if len(log_line) > 0:
            debug_print(log_line)


def clean_up() -> None:
    if os.path.exists(input_object_name):
        os.remove(input_object_name)
        debug_print(f'File Deleted: {input_object_name}')
    else:
        debug_print(f'File Not Found: {input_object_name}')

    try:
        response = s3.delete_object(Bucket=bucket_in_name, Key=input_object_name)
        debug_print(f"Object '{input_object_name}' deleted successfully from bucket '{bucket_in_name}'")
        debug_print(response)
    except Exception as e:
        debug_print(f"Error deleting object: {e}")


def conversion_failed() -> None:
    try:
        debug_print("Failed to convert cleaning up artifacts.")
        response = s3.delete_object(Bucket=bucket_out_name, Key=input_object_name)
        debug_print(f"Object '{input_object_name}' deleted successfully from bucket '{bucket_out_name}'")
        debug_print(response)
    except Exception as e:
        debug_print(f"Error deleting object: {e}")


class StoppableWSGIServer:
    def __init__(self, host, port, app):
        self.httpd = make_server(host, port, app)
        self.host = host
        self.running = False
        self.server_thread = None

    def start(self):
        self.running = True
        self.server_thread = threading.Thread(target=self._serve, daemon=True)
        self.server_thread.start()

    def _serve(self):
        while self.running:
            self.httpd.handle_request()  # Handle one request at a time

    def shutdown(self):
        self.running = False
        try:
            # Sending a dummy request to wake up `handle_request()`
            requests.get(f"http://{self.host}:{self.httpd.server_port}/")
        except requests.exceptions.RequestException:
            pass  # Ignore errors if the server isn't fully started yet


def main():
    # Register clean up first
    atexit.register(clean_up)

    # Create the rpc server
    server = StoppableWSGIServer('0.0.0.0', 5000, application)
    server.start()

    # Setup path to ffmpeg on windows
    if get_os() == 'Windows':
        setup_path()

    # Needed for total frames in file if we do not care about this we can save io
    with s3_open(f's3://{access_key}:{secret_key}@{bucket_in_name}/{input_object_name}', 'rb') as s3_src:
        with open(input_object_name, 'wb') as s3_dest:
            while True:
                data = s3_src.read(file_chunk_size)
                if not data:
                    break
                s3_dest.write(data)

    json_data = ffmpeg.probe(input_object_name)

    global total_frames

    total_frames = 1
    num_streams = json_data['format']['nb_streams']

    for i in range(0, num_streams):
        if json_data['streams'][i]['codec_type'] == 'video':
            try:
                total_frames = int(json_data['streams'][i]['nb_frames'])
            except KeyError:
                total_frames = 1

    process = (
        ffmpeg
        .input(input_object_name)
        .output('pipe:',
                format=output_object_format,
                sn=None,
                vcodec=os.environ['VIDEO_CODEC'],
                acodec=os.environ['AUDIO_CODEC'])
        .run_async(pipe_stdout=True, pipe_stderr=True)
    )

    stdout_thread = threading.Thread(target=read_stdout, args=(process,))
    stdout_thread.start()
    stderr_thread = threading.Thread(target=read_stderr, args=(process,))
    stderr_thread.start()

    # Join threads for graceful exit
    stdout_thread.join()
    stderr_thread.join()

    if process.poll() == 0:
        collection.update_one({'key': input_object_name}, {'$set': {'status': 'complete'}})
    else:
        collection.update_one({'key': input_object_name}, {'$set': {'status': 'failed'}})
        conversion_failed()

    server.shutdown()


if __name__ == "__main__":
    main()
