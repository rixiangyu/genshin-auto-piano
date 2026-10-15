package com.genshin.piano.perm

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Environment
import android.provider.Settings
import androidx.core.content.ContextCompat

/**
 * 权限工具：App 启动时检查，缺则主动申请。
 * 需要 ① 所有文件访问 ② 悬浮窗 ③ 无障碍 ④ 通知（前台服务用）。
 */
object Permissions {

    private const val ACCESSIBILITY_SERVICE =
        "com.genshin.piano/com.genshin.piano.access.AccessibilityClickService"

    /** 所有文件访问（Android 11+ 用 MANAGE_EXTERNAL_STORAGE；以下退化为读存储） */
    fun hasAllFiles(context: Context): Boolean =
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            Environment.isExternalStorageManager()
        } else {
            ContextCompat.checkSelfPermission(
                context, Manifest.permission.READ_EXTERNAL_STORAGE
            ) == PackageManager.PERMISSION_GRANTED
        }

    /** 悬浮窗权限 */
    fun hasOverlay(context: Context): Boolean = Settings.canDrawOverlays(context)

    /** 无障碍服务是否已开启 */
    fun hasAccessibility(context: Context): Boolean {
        val enabled = Settings.Secure.getString(
            context.contentResolver,
            Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES
        ) ?: return false
        return enabled.split(':').any { it.equals(ACCESSIBILITY_SERVICE, ignoreCase = true) }
    }

    /** 通知权限（Android 13+，前台服务需要） */
    fun hasNotifications(context: Context): Boolean =
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            ContextCompat.checkSelfPermission(
                context, Manifest.permission.POST_NOTIFICATIONS
            ) == PackageManager.PERMISSION_GRANTED
        } else true

    fun allGranted(context: Context): Boolean =
        hasAllFiles(context) && hasOverlay(context) &&
            hasAccessibility(context) && hasNotifications(context)

    // ---------------- 申请 ----------------

    fun requestAllFiles(context: Context) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            val appIntent = Intent(
                Settings.ACTION_MANAGE_APP_ALL_FILES_ACCESS_PERMISSION,
                Uri.parse("package:${context.packageName}")
            ).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            runCatching { context.startActivity(appIntent) }.onFailure {
                context.startActivity(
                    Intent(Settings.ACTION_MANAGE_ALL_FILES_ACCESS_PERMISSION)
                        .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                )
            }
        }
    }

    fun requestOverlay(context: Context) {
        context.startActivity(
            Intent(
                Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                Uri.parse("package:${context.packageName}")
            ).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        )
    }

    fun requestAccessibility(context: Context) {
        context.startActivity(
            Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        )
    }
}
