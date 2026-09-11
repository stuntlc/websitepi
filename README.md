<img width="1335" height="561" alt="image" src="https://github.com/user-attachments/assets/c8628458-28b7-4389-99c7-dc5f56eea0e2" />
a website for pi that can read sensors from ads1115 and vma407 and read volts via a 2 alligator clips 
<img width="1335" height="552" alt="image" src="https://github.com/user-attachments/assets/a0649d76-f372-4d39-a468-0e326aae6dbe" />

## Phone listening

The main page has a `Listen` control for the Android phone. The old camera/microphone privacy controls were removed because they are not a reliable way to control an app microphone stream on LineageOS.

`Listen` accepts either `PHONE_AUDIO_URL`, pointing to a browser-playable HTTP audio stream supplied by CaptureCap or AndroidMic, or `PHONE_AUDIO_COMMAND`, which must write that stream to standard output. Set `PHONE_AUDIO_CONTENT_TYPE` to match the stream (the default is `audio/mpeg`). For RTMP, SRT, or another non-browser protocol, use ffmpeg in `PHONE_AUDIO_COMMAND` to convert it to MP3 or AAC.

The `Start audio app` button launches AndroidMic through ADB using `PHONE_AUDIO_APP_PACKAGE` and `PHONE_AUDIO_APP_ACTIVITY`. The defaults are `io.github.teamclouday.AndroidMic` and `io.github.teamclouday.androidMic.ui.MainActivity`. These can be overridden if the app changes its component name.

For AndroidMic's ADB mode, the launcher also creates `adb reverse tcp:666 tcp:666` (override the port with `PHONE_AUDIO_ADB_PORT`). In AndroidMic, select **USB ADB**, port `666`, audio format `i16`, sample rate `44100`, and mono, then connect. A compatible AndroidMic PC receiver must be listening on the same Pi port; the reverse tunnel carries AndroidMic's length-prefixed protobuf audio packets, not MP3 or browser audio directly. The receiver must convert those packets to PCM/WAV/MP3 for `phone-audio.cgi`.
