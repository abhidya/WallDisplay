on run argv
    set command to item 1 of argv
    
    if command is "start" then
        set deviceName to item 2 of argv
        set displayMode to "mirror"
        if (count of argv) is greater than 2 then
            set displayMode to item 3 of argv
        end if
        startMirroring(deviceName, displayMode)
    else if command is "stop" then
        stopMirroring()
    else
        error "Unknown command: " & command
    end if
end run

on _activateDisplaysSettings()
    try
        tell application "System Settings"
            activate
        end tell
    on error
        tell application "System Preferences"
            activate
            reveal pane "com.apple.preference.displays"
        end tell
    end try
    delay 1
end _activateDisplaysSettings

on _getSettingsProcessName()
    tell application "System Events"
        if exists process "System Settings" then
            return "System Settings"
        end if
    end tell
    return "System Preferences"
end _getSettingsProcessName

on _configureDisplayMode(displayMode)
    set normalizedMode to do shell script "printf %s " & quoted form of displayMode & " | tr '[:upper:]' '[:lower:]'"
    set desiredLabels to {}
    if normalizedMode is in {"extend", "extended", "separate", "separate_display"} then
        set desiredLabels to {"Use As Separate Display", "Separate Display", "Use as Separate Display", "Extend Display", "Extended Display"}
    else
        set desiredLabels to {"Mirror", "Mirror Built-in Display", "Mirror Main Display", "Mirroring"}
    end if
    
    tell application "System Events"
        tell process my _getSettingsProcessName()
            repeat with popupButton in (every pop up button of window 1)
                set buttonTitle to ""
                set buttonDescription to ""
                set buttonValue to ""
                try
                    set buttonTitle to title of popupButton as text
                end try
                try
                    set buttonDescription to description of popupButton as text
                end try
                try
                    set buttonValue to value of popupButton as text
                end try
                
                if buttonTitle contains "Use As" or buttonDescription contains "Use As" or buttonValue contains "Use As" then
                    click popupButton
                    delay 0.5
                    repeat with menuItem in menu items of menu 1 of popupButton
                        set menuItemName to name of menuItem as text
                        repeat with desiredLabel in desiredLabels
                            if menuItemName contains desiredLabel then
                                click menuItem
                                delay 0.5
                                return
                            end if
                        end repeat
                    end repeat
                    key code 53
                end if
            end repeat
        end tell
    end tell
end _configureDisplayMode

on startMirroring(deviceName, displayMode)
    my _activateDisplaysSettings()
    tell application "System Preferences"
        tell application "System Events"
            tell process my _getSettingsProcessName()
                # Click AirPlay dropdown 
                click pop up button 1 of tab group 1 of window 1
                delay 0.5
                
                # Find and click the device with matching name
                repeat with menuItem in menu items of menu 1 of pop up button 1 of tab group 1 of window 1
                    if name of menuItem contains deviceName then
                        click menuItem
                        delay 0.5
                        my _configureDisplayMode(displayMode)
                        # Success
                        return 0
                    end if
                end repeat
                
                # Device not found
                error "AirPlay device not found: " & deviceName
            end tell
        end tell
    end tell
end startMirroring

on stopMirroring()
    my _activateDisplaysSettings()
    tell application "System Preferences"
        tell application "System Events"
            tell process my _getSettingsProcessName()
                # Click AirPlay dropdown 
                click pop up button 1 of tab group 1 of window 1
                delay 0.5
                
                # Click "This Mac" to stop mirroring
                click menu item "This Mac" of menu 1 of pop up button 1 of tab group 1 of window 1
                delay 0.5
                # Success
                return 0
            end tell
        end tell
    end tell
end stopMirroring 
