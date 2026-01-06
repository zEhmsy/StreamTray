# StreamTray

StreamTray is a lightweight, web-based tool for managing and viewing RTSP video streams. It provides a clean, modern dashboard to organize your camera feeds and view them on demand.

![Dashboard Preview](templates/preview.png)

## Features

-   **Web Dashboard Manager**: A sleek, dark-mode web interface to manage all your streams (`http://localhost:5050`).
-   **RTSP Stream Management**: Add, Edit, and Delete RTSP streams easily via the UI.
-   **Live Player (Lightbox)**: Click "Play" on any stream to open a low-latency live video feed in a fullscreen overlay.
-   **API Documentation**: Built-in, interactive documentation panel for developers right in the dashboard.
-   **Resource Efficient**: No background streaming load when not viewing a camera.
-   **Cross-Platform**: Runs on macOS (tray icon included), Linux, and Windows.

## Installation

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/yourusername/StreamTray.git
    cd StreamTray
    ```

2.  **Set up the environment** (using `uv` or `venv`):
    ```bash
    uv venv
    source .venv/bin/activate
    uv pip install -r requirements.txt
    ```

3.  **Run the application**:
    ```bash
    python streamtray.py
    ```

## Usage

1.  The application starts a web server on `http://localhost:5050`.
2.  A system tray icon (on macOS) allows you to quickly open the dashboard or quit the app.
3.  **Add Stream**: Click the "+" button in the header.
4.  **View Stream**: Click the "Play" icon (triangular shape) in the list to open the live view.
5.  **API Docs**: Click the "API Docs" button in the header to view available networking endpoints.

## API Reference

StreamTray exposes a REST API for automation:

-   `GET /api/streams`: List all streams.
-   `POST /api/streams`: Add a new stream.
-   `PUT /api/streams/<id>`: Update a stream.
-   `DELETE /api/streams/<id>`: Remove a stream.
-   `GET /video_feed/<id>`: Live MJPEG stream.
-   `GET /api/snapshot/<id>`: Single JPEG frame.

## License

Apache License 2.0
