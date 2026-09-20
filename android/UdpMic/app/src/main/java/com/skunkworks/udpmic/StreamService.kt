package com.skunkworks.udpmic

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Intent
import android.content.pm.ServiceInfo
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.os.Build
import android.os.IBinder
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress

/** Runs the mic-capture/UDP loop as a foreground service so adb can start/stop it headlessly. */
class StreamService : Service() {

    private val sampleRate = 16000
    private val chunkMillis = 40
    private var worker: Thread? = null

    @Volatile
    private var streaming = false

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP) {
            stopStreaming()
            return START_NOT_STICKY
        }

        val host = intent?.getStringExtra(EXTRA_HOST)
        val port = intent?.getIntExtra(EXTRA_PORT, DEFAULT_PORT) ?: DEFAULT_PORT
        startForegroundNotification()
        if (host != null) startStreaming(host, port)
        return START_NOT_STICKY
    }

    private fun startForegroundNotification() {
        val channelId = "udpmic-stream"
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val manager = getSystemService(NotificationManager::class.java)
            manager?.createNotificationChannel(
                NotificationChannel(channelId, "UDP Mic Streaming", NotificationManager.IMPORTANCE_LOW)
            )
        }
        val notification = Notification.Builder(this, channelId)
            .setContentTitle("UDP Mic")
            .setContentText("Streaming microphone audio")
            .setSmallIcon(android.R.drawable.ic_btn_speak_now)
            .build()

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            startForeground(NOTIFICATION_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE)
        } else {
            startForeground(NOTIFICATION_ID, notification)
        }
    }

    private fun startStreaming(host: String, port: Int) {
        if (streaming) return
        streaming = true
        worker = Thread { runStreaming(host, port) }.also { it.start() }
    }

    private fun runStreaming(host: String, port: Int) {
        val chunkSize = sampleRate * 2 * chunkMillis / 1000
        val minBuffer = AudioRecord.getMinBufferSize(
            sampleRate, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT
        )
        val bufferSize = maxOf(minBuffer, chunkSize * 4)

        var audioRecord: AudioRecord? = null
        var socket: DatagramSocket? = null
        try {
            audioRecord = AudioRecord(
                MediaRecorder.AudioSource.MIC,
                sampleRate,
                AudioFormat.CHANNEL_IN_MONO,
                AudioFormat.ENCODING_PCM_16BIT,
                bufferSize
            )
            socket = DatagramSocket()
            val address = InetAddress.getByName(host)
            val buffer = ByteArray(chunkSize)

            audioRecord.startRecording()
            while (streaming) {
                val read = audioRecord.read(buffer, 0, buffer.size)
                if (read > 0) {
                    socket.send(DatagramPacket(buffer, read, address, port))
                }
            }
        } catch (error: Exception) {
            streaming = false
        } finally {
            audioRecord?.stop()
            audioRecord?.release()
            socket?.close()
        }
    }

    private fun stopStreaming() {
        streaming = false
        worker = null
        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    override fun onDestroy() {
        streaming = false
        super.onDestroy()
    }

    companion object {
        const val ACTION_STOP = "com.skunkworks.udpmic.STOP"
        const val EXTRA_HOST = "host"
        const val EXTRA_PORT = "port"
        const val DEFAULT_PORT = 9100
        private const val NOTIFICATION_ID = 42
    }
}
