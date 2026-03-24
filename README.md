# nano-dlna

[![Build Status](https://travis-ci.org/gabrielmagno/nano-dlna.svg?branch=master)](https://travis-ci.org/gabrielmagno/nano-dlna)
[![PyPI](https://img.shields.io/pypi/v/nanodlna.svg)](https://pypi.python.org/pypi/nanodlna)
[![License](https://img.shields.io/github/license/gabrielmagno/nano-dlna.svg)](https://github.com/gabrielmagno/nano-dlna/blob/master/LICENSE)

A minimal UPnP/DLNA media streamer with web dashboard for managing and streaming videos to DLNA devices.

## Overview

nano-dlna lets you play local media files on your DLNA-compatible devices (TVs, projectors, etc.) with both CLI and web-based interfaces. It's designed to be simple, reliable, and flexible.

🦀 **Note**: Also check out [crab-dlna](https://github.com/gabrielmagno/crab-dlna), a Rust implementation of nano-dlna.

## Features

- **Device Management**:
  - Auto-discover DLNA devices on your network
  - Manual configuration of devices
  - View device status and connection info

- **Video Management**:
  - Stream videos to any DLNA device
  - Upload and manage video files
  - Scan directories for videos

- **Playback Control**:
  - Play, pause, stop video playback
  - Seek to specific positions
  - Loop videos automatically

- **Auto-Play**:
  - Automatically play videos on specific devices
  - Device-video mapping via configuration files
  - Continuous monitoring and reconnection

- **Multiple Interfaces**:
  - Web dashboard for visual management
  - CLI for command-line operations
  - REST API for integration with other tools

## Installation

### Method 1: Using pip

```bash
pip install nanodlna
```

### Method 2: From source

```bash
git clone https://github.com/gabrielmagno/nano-dlna.git
cd nano-dlna
pip install -e .
```

## Usage

### Web Dashboard

The web dashboard provides a user-friendly interface for managing devices and videos.

#### Starting the Dashboard

```bash
# Pick the env file for this machine once, then edit if needed
cp .env.dev-laptop.example .env

# Start the dashboard
./run_dashboard.sh

# Stop the dashboard
./stop_dashboard.sh
```

This will start both the backend API and the frontend web interface:

- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Documentation: http://localhost:8000/docs

#### Dashboard Features

1. **Devices Page**: View and manage discovered DLNA devices
2. **Videos Page**: Upload, scan, and manage your video library
3. **Play Page**: Select a device and video to play
4. **Device Configuration**: Set up automatic video assignments

### Command Line Interface

The CLI allows you to manage devices and videos directly from the terminal.

#### Basic Commands

```bash
# List available DLNA devices
nanodlna list

# Play a video on a device
nanodlna play video.mp4 -q "TV"

# Play with device URL (faster, no scan)
nanodlna play video.mp4 -d "http://192.168.1.13:1082/"

# Seek to a specific position
nanodlna seek -q "TV" "00:17:25"
```

#### Using Scripts

Several helper scripts are available:

```bash
# Run the auto-play functionality
./run_nanodlna.sh

# Cast to a specific transcreen projector
./cast_to_transcreen.sh

# Run both the nanodlna app and web interface
./run_all.sh
```

## Configuration

### Device-Video Mapping

The primary configuration file is `my_device_config.json`, which maps devices to videos:

```json
[
    {
        "device_name": "LivingRoomTV",
        "type": "dlna",
        "hostname": "192.168.1.100",
        "video_file": "/path/to/video.mp4"
    },
    {
        "device_name": "BedroomTV",
        "type": "dlna",
        "hostname": "192.168.1.101",
        "video_file": "/path/to/another_video.mp4"
    }
]
```

`video_file` now supports:

- Relative paths, resolved from the config file location
- Environment variables such as `${HOME}` or `${NANODLNA_MEDIA_ROOT}`
- Absolute paths when you really need them

For each machine, keep machine-specific settings in `.env` instead of editing source:

```bash
cp .env.dev-laptop.example .env
```

Committed templates:

```bash
./.env.dev-laptop.example
./.env.mac-mini.example
```

Use the laptop template on:

```bash
/Users/abdulrehmanbhidya/PycharmProjects/nano-dlna
```

Use the Mac mini template on:

```bash
/Users/mannybhidya/PycharmProjects/WallMapper
```

Both templates assume:

- `my_device_config.json` is the active device config
- `NANODLNA_MEDIA_ROOT` points at the machine's `Movies` folder
- the Python venv lives in repo-local `.venv`

If your media lives elsewhere, change `NANODLNA_MEDIA_ROOT` in the copied `.env`.

## Dev Workflow

Laptop dev:

```bash
cp .env.dev-laptop.example .env
./run_dashboard.sh
```

Mac mini dev / manual run:

```bash
cp .env.mac-mini.example .env
./run_dashboard.sh
```

## macOS Service

For an always-on Mac mini, use `launchd`:

```bash
cp .env.mac-mini.example .env
./service/install_launchd.sh
```

What this gives you:

- Starts automatically at login / machine startup for that user
- Restarts if backend or frontend exits
- Writes logs under `logs/`
- Optionally fast-forwards the repo and restarts the service every 5 minutes when `NANODLNA_GIT_AUTO_UPDATE=1`

Useful commands:

```bash
launchctl print gui/$UID/com.nanodlna.dashboard
launchctl kickstart -k gui/$UID/com.nanodlna.dashboard
tail -f logs/service-supervisor.log
tail -f logs/backend.stderr.log
```

Two-machine workflow:

```bash
# On the dev laptop
cp .env.dev-laptop.example .env

# On the Mac mini
cp .env.mac-mini.example .env
```

The `.env` file itself stays local and is ignored by git. Commit the two example files instead.

### Auto-Play Configuration

You can configure auto-play behavior in several ways:

1. **Manual Assignment** via the web interface
2. **Configuration Files** with device-video mappings
3. **Scheduled Playback** using the web dashboard

## Utility Scripts

Several utility scripts are available to help manage the system:

### clean_videos.py

```bash
python clean_videos.py
```

Cleans up the database by removing non-existent videos and handling duplicates.

### add_config_videos.py

```bash
python add_config_videos.py
```

Adds videos from the configuration files to the database.

### scan_videos.py

```bash
python scan_videos.py --directory "/path/to/videos" --recursive
```

Scans a directory for videos and adds them to the database.

### fix_device.py

```bash
python fix_device.py --device "DeviceName"
```

Attempts to fix issues with a specific device.

## Troubleshooting

### Common Issues

1. **Devices not discovered**
   - Ensure devices are on the same network
   - Check firewall settings
   - Try increasing discovery timeout: `nanodlna -t 20 list`

2. **Videos won't play**
   - Check that file paths in configuration are correct
   - Verify video format is compatible (H.264 MP4 is most reliable)
   - Check network connectivity

3. **Web Dashboard Issues**
   - Clear browser cache
   - Restart the dashboard
   - Check backend logs for errors

### Advanced Troubleshooting

For more serious issues:

1. Enable verbose logging:
   ```bash
   export NANODLNA_DEBUG=1
   ```

2. Check the log files:
   ```bash
   cat nanodlna.log
   ```

3. Clean the database:
   ```bash
   python clean_videos.py
   ```

## Technical Details

nano-dlna functions as both a DLNA MediaServer (to serve your media files) and a MediaController (to send commands to your devices).

The auto-play system works by:
1. Loading device configurations from JSON files
2. Discovering devices on the network
3. Matching discovered devices with configurations
4. Starting media servers for video streaming
5. Sending play commands to matched devices
6. Continuously monitoring playback and reconnecting as needed

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request
