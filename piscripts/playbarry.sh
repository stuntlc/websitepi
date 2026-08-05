ffmpeg -i barry.mp3 -f s16le -acodec pcm_s16le -ac 2 -ar 44100 - | aplay -D hw:0,0 -f S16_LE -c 2 -r 44100
