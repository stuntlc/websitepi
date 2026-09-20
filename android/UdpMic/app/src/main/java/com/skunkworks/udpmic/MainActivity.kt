package com.skunkworks.udpmic

import android.Manifest
import android.app.Activity
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.TextView

class MainActivity : Activity() {

    private lateinit var hostInput: EditText
    private lateinit var portInput: EditText
    private lateinit var statusView: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val density = resources.displayMetrics.density
        val padding = (16 * density).toInt()

        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(padding, padding, padding, padding)
        }

        hostInput = EditText(this).apply {
            hint = "Pi host or IP"
            setText("10.0.0.1")
        }
        portInput = EditText(this).apply {
            hint = "UDP port"
            setText("9100")
        }
        statusView = TextView(this).apply {
            text = "READY (also controllable via adb, see StreamService)"
            setPadding(0, padding, 0, 0)
        }

        val startButton = Button(this).apply { text = "Start streaming" }
        val stopButton = Button(this).apply { text = "Stop" }

        startButton.setOnClickListener { onStartClicked() }
        stopButton.setOnClickListener { stopStreaming() }

        root.addView(hostInput)
        root.addView(portInput)
        root.addView(startButton)
        root.addView(stopButton)
        root.addView(statusView)

        setContentView(root)
        requestRuntimePermissions()
    }

    private fun requestRuntimePermissions() {
        val needed = mutableListOf<String>()
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            needed += Manifest.permission.RECORD_AUDIO
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) {
            needed += Manifest.permission.POST_NOTIFICATIONS
        }
        if (needed.isNotEmpty()) {
            requestPermissions(needed.toTypedArray(), REQUEST_PERMISSIONS)
        }
    }

    private fun onStartClicked() {
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            requestRuntimePermissions()
            return
        }
        startStreaming()
    }

    private fun startStreaming() {
        val host = hostInput.text.toString().trim()
        val port = portInput.text.toString().trim().toIntOrNull()
        if (host.isEmpty() || port == null) {
            statusView.text = "Enter a valid host and port."
            return
        }

        val intent = Intent(this, StreamService::class.java)
            .putExtra(StreamService.EXTRA_HOST, host)
            .putExtra(StreamService.EXTRA_PORT, port)
        startForegroundService(intent)
        statusView.text = "STREAMING to $host:$port"
    }

    private fun stopStreaming() {
        val intent = Intent(this, StreamService::class.java).setAction(StreamService.ACTION_STOP)
        startService(intent)
        statusView.text = "STOPPED"
    }

    companion object {
        private const val REQUEST_PERMISSIONS = 1
    }
}
