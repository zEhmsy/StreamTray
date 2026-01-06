<!-- PROJECT SHIELDS -->
[![Contributors][contributors-shield]][contributors-url]
[![Forks][forks-shield]][forks-url]
[![Stargazers][stars-shield]][stars-url]
[![Issues][issues-shield]][issues-url]
[![Apache 2.0 License][license-shield]][license-url]

<!-- PROJECT LOGO -->
<br />
<div align="center">
  <a href="https://github.com/zEhmsy/StreamTray">
    <img src="app.png" alt="StreamTray logo" width="96" height="96">
  </a>

  <h3 align="center">StreamTray</h3>

  <p align="center">
    Tiny Python tray-server that converts any <strong>RTSP</strong> camera/DVR<br />
    into lightweight <strong>MJPEG</strong> feeds for browsers &amp; mobile apps.
    <br />
    <br />
    <a href="https://github.com/zEhmsy/StreamTray"><strong>Explore the docs »</strong></a>
    ·
    <a href="https://github.com/zEhmsy/StreamTray/issues">Report Bug</a>
    ·
    <a href="https://github.com/zEhmsy/StreamTray/issues">Request Feature</a>
  </p>
</div>

<!-- TABLE OF CONTENTS -->
<details>
  <summary>Table of Contents</summary>
  <ol>
    <li>
      <a href="#about-the-project">About The Project</a>
      <ul>
        <li><a href="#built-with">Built With</a></li>
      </ul>
    </li>
    <li><a href="#key-features">Key Features</a></li>
    <li>
      <a href="#getting-started">Getting Started</a>
      <ul>
        <li><a href="#prerequisites">Prerequisites</a></li>
        <li><a href="#installation">Installation</a></li>
      </ul>
    </li>
    <li><a href="#usage">Usage</a></li>
    <li><a href="#api-reference">API Reference</a></li>
    <li><a href="#roadmap">Roadmap</a></li>
    <li><a href="#license">License</a></li>
    <li><a href="#contact">Contact</a></li>
  </ol>
</details>

---

## About The Project

**StreamTray** is a zero-config micro-server that sits in your system-tray, opens an RTSP connection **once per camera**, and re-streams frames as `multipart/x-mixed-replace; boundary=frame`.

This format is universally compatible, allowing any browser `<img>` tag or mobile framework (like Flutter) to render low-latency video feeds without complex players or HLS latency.

### Architecture
```txt
┌────────────────────────┐
│                        │
│ RTSP/H-264│   Camera   │
│ streams ► │ DVR / NVR  │
└────────────────────────┘
            │
            ▼ (single connection per cam)
┌──────────────────────────┐
│    StreamTray Server     │
│  ▸ SQLite DB of streams  │
│  ▸ OpenCV Capture Engine │
│  ▸ MJPEG HTTP Endpoint   │
└──────────────────────────┘
            │
            ▼ (multiple clients)
  Browser ▸ <img src=/video_feed/uuid>
  Dashboard (localhost:5050)
  Mobile App (PixPulse Viewer)
```

<p align="right">(<a href="#top">back to top</a>)</p>

### Built With

*   ![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
*   ![Flask](https://img.shields.io/badge/flask-%23000.svg?style=for-the-badge&logo=flask&logoColor=white)
*   ![OpenCV](https://img.shields.io/badge/opencv-%23white.svg?style=for-the-badge&logo=opencv&logoColor=white)
*   ![SQLite](https://img.shields.io/badge/sqlite-%2307405e.svg?style=for-the-badge&logo=sqlite&logoColor=white)

<p align="right">(<a href="#top">back to top</a>)</p>

## Key Features

*   **🚀 Zero Config**: Runs instantly from System Tray.
*   **🎥 Universal Compatibility**: Converts RTSP to MJPEG for valid display in any HTML `<img>` tag.
*   **💻 Modern Dashboard**: Manage streams, rename cameras, and preview feeds via a sleek Web UI.
*   **🏎️ High Performance**: Centralized encoding engine ensures the camera is only polled once, regardless of client count.
*   **📦 Portable**: Single executable (Windows .exe or macOS .app) with persistent SQLite storage.
*   **🌑 Dark Mode**: Beautiful, responsive user interface with custom styling.

<p align="right">(<a href="#top">back to top</a>)</p>

## Getting Started

### Prerequisites

*   Python 3.10+
*   RTSP Enabled Camera

### Installation

1.  **Clone the repo**
    ```sh
    git clone https://github.com/zEhmsy/StreamTray.git
    cd StreamTray
    ```
2.  **Install Python packages**
    ```sh
    pip install -r requirements.txt
    ```
3.  **Run the application**
    ```sh
    python streamtray.py
    ```

    *Or build the standalone app:*
    ```sh
    # MacOS
    ./build_mac.sh
    ```

<p align="right">(<a href="#top">back to top</a>)</p>

## Usage

1.  Start the application. The **StreamTray icon** will appear in your system tray / menu bar.
2.  Click **Open Dashboard** (or go to `http://localhost:5050`).
3.  Click **+ Add Stream**.
4.  Enter a "Friendly Name" (e.g., *Front Door*) and the RTSP URL (e.g., `rtsp://user:pass@192.168.1.10:554/stream`).
5.  The stream will immediately appear in the list.

### Dashboard Preview
Use the Play button on any stream to open the live lightbox preview.

<p align="right">(<a href="#top">back to top</a>)</p>

## API Reference

The server exposes a RESTful API for integration.

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/api/streams` | List all configured streams `[{id, url, name}]`. |
| `POST` | `/api/streams` | Add a stream. Body: `{"url": "...", "name": "..."}`. |
| `PUT` | `/api/streams/<id>` | Update a stream. |
| `DELETE` | `/api/streams/<id>` | Remove a stream. |
| `GET` | `/video_feed/<id>` | **MJPEG Live Stream**. Embed as `src` in `<img>`. |
| `GET` | `/api/snapshot/<id>` | Single JPEG frame. |

<p align="right">(<a href="#top">back to top</a>)</p>

## Roadmap

*   [x] Basic RTSP to MJPEG bridging
*   [x] Web Dashboard for management
*   [x] Persistent SQLite Storage
*   [x] Custom Stream Naming
*   [x] MacOS .app Packaging
*   [ ] User Authentication (Login)
*   [ ] HLS / WebRTC Support
*   [ ] Docker Container

See the [open issues](https://github.com/zEhmsy/StreamTray/issues) for a full list of proposed features (and known bugs).

<p align="right">(<a href="#top">back to top</a>)</p>

## License

Distributed under the Apache 2.0 License. See `LICENSE` for more information.

<p align="right">(<a href="#top">back to top</a>)</p>

## Contact

Project Link: [https://github.com/zEhmsy/StreamTray](https://github.com/zEhmsy/StreamTray)

<p align="right">(<a href="#top">back to top</a>)</p>

<!-- MARKDOWN LINKS & IMAGES -->
[contributors-shield]: https://img.shields.io/github/contributors/zEhmsy/StreamTray.svg?style=for-the-badge
[contributors-url]: https://github.com/zEhmsy/StreamTray/graphs/contributors
[forks-shield]: https://img.shields.io/github/forks/zEhmsy/StreamTray.svg?style=for-the-badge
[forks-url]: https://github.com/zEhmsy/StreamTray/network/members
[stars-shield]: https://img.shields.io/github/stars/zEhmsy/StreamTray.svg?style=for-the-badge
[stars-url]: https://github.com/zEhmsy/StreamTray/stargazers
[issues-shield]: https://img.shields.io/github/issues/zEhmsy/StreamTray.svg?style=for-the-badge
[issues-url]: https://github.com/zEhmsy/StreamTray/issues
[license-shield]: https://img.shields.io/github/license/zEhmsy/StreamTray.svg?style=for-the-badge
[license-url]: https://github.com/zEhmsy/StreamTray/blob/master/LICENSE
