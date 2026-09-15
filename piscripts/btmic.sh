
#!/bin/bash
# bt_record.sh — record, stream, or playback Bluetooth audio
# Smart version: checks headset first, restarts services only if needed

REC_DIR="/home/q/recorded"
PORT=8000

mkdir -p "$REC_DIR"

# --- Check Bluetooth headset status ---
echo "🔍 Checking Bluetooth headset status..."
BT_INPUT_INFO=$(pw-cli ls Node | grep -A25 "bluez_input" | head -n25)
BT_OUTPUT_INFO=$(pw-cli ls Node | grep -A25 "bluez_sink" | head -n25)
BT_INPUT_ID=$(echo "$BT_INPUT_INFO" | awk '/id/{print $2; exit}')
BT_OUTPUT_ID=$(echo "$BT_OUTPUT_INFO" | awk '/id/{print $2; exit}')

# Try multiple fields for name: node.description, device.description, node.name
BT_DEVICE_NAME=$(echo "$BT_INPUT_INFO" | grep -Po '(?<=node.description = ").*(?=")' | head -n1)
if [ -z "$BT_DEVICE_NAME" ]; then
    BT_DEVICE_NAME=$(echo "$BT_INPUT_INFO" | grep -Po '(?<=device.description = ").*(?=")' | head -n1)
fi
if [ -z "$BT_DEVICE_NAME" ]; then
    BT_DEVICE_NAME=$(echo "$BT_INPUT_INFO" | grep -Po '(?<=node.name = ").*(?=")' | head -n1)
fi

if [ -n "$BT_INPUT_ID" ] || [ -n "$BT_OUTPUT_ID" ]; then
    echo "✅ Headset detected: ${BT_DEVICE_NAME:-Unknown device}"
else
    echo "⚠️ Headset not detected, restarting Bluetooth and PipeWire..."
    sudo systemctl restart bluetooth
    systemctl --user restart pipewire
    systemctl --user restart wireplumber
    sleep 3
fi

# Recheck after restart
BT_INPUT_INFO=$(pw-cli ls Node | grep -A15 "bluez_input" | head -n15)
BT_OUTPUT_INFO=$(pw-cli ls Node | grep -A15 "bluez_sink" | head -n15)
BT_INPUT_ID=$(echo "$BT_INPUT_INFO" | awk '/id/{print $2; exit}')
BT_OUTPUT_ID=$(echo "$BT_OUTPUT_INFO" | awk '/id/{print $2; exit}')
BT_DEVICE_NAME=$(echo "$BT_INPUT_INFO" | grep -Po '(?<=device.description = ").*(?=")' | head -n1)

# Friendly output node label
if [ -n "$BT_OUTPUT_ID" ]; then
    OUTPUT_LABEL="headset ($BT_OUTPUT_ID)"
else
    OUTPUT_LABEL="none"
fi

echo "🎙️ Input node: ${BT_INPUT_ID:-none}"
echo "🎧 Output node: ${OUTPUT_LABEL}"


cleanup() {
    echo -e "\nCleaning up..."
    pkill -f "pw-record --target $BT_INPUT_ID" 2>/dev/null
    pkill -f "pw-play --target $BT_OUTPUT_ID" 2>/dev/null
    pkill -f "nc -l -p $PORT" 2>/dev/null
    sleep 1
    exit 0
}
trap cleanup INT

echo "Choose mode: record / stream / playback / monitor"
read MODE

# --- RECORD MODE ---
if [ "$MODE" = "record" ]; then
    echo "Select recording mode:"
    echo "1) Voice — low latency, smaller file, suitable for speech"
    echo "2) High Quality — best fidelity, larger file, suitable for music"
    read CHOICE

    if [ "$CHOICE" = "1" ]; then
        RATE=16000
        FORMAT="s16"
        DESC="Voice mode (16 kHz mono)"
    else
        RATE=48000
        FORMAT="s16"
        DESC="High‑Quality mode (48 kHz stereo)"
    fi

    echo "How many seconds do you want to record?"
    read SECS
    TS=$(date +"%Y-%m-%d_%H-%M-%S")
    OUT="$REC_DIR/rec_$TS.wav"

    # Boost mic gain safely
    if [[ "$BT_INPUT_ID" =~ ^[0-9]+$ ]]; then
        wpctl set-volume "$BT_INPUT_ID" 1.5
    fi

    echo "Recording $SECS seconds from $BT_DEVICE_NAME in $DESC..."
    timeout "$SECS" pw-record --target "$BT_INPUT_ID" --rate "$RATE" --channels 1 --format "$FORMAT" "$OUT"
    echo "Saved: $OUT"
    sleep 2
    exit 0
fi

# --- STREAM MODE ---
if [ "$MODE" = "stream" ]; then
    echo "Starting live stream on port $PORT..."
    echo "Open: http://$(hostname -I | awk '{print $1}'):$PORT/live.wav"

    # Boost mic gain safely
    if [[ "$BT_INPUT_ID" =~ ^[0-9]+$ ]]; then
        wpctl set-volume "$BT_INPUT_ID" 1.5
    fi

    # Serve continuous audio stream
    while true; do
        {
            printf "HTTP/1.1 200 OK\r\n"
            printf "Content-Type: audio/wav\r\n"
            printf "Cache-Control: no-cache\r\n"
            printf "Connection: close\r\n\r\n"

            # WAV header with "data" chunk size set to 0xFFFFFFFF (infinite stream)
            printf "RIFF\xFF\xFF\xFF\xFFWAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00\x80\x3E\x00\x00\x00\x7D\x00\x00\x02\x00\x10\x00data\xFF\xFF\xFF\xFF"

            # Stream mic data continuously
            pw-record --target "$BT_INPUT_ID" --rate 16000 --channels 1 --format s16 - 2>/dev/null
        } | socat - TCP-LISTEN:$PORT,reuseaddr
    done
fi


# -- PLAYBACK MODE ---
if [ "$MODE" = "playback" ]; then
    echo "Available recordings:"
    ls "$REC_DIR"/*.wav 2>/dev/null || echo "No recordings found."
    echo "Enter filename to play (without path):"
    read FILE
    FULL_PATH="$REC_DIR/$FILE"

    if [ ! -f "$FULL_PATH" ]; then
        echo "❌ Error: File not found: $FULL_PATH"
        exit 1
    fi

    echo "Play via: headset / website"
    read DEST

    # Boost playback volume safely
    if [[ "$BT_OUTPUT_ID" =~ ^[0-9]+$ ]]; then
        wpctl set-volume "$BT_OUTPUT_ID" 1.5
    fi

    if [ "$DEST" = "headset" ]; then
        echo "Playing $FILE on $BT_DEVICE_NAME..."
        pw-play --target "$BT_OUTPUT_ID" "$FULL_PATH"
        sleep 1
        exit 0
    fi

    if [ "$DEST" = "website" ]; then
        echo "Serving $FILE on port $PORT..."
        echo "Open: http://$(hostname -I | awk '{print $1}'):$PORT/play.wav"

        {
            printf "HTTP/1.1 200 OK\r\n"
            printf "Content-Type: audio/wav\r\n"
            printf "Cache-Control: no-cache\r\n"
            printf "Connection: close\r\n\r\n"
            cat "$FULL_PATH"
        } | nc -l -p "$PORT"
        sleep 1
        exit 0
    fi
fi

# --- MONITOR MODE ---
if [ "$MODE" = "monitor" ]; then
    echo "Starting low‑latency monitor mode..."
    echo "Press Ctrl+C to stop."

    # Boost mic gain safely
    if [[ "$BT_INPUT_ID" =~ ^[0-9]+$ ]]; then
        wpctl set-volume "$BT_INPUT_ID" 1.8
    fi

    # Force smaller PipeWire buffers for faster response
    pw-metadata -n settings 0 clock.force-rate 8000
    pw-metadata -n settings 0 clock.force-quantum 64

    # Direct playback with ffplay (requires ffmpeg installed)
    pw-record --target "$BT_INPUT_ID" --rate 8000 --channels 1 --format s16 - | \
        ffplay -nodisp -autoexit -f s16le -ar 8000 -
fi
