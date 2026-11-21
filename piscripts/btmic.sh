
#!/bin/bash
# bt_record.sh — record, stream, or playback Bluetooth audio
# Check headset nodes before starting audio.

REC_DIR="/home/q/recorded"
PORT=8000

mkdir -p "$REC_DIR"

echo "🔍 Checking Bluetooth headset status..."
if ! NODES=$(pw-cli ls Node); then
    echo "Bluetooth audio nodes unavailable"
    exit 1
fi
find_node() {
    printf '%s\n' "$NODES" | awk -v direction="$1" '
        /^[[:space:]]*id [0-9]+, type PipeWire:Interface:Node/ {
            id = $2
            sub(/,$/, "", id)
        }
        direction == "input" && /node.name = "bluez_input\./ { print id; exit }
        direction == "output" && /node.name = "bluez_(output|sink)\./ { print id; exit }
    '
}
BT_INPUT_ID=$(find_node input)
BT_OUTPUT_ID=$(find_node output)
BT_DEVICE_NAME="Bluetooth headset"
if [ -z "$BT_INPUT_ID" ] && [ -z "$BT_OUTPUT_ID" ]; then
    echo "Bluetooth headset not detected"
    exit 1
fi

# Friendly output node label
if [ -n "$BT_OUTPUT_ID" ]; then
    OUTPUT_LABEL="headset ($BT_OUTPUT_ID)"
else
    OUTPUT_LABEL="none"
fi

echo "🎙️ Input node: ${BT_INPUT_ID:-none}"
echo "🎧 Output node: ${OUTPUT_LABEL}"


cleanup() {
    status=$?
    trap - INT TERM EXIT
    echo -e "\nCleaning up..."
    exit "$status"
}
echo "Choose mode: record / stream / playback / monitor"
read MODE

if { [ "$MODE" = "record" ] || [ "$MODE" = "stream" ] || [ "$MODE" = "monitor" ]; } &&
   ! [[ "$BT_INPUT_ID" =~ ^[0-9]+$ ]]; then
    echo "Bluetooth microphone input not detected"
    exit 1
fi
trap 'exit 130' INT
trap 'exit 143' TERM
trap cleanup EXIT

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
    OUT="$REC_DIR/rec_$TS.mp3"

    # Boost mic gain safely
    if [[ "$BT_INPUT_ID" =~ ^[0-9]+$ ]]; then
        wpctl set-volume "$BT_INPUT_ID" 1.5
    fi

    echo "Recording $SECS seconds from $BT_DEVICE_NAME in $DESC..."
    timeout "$SECS" sh -c 'pw-record --target "$1" --rate "$2" --channels 1 --format "$3" --latency 20ms - | ffmpeg -hide_banner -loglevel error -f s16le -ar "$2" -ac 1 -i - -c:a libmp3lame -b:a 64k -write_xing 0 -flush_packets 1 "$4"' sh "$BT_INPUT_ID" "$RATE" "$FORMAT" "$OUT"
    echo "Saved: $OUT"
    sleep 2
    exit 0
fi

# --- STREAM MODE ---
if [ "$MODE" = "stream" ]; then
    echo "Starting live stream on port $PORT..."
    echo "Streaming locally on 127.0.0.1:$PORT"

    if ! LISTENERS=$(ss -H -ltn "sport = :$PORT"); then
        echo "Could not check the audio port"
        exit 1
    fi
    if [ -n "$LISTENERS" ]; then
        echo "Audio port $PORT is already in use"
        exit 1
    fi

    # Boost mic gain safely
    if [[ "$BT_INPUT_ID" =~ ^[0-9]+$ ]]; then
        wpctl set-volume "$BT_INPUT_ID" 1.5
    fi

    # Serve continuous audio stream
    while true; do
        {
            printf "HTTP/1.1 200 OK\r\n"
            printf "Content-Type: audio/mpeg\r\n"
            printf "Cache-Control: no-cache\r\n"
            printf "Connection: close\r\n\r\n"

            # Encode live PCM as MP3 so browser audio elements can start playback.
            pw-record --target "$BT_INPUT_ID" --rate 16000 --channels 1 --format s16 --latency 20ms - 2>/dev/null | \
                ffmpeg -hide_banner -loglevel error -fflags nobuffer -f s16le -ar 16000 -ac 1 -i - \
                -c:a libmp3lame -b:a 64k -write_xing 0 -flush_packets 1 -f mp3 - 2>/dev/null
        } | socat - TCP-LISTEN:$PORT,bind=127.0.0.1,reuseaddr || {
            echo "Audio listener failed"
            exit 1
        }
    done
fi


# -- PLAYBACK MODE ---
if [ "$MODE" = "playback" ]; then
    echo "Available recordings:"
    ls "$REC_DIR"/*.mp3 "$REC_DIR"/*.wav 2>/dev/null || echo "No recordings found."
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
        echo "Open: http://$(hostname -I | awk '{print $1}'):$PORT/play.mp3"

        {
            printf "HTTP/1.1 200 OK\r\n"
            printf "Content-Type: audio/mpeg\r\n"
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
    pw-record --target "$BT_INPUT_ID" --rate 8000 --channels 1 --format s16 --latency 10ms - | \
        ffplay -nodisp -autoexit -f s16le -ar 8000 -
fi
