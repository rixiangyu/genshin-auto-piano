package com.genshin.piano.perm

import android.app.Activity
import android.os.Build
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import com.genshin.piano.ui.theme.*

/**
 * 启动引导：逐项申请权限，全部到位后进入主界面。
 * 从系统设置页返回时会自动刷新状态。
 */
@Composable
fun OnboardingScreen(onDone: () -> Unit) {
    val context = LocalContext.current
    var tick by remember { mutableStateOf(0) }   // 变更时触发重新检查

    // 每次回到前台重新检查（从设置页返回时刷新）
    val lifecycleOwner = LocalLifecycleOwner.current
    DisposableEffect(lifecycleOwner) {
        val obs = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_RESUME) tick++
        }
        lifecycleOwner.lifecycle.addObserver(obs)
        onDispose { lifecycleOwner.lifecycle.removeObserver(obs) }
    }

    val notifLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { tick++ }

    // 读取当前各项状态（tick 变化时重算）
    val all = remember(tick) { Permissions.hasAllFiles(context) }
    val overlay = remember(tick) { Permissions.hasOverlay(context) }
    val access = remember(tick) { Permissions.hasAccessibility(context) }
    val notif = remember(tick) { Permissions.hasNotifications(context) }
    val done = all && overlay && access && notif

    Column(
        Modifier
            .fillMaxSize()
            .background(BgDark)
            .verticalScroll(rememberScrollState())
            .padding(24.dp)
    ) {
        Spacer(Modifier.height(24.dp))
        Text("原神自动弹琴", color = Gold, fontSize = 26.sp, fontWeight = FontWeight.Bold)
        Spacer(Modifier.height(6.dp))
        Text(
            "首次使用需要开启以下权限，全部到位后才能自动演奏。",
            color = TextSecondary, fontSize = 13.sp
        )
        Spacer(Modifier.height(22.dp))

        PermItem(
            index = 1,
            title = "所有文件访问",
            desc = "用于读取你选择的 MIDI 文件",
            granted = all,
        ) { Permissions.requestAllFiles(context) }

        PermItem(
            index = 2,
            title = "悬浮窗",
            desc = "显示 21 键连点器与悬浮控制条",
            granted = overlay,
        ) { Permissions.requestOverlay(context) }

        PermItem(
            index = 3,
            title = "无障碍服务",
            desc = "模拟点击屏幕琴键，仅在自动演奏时生效",
            granted = access,
        ) { Permissions.requestAccessibility(context) }

        PermItem(
            index = 4,
            title = "通知",
            desc = "前台服务运行提示（Android 13+）",
            granted = notif,
        ) {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                notifLauncher.launch(android.Manifest.permission.POST_NOTIFICATIONS)
            } else tick++
        }

        Spacer(Modifier.height(26.dp))
        Button(
            onClick = onDone,
            enabled = done,
            modifier = Modifier.fillMaxWidth().height(48.dp),
            shape = RoundedCornerShape(12.dp),
            colors = ButtonDefaults.buttonColors(
                containerColor = Gold,
                contentColor = Color(0xFF2A2005),
                disabledContainerColor = BgInput,
                disabledContentColor = TextMute,
            ),
        ) {
            Text(if (done) "进入应用" else "请先完成以上授权", fontWeight = FontWeight.Bold)
        }
        Spacer(Modifier.height(24.dp))
    }
}

@Composable
private fun PermItem(
    index: Int,
    title: String,
    desc: String,
    granted: Boolean,
    onRequest: () -> Unit,
) {
    Row(
        Modifier
            .fillMaxWidth()
            .padding(vertical = 4.dp)
            .clip(RoundedCornerShape(12.dp))
            .background(BgCard)
            .padding(14.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(
            Modifier
                .size(30.dp)
                .clip(RoundedCornerShape(9.dp))
                .background(if (granted) Success else BgInput),
            contentAlignment = Alignment.Center,
        ) {
            Text(
                if (granted) "✓" else "$index",
                color = if (granted) Color(0xFF0F2A12) else TextSecondary,
                fontWeight = FontWeight.Bold,
            )
        }
        Spacer(Modifier.width(12.dp))
        Column(Modifier.weight(1f)) {
            Text(title, color = TextPrimary, fontSize = 15.sp, fontWeight = FontWeight.Bold)
            Text(desc, color = TextMute, fontSize = 12.sp)
        }
        Spacer(Modifier.width(8.dp))
        if (granted) {
            Text("已开启", color = Success, fontSize = 13.sp, fontWeight = FontWeight.Bold)
        } else {
            OutlinedButton(
                onClick = onRequest,
                shape = RoundedCornerShape(9.dp),
            ) { Text("去开启", color = Gold) }
        }
    }
}
