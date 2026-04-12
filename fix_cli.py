import os
import re

with open('nanodlna/cli.py', 'r') as f:
    content = f.read()

# I will replace the "elif args.config_file:" block with the updated threading logic.
# Finding the block
start_idx = content.find("    elif args.config_file:")
end_idx = content.find("def set_logs(args):")

if start_idx != -1 and end_idx != -1:
    before = content[:start_idx]
    after = "\n" + content[end_idx:]
    
    new_block = """    # Handle config file mode
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
        logging.info("\\nPlayback status summary:")
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
"""
    new_content = before + new_block + after
    with open('nanodlna/cli.py', 'w') as f:
        f.write(new_content)
    print("Replaced cli.py successfully.")
else:
    print("Could not find the block to replace!")
