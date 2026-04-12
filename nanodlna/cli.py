#!/usr/bin/env python3

from __future__ import print_function
import argparse
import json
import os
import sys
import signal
import datetime
import tempfile
import time
import threading
import logging
import twisted.internet.error
from tqdm import tqdm  # For progress bar

from . import devices, dlna, streaming

# Avoid naming conflict
devices_lib = devices

# A new signal handler for the main thread
def signal_handler_main(sig, frame, devices=None):
    """Handle SIGINT to gracefully stop streaming."""
    logging.info("Stopping streaming...")
    try:
        # Check if server is active before attempting to stop it
        if streaming.is_server_active():
            streaming.stop_server()
        
        # Stop any playing devices
        if devices:
            for device in devices:
                try:
                    device.stop()
                except Exception as e:
                    logging.error(f"Error stopping device {device.name}: {e}")
    except twisted.internet.error.ReactorNotRunning:
        logging.info("Reactor was not running, nothing to stop")
    except Exception as e:
        logging.error(f"Error in signal handler: {e}")
    finally:
        sys.exit(0)



# This function will be executed in each thread for each device
def play_video_on_device(device_name, video_file, args):

    while(True):
        try:
            device = find_device_with_retry(args, device_name)

            if device:

                logging.info(f"Attempting to play video '{video_file}' on device '{device['friendly_name']}'")

                # Configure streaming server
                files = {"file_video": video_file}

                # Check for subtitle if use_subtitle flag is set or not explicitly disabled
                use_subtitle = getattr(args, 'use_subtitle', True)
                if use_subtitle:
                    subtitle_file = get_subtitle(video_file)
                    if subtitle_file:
                        files["file_subtitle"] = subtitle_file

                logging.info(f"Media files: {json.dumps(files)}")

                # Get serve_ip - either from args or determine from target's hostname
                target_ip = device.get("hostname")
                serve_ip = getattr(args, "serve_ip", None) or getattr(args, "local_host", None)
                if not serve_ip and target_ip:
                    serve_ip = streaming.get_serve_ip(target_ip)
                
                # Start streaming
                url_dict, _ = streaming.start_server(files, serve_ip)
                logging.info(f"Stream available at: {url_dict}")

                logging.info("Streaming server ready")

                # Play the video via DLNA protocol
                logging.info("Sending play command")
                dlna.play(url_dict["file_video"], device, args)

                logging.info(f"Video '{video_file}' started playing on device '{device['friendly_name']}'")

                # Use tqdm to show progress for the video
                video_duration = dlna.get_video_duration(device)
                with tqdm(total=video_duration, desc=f"Playing {video_file}", ncols=100) as pbar:
                    for _ in range(video_duration):
                        time.sleep(1)  # Simulating each second of the video playing
                        pbar.update(1)  # Update the progress bar

                    if args.loop:
                        logging.info("Looping video in 5 seconds before it finishes")
                        time.sleep(max(0, video_duration - 5))
                        dlna.play(url_dict["file_video"], device, args)

                # Wait until the video finishes
                logging.info(f"Waiting for the video '{video_file}' to finish")
                time.sleep(video_duration)
        except:
            pass


# Restarting threads function
def monitor_and_restart_threads(threads, devices_config, args):
    while True:
        for i, thread in enumerate(threads):
            # If the thread is no longer alive, restart it
            if not thread.is_alive():
                config_item = devices_config[i]
                device_name = config_item["device_name"]
                video_file = config_item["video_file"]

                logging.warning(f"Thread for {device_name} stopped. Restarting...")


                # Create and start a new thread
                new_thread = threading.Thread(target=play_video_on_device, args=(device_name, video_file, args))
                threads[i] = new_thread  # Replace the old thread with the new one
                new_thread.start()

        # Sleep before next check to avoid high CPU usage
        time.sleep(1)


def play(args):
    """Search for DLNA renderers and play media."""

    logging.info(f"Playing {'looped' if args.loop else ''} media in DLNA renderer")

    # Validate arguments
    if not args.config_file and not args.media_path:
        sys.exit("Error: Either --config-file or media_path must be specified")

    # Find target renderer device
    if args.device_url is not None:
        logging.info(f"Using specified device URL: {args.device_url}")
        devices = [devices_lib.register_device(args.device_url)]
    else:
        # Add default values for attempts and timeout if not present
        n_attempts = getattr(args, 'attempts', 1)
        timeout = getattr(args, 'timeout', 5)
        device_query = getattr(args, 'device_query', None)
        logging.info(f"Searching for devices matching query: {device_query}. Timeout: {timeout}s, attempts: {n_attempts}")
        device_list = []
        for attempt in range(n_attempts):
            device_list = devices_lib.get_devices(timeout=timeout)
            if device_query:
                device_list = [d for d in device_list if device_query.lower() in str(d).lower()]
            if device_list:
                break
            logging.info(f"No devices found on attempt {attempt + 1}/{n_attempts}, retrying...")
        
        devices = device_list
    
    if not devices:
        logging.error("No matching devices found")
        return

    # Handle direct video playback mode
    if args.media_path:
        if not os.path.exists(args.media_path):
            logging.error(f"Media file not found: {args.media_path}")
            return

        # Use first discovered device if no query/url specified
        device = devices[0]
        device_name = device['friendly_name']
        
        logging.info(f"Playing {args.media_path} on device {device_name}")
        
        # Prepare the media for streaming
        files = {"file_video": args.media_path}
        
        # Handle subtitle
        if getattr(args, 'use_subtitle', True):
            subtitle_path = get_subtitle_path(args.media_path)
            if subtitle_path:
                files["file_subtitle"] = subtitle_path
                logging.info(f"Found subtitle: {subtitle_path}")
        elif args.file_subtitle:
            if os.path.exists(args.file_subtitle):
                files["file_subtitle"] = args.file_subtitle
                logging.info(f"Using specified subtitle: {args.file_subtitle}")
            else:
                logging.error(f"Specified subtitle file not found: {args.file_subtitle}")
        
        # Get serve_ip
        target_ip = device.get("hostname")
        serve_ip = getattr(args, "serve_ip", None) or getattr(args, "local_host", None)
        if not serve_ip and target_ip:
            serve_ip = streaming.get_serve_ip(target_ip)
            
        # Start streaming
        url_dict, _ = streaming.start_server(files, serve_ip)
        logging.info(f"Stream available at: {url_dict}")
        
        try:
            dlna.play(url_dict, device, args)
            logging.info(f"Successfully playing on device: {device_name}")
            
            # Wait for user interrupt
            signal.signal(signal.SIGINT, lambda sig, frame: signal_handler_main(sig, frame, [device]))
            logging.info("Press Ctrl+C to stop playback")
            signal.pause()
            
        except Exception as e:
            logging.error(f"Failed to play on device: {device_name}. Error: {str(e)}")
            return
    
    # Handle config file mode
    # Handle config file mode
    elif args.config_file:
        logging.info(f"Using configuration file: {args.config_file}")
        try:
            with open(args.config_file, 'r') as f:
                config_data = json.load(f)
            
            filtered_devices = []
            device_to_video = {}
            
            for config_entry in config_data:
                if 'device_name' in config_entry and 'video_file' in config_entry:
                    device_name = config_entry['device_name']
                    video_path = config_entry['video_file']
                    
                    for device in devices:
                        if device['friendly_name'] == device_name:
                            filtered_devices.append(device)
                            device_to_video[device_name] = video_path
                            logging.info(f"Matched device {device_name} with video {video_path}")
                            break
            
            if filtered_devices:
                devices = filtered_devices
                logging.info(f"Using {len(devices)} devices from configuration")
            else:
                logging.warning("No devices in configuration matched discovered devices")
                return
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logging.error(f"Error loading configuration file: {e}")
            return
            
        # Start streaming server ONCE for all files
        files = {}
        for device_name, video_file in device_to_video.items():
            if not os.path.exists(video_file):
                logging.error(f"Video file not found: {video_file}")
                continue
            
            # Using basename to avoid file collisions if names are identical? 
            # We'll prefix with device_name to be safe
            safe_name = f"{device_name.replace(' ', '_')}_{os.path.basename(video_file)}"
            files[safe_name] = video_file
            
            # Also add subtitle if needed
            if getattr(args, 'use_subtitle', True):
                subtitle_path = get_subtitle_path(video_file)
                if subtitle_path:
                    files[f"sub_{safe_name}"] = subtitle_path
                    
        if not files:
            logging.error("No valid media files found to stream.")
            return
            
        # Get serve_ip
        target_ip = None
        if len(devices) > 0:
            target_ip = devices[0].get("hostname")
            
        serve_ip = getattr(args, "serve_ip", None) or getattr(args, "local_host", None)
        if not serve_ip and target_ip:
            serve_ip = streaming.get_serve_ip(target_ip)
            
        url_dict, _ = streaming.start_server(files, serve_ip)
        logging.info(f"Stream server started. URLs available: {len(url_dict)}")
        
        status = {}
        threads = []
        
        def play_on_device(device, video_file, safe_name):
            device_name = device['friendly_name']
            try:
                # Package files_urls as expected by dlna.play
                files_urls = {"file_video": url_dict[safe_name]}
                
                # Check for subtitle
                if getattr(args, 'use_subtitle', True):
                    sub_key = f"sub_{safe_name}"
                    if sub_key in url_dict:
                        files_urls["file_subtitle"] = url_dict[sub_key]
                
                status[device_name] = "playing"
                dlna.play(files_urls, device, args)
                logging.info(f"Successfully playing on device: {device_name}")
                
                # Progress bar
                video_duration = dlna.get_video_duration(device)
                if video_duration:
                    with tqdm(total=video_duration, desc=f"Playing on {device_name}", ncols=80) as pbar:
                        for _ in range(video_duration):
                            time.sleep(1)
                            pbar.update(1)
                        
                        if getattr(args, 'loop', False):
                            time.sleep(max(0, video_duration - 5))
                            dlna.play(files_urls, device, args)
                
            except Exception as e:
                logging.error(f"Error playing on device {device_name}: {e}")
                status[device_name] = f"error: {str(e)}"
        
        # Start threads for each device
        for device in devices:
            device_name = device['friendly_name']
            video_file = device_to_video.get(device_name)
            safe_name = f"{device_name.replace(' ', '_')}_{os.path.basename(video_file)}"
            
            t = threading.Thread(target=play_on_device, args=(device, video_file, safe_name))
            t.daemon = True
            t.start()
            threads.append(t)
            
        # Summary
        logging.info("\nPlayback status summary:")
        for device_name, device_status in status.items():
            logging.info(f"Device: {device_name}, Status: {device_status}")
            
        try:
            # Wait for user interrupt
            signal.signal(signal.SIGINT, lambda sig, frame: signal_handler_main(sig, frame, devices))
            logging.info("Press Ctrl+C to stop playback")
            for t in threads:
                while t.is_alive():
                    t.join(1.0)
        except KeyboardInterrupt:
            signal_handler_main(signal.SIGINT, None, devices)
        except Exception as e:
            logging.error(f"Error in main thread: {e}")
            signal_handler_main(signal.SIGINT, None, devices)

def set_logs(args):
    log_filename = os.path.join(
        tempfile.mkdtemp(),
        "nanodlna-{}.log".format(
            datetime.datetime.today().strftime("%Y-%m-%d_%H-%M-%S")
        )
    )

    logging.basicConfig(
        filename=log_filename,
        filemode="w",
        level=logging.INFO,
        format="[ %(asctime)s ] %(levelname)s : %(message)s"
    )

    if args.debug_activated:
        logging.getLogger().setLevel(logging.DEBUG)

    print("nano-dlna log will be saved here: {}".format(log_filename))


def get_subtitle(file_video):
    video, extension = os.path.splitext(file_video)
    file_subtitle = "{0}.srt".format(video)

    if not os.path.exists(file_subtitle):
        return None
    return file_subtitle


def get_subtitle_path(video_path):
    """
    Try to find a subtitle file for the given video file.
    Looks for files with the same name but different extensions.
    
    Args:
        video_path (str): Path to the video file
        
    Returns:
        str: Path to the subtitle file if found, None otherwise
    """
    subtitle_extensions = ['.srt', '.sub', '.smi', '.ssa', '.ass', '.vtt']
    base_path = os.path.splitext(video_path)[0]
    
    for ext in subtitle_extensions:
        subtitle_path = base_path + ext
        if os.path.exists(subtitle_path):
            return subtitle_path
    
    return None


def list_devices(args):
    set_logs(args)

    logging.info("Scanning devices...")
    my_devices = devices_lib.get_devices(args.timeout, args.local_host)
    logging.info("Number of devices found: {}".format(len(my_devices)))

    for i, device in enumerate(my_devices, 1):
        print("Device {0}:\n{1}\n\n".format(i, json.dumps(device, indent=4)))


def generate_config(args):
    set_logs(args)
    logging.info("Generating configuration template...")

    # Get the list of devices
    my_devices = devices_lib.get_devices(args.timeout, args.local_host)

    # Create a configuration template with placeholders
    config = []
    for device in my_devices:
        config.append({
            "device_name": device.get("friendly_name", "Unknown Device"),
            "hostname": device["hostname"],
            "action_url": device["action_url"],
            "video_file": ""  # Placeholder for the user to fill in
        })

    # Output config to JSON file
    config_filename = args.config_file or "dlna_device_config.json"
    with open(config_filename, "w") as config_file:
        json.dump(config, config_file, indent=4)

    print(f"Configuration template saved to {config_filename}")
    logging.info(f"Configuration template saved to {config_filename}")


def find_device(args, device_name=None):
    logging.info("Selecting device to play")

    device = None
    if device_name:
        logging.info(f"Searching for device with name: {device_name}")
        my_devices = devices_lib.get_devices(args.timeout, args.local_host)
        device = next((d for d in my_devices if device_name.lower() in d["friendly_name"].lower()), None)
    else:
        if args.device_url:
            device = devices_lib.register_device(args.device_url)
        else:
            my_devices = devices_lib.get_devices(args.timeout, args.local_host)
            if len(my_devices) > 0:
                if args.device_query:
                    device = next((d for d in my_devices if args.device_query.lower() in str(d).lower()), None)
                else:
                    device = my_devices[0]
    return device


def find_device_with_retry(args, device_name=None, max_retries=99999999, sleep_interval=5):
    retries = 0
    device = None
    while retries < max_retries:
        device = find_device(args, device_name)
        if device:
            break
        retries += 1
        logging.warning(f"Device not found, retrying {retries}/{max_retries}...")
        time.sleep(sleep_interval)

    if not device:
        sys.exit("Device not found after retries")
    return device


def seek(args):
    set_logs(args)
    logging.info("Starting to seek")

    device = find_device(args)
    if not device:
        sys.exit("No devices found.")

    logging.info("Sending seek command: {}".format(args.target))
    dlna.seek(args.target, device)


def pause(args):
    set_logs(args)

    logging.info("Selecting device to pause")
    device = find_device(args)

    # Pause through DLNA protocol
    logging.info("Sending pause command")
    dlna.pause(device)


def stop(args):
    set_logs(args)

    logging.info("Selecting device to stop")
    device = find_device(args)

    # Stop through DLNA protocol
    logging.info("Sending stop command")
    dlna.stop(device)


def run():
    parser = argparse.ArgumentParser(
        description="A minimal UPnP/DLNA media streamer.")
    parser.set_defaults(func=lambda args: parser.print_help())
    parser.add_argument("-H", "--host", dest="local_host")
    parser.add_argument("-t", "--timeout", type=float, default=5)
    parser.add_argument("-b", "--debug",
                        dest="debug_activated", action="store_true")
    subparsers = parser.add_subparsers(dest="subparser_name")

    p_list = subparsers.add_parser('list')
    p_list.set_defaults(func=list_devices)

    # New generate-config command
    p_generate_config = subparsers.add_parser('generate-config')
    p_generate_config.add_argument(
        "-o", "--output", dest="config_file",
        help="Path to save the generated configuration file (default: dlna_device_config.json)"
    )
    p_generate_config.set_defaults(func=generate_config)

    p_play = subparsers.add_parser('play', 
        description="""
Play media files on DLNA devices. Two modes are supported:

1. Direct playback: Specify a media file to play on a single device
   Example: nanodlna play video.mp4 -q "Living Room TV"

2. Config file mode: Use a JSON config file to play different videos on multiple devices
   Example: nanodlna play -c config.json

The config file should be in JSON format:
[
    {
        "device_name": "Living Room TV",
        "video_file": "/path/to/video1.mp4"
    },
    {
        "device_name": "Bedroom TV",
        "video_file": "/path/to/video2.mp4"
    }
]
""",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    p_play.add_argument("-c", "--config-file", required=False, help="Optional path to the config file for video and device information")
    p_play.add_argument("-d", "--device", dest="device_url", help="URL of the specific device to play on")
    p_play.add_argument("-q", "--query-device", dest="device_query", help="Search for a device matching this query")
    p_play.add_argument("-s", "--subtitle", dest="file_subtitle", help="Path to subtitle file")
    p_play.add_argument("-n", "--no-subtitle", dest="use_subtitle", action="store_false", help="Disable automatic subtitle detection")
    p_play.add_argument("--loop", action="store_true", help="Loop the video 5 seconds before it finishes")
    p_play.add_argument("media_path", nargs="?", help="Path to the media file to play. Not required if using --config-file")
    p_play.set_defaults(func=play)

    p_seek = subparsers.add_parser('seek')
    p_seek.add_argument("-d", "--device", dest="device_url")
    p_seek.add_argument("-q", "--query-device", dest="device_query")
    p_seek.add_argument("target", help="e.g. '00:17:25'")
    p_seek.set_defaults(func=seek)

    p_pause = subparsers.add_parser('pause')
    p_pause.add_argument("-d", "--device", dest="device_url")
    p_pause.add_argument("-q", "--query-device", dest="device_query")
    p_pause.set_defaults(func=pause)

    p_stop = subparsers.add_parser('stop')
    p_stop.add_argument("-d", "--device", dest="device_url")
    p_stop.add_argument("-q", "--query-device", dest="device_query")
    p_stop.set_defaults(func=stop)

    # Additional commands
    p_update = subparsers.add_parser('update')
    p_update.add_argument("action", choices=['add', 'remove'], help="Action to update device")
    p_update.add_argument("device_name", help="Name of the device to add or remove")
    p_update.set_defaults(func=update_device)

    args = parser.parse_args()
    args.func(args)


def update_device(args):
    # Handle device addition or removal
    logging.info(f"Starting device update with action: {args.action} for device: {args.device_name}")
    try:
        if args.action == 'add':
            add_device(args.device_name)
        elif args.action == 'remove':
            remove_device(args.device_name)
    except Exception as e:
        logging.error(f"Error updating device: {e}")
        sys.exit(1)

def add_device(device_name):
    # Implement device addition logic
    logging.info(f"Adding device with name: {device_name}")
    # Logic to add the device goes here (e.g., adding to a list, config file, etc.)

def remove_device(device_name):
    # Implement device removal logic
    logging.info(f"Removing device with name: {device_name}")
    # Logic to remove the device goes here (e.g., from a list, config file, etc.)

def send_video(device_info, video_path, loop=False):
    """
    Send a video to a DLNA device.
    
    Args:
        device_info (dict): Device information dictionary
        video_path (str): Path to the video file
        loop (bool): Whether to loop the video
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Configure streaming server
        files = {"file_video": video_path}
        
        # Get serve_ip from device's hostname
        target_ip = device_info.get("hostname")
        serve_ip = streaming.get_serve_ip(target_ip)
        
        # Start streaming
        url_dict, _ = streaming.start_server(files, serve_ip)
        
        # Create args object with loop attribute
        class Args:
            pass
        args = Args()
        args.loop = loop
        
        # Play the video
        dlna.play(url_dict, device_info, args)
        return True
    except Exception as e:
        logging.error(f"Error sending video: {e}")
        return False

def process_config(config_file):
    """
    Process a configuration file to play videos on devices.
    
    Args:
        config_file (str): Path to the configuration file
        
    Returns:
        bool: True if successful, False otherwise
    """
    logging.info(f"Processing configuration file: {config_file}")
    
    try:
        # Load the configuration file
        with open(config_file, 'r') as f:
            config_data = json.load(f)
        
        # Create args object for compatibility with play function
        class Args:
            pass
        args = Args()
        args.loop = False
        args.timeout = 5
        args.local_host = None
        args.debug_activated = False
        
        # Process each device in the configuration
        for config_item in config_data:
            if 'device_name' in config_item and 'video_file' in config_item:
                device_name = config_item['device_name']
                video_file = config_item['video_file']
                
                # Check if video file exists
                if not os.path.exists(video_file):
                    logging.error(f"Video file not found: {video_file}")
                    continue
                
                # Find the device
                device = find_device(args, device_name)
                if not device:
                    logging.error(f"Device not found: {device_name}")
                    continue
                
                # Send the video to the device
                logging.info(f"Sending video {video_file} to device {device_name}")
                send_video(device, video_file, args.loop)
        
        return True
    except Exception as e:
        logging.error(f"Error processing configuration file: {e}")
        return False
