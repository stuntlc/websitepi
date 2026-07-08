#!/bin/bash
echo "Content-type: text/plain"
echo ""

cd /home/q/websd

# Find newest .jpg or .jpeg (excluding protected files)
NEWEST=$(ls -t *.jpg *.jpeg 2>/dev/null \
    | grep -v "^1\.jpeg$" \
    | grep -v "^skunk-bg\.jpg$" \
    | grep -v "^skunk-logo\.png$" \
    | head -n 1)

echo "Newest file: $NEWEST"

# Loop through all jpg/jpeg files
for f in *.jpg *.jpeg; do

    # Skip protected files
    case "$f" in
        "1.jpeg"|"skunk-bg.jpg"|"skunk-logo.png")
            continue
            ;;
    esac

    # Skip newest file
    if [ "$f" = "$NEWEST" ]; then
        continue
    fi

    # Delete everything else
    rm "$f"
    echo "Deleted: $f"
done

echo "Cleanup complete."
