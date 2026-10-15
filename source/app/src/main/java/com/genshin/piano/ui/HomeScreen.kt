package com.genshin.piano.ui

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Handler
import android.os.Looper
import android.provider.OpenableColumns
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Pause
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material.icons.filled.Tune
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.genshin.piano.data.KeymapAdapter
import com.genshin.piano.data.Song
import com.genshin.piano.data.SongList
import com.genshin.piano.midi.MidiParser
import com.genshin.piano.overlay.OverlayClickerService
import com.genshin.piano.perm.Permissions
import com.genshin.piano.play.PlayerEngine
import com.genshin.piano.play.PlayerState
import com.genshin.piano.ui.theme.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/** 主界面：导入 MIDI · 曲库 · 内置播放器（21 键点动）· 启动连点器 */
@Composable
fun HomeScreen() {
    val context = LocalContext.current
    val store = remember { SongList(context) }
    val songs = remember { mutableStateListOf<Song>().apply { addAll(store.load()) } }
    val selected = remember { mutableStateOf(if (songs.isEmpty()) -1 else 0) }

    val mainHandler = remember { Handler(Looper.getMainLooper()) }
    val playing = remember { mutableStateOf(false) }
    val keyActive = remember { mutableStateListOf<Boolean>().apply { repeat(21) { add(false) } } }
    val curSec = remember { mutableStateOf(0.0) }
    val totalSec = remember { mutableStateOf(0.0) }
    val nowNotes = remember { mutableStateOf("") }

    val engine = remember {
        PlayerEngine(
            keymap = KeymapAdapter(autoAdapt = true),
            onNoteStart = { idx, _ -> mainHandler.post { keyActive[idx] = true } },
            onNoteEnd = { idx -> mainHandler.post { keyActive[idx] = false } },
            onProgress = { cur, tot, notes -> mainHandler.post {
                curSec.value = cur; totalSec.value = tot; nowNotes.value = notes.joinToString(" ")
            } },
            onFinished = { mainHandler.post { nowNotes.value = "播放结束" } },
            onState = { s -> mainHandler.post { playing.value = (s == PlayerState.PLAYING) } },
        )
    }
    DisposableEffect(Unit) { onDispose { engine.stop() } }

    // 选中曲目变化 → 解析 MIDI（IO 线程）并装载引擎
    LaunchedEffect(selected.value) {
        val s = songs.getOrNull(selected.value) ?: return@LaunchedEffect
        engine.stop()
        curSec.value = 0.0
        keyActive.indices.forEach { keyActive[it] = false }
        val data = withContext(Dispatchers.IO) {
            runCatching {
                context.contentResolver.openInputStream(Uri.parse(s.uri))?.use { MidiParser.parse(it) }
            }.getOrNull()
        }
        if (data != null) {
            engine.load(data)
            totalSec.value = data.totalDuration
            nowNotes.value = "已加载 ${s.name} · ${data.events.size} 音符 · 可演奏 ${engine.playableCount}" +
                if (data.hasChords) " · 含和弦" else ""
        } else {
            nowNotes.value = "无法解析该文件"
        }
    }

    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri != null) {
            runCatching {
                context.contentResolver.takePersistableUriPermission(uri, Intent.FLAG_GRANT_READ_URI_PERMISSION)
            }
            val name = queryDisplayName(context, uri) ?: "未命名.mid"
            songs.add(Song(uri.toString(), name))
            store.save(songs)
            selected.value = songs.size - 1
        }
    }

    Column(
        Modifier.fillMaxSize().background(BgDark).verticalScroll(rememberScrollState()).padding(18.dp)
    ) {
        // 标题
        Row(verticalAlignment = Alignment.CenterVertically) {
            Box(
                Modifier.size(36.dp).clip(RoundedCornerShape(10.dp)).background(Gold),
                contentAlignment = Alignment.Center,
            ) { Text("♪", color = Color(0xFF2A2005), fontWeight = FontWeight.Bold, fontSize = 18.sp) }
            Spacer(Modifier.width(10.dp))
            Column {
                Text("原神自动弹琴", color = TextPrimary, fontSize = 18.sp, fontWeight = FontWeight.Bold)
                Text("MIDI → 21 键 · 自动演奏", color = TextMute, fontSize = 11.sp)
            }
        }
        Spacer(Modifier.height(16.dp))

        // 曲库
        Card(colors = CardDefaults.cardColors(containerColor = BgCard), shape = RoundedCornerShape(14.dp)) {
            Column(Modifier.padding(14.dp)) {
                Text("曲库", color = Gold, fontSize = 12.sp, fontWeight = FontWeight.Bold)
                Spacer(Modifier.height(10.dp))
                Button(
                    onClick = { picker.launch(arrayOf("*/*")) },
                    colors = ButtonDefaults.buttonColors(containerColor = Gold, contentColor = Color(0xFF2A2005)),
                    shape = RoundedCornerShape(10.dp),
                ) {
                    Icon(Icons.Filled.Add, null, Modifier.size(18.dp)); Spacer(Modifier.width(6.dp))
                    Text("导入 MIDI", fontWeight = FontWeight.Bold)
                }
                Spacer(Modifier.height(10.dp))
                if (songs.isEmpty()) {
                    Text("还没有曲目，点上方按钮导入 MIDI 文件", color = TextMute, fontSize = 12.sp)
                } else {
                    songs.forEachIndexed { i, s ->
                        val cur = i == selected.value
                        Row(
                            Modifier.fillMaxWidth().clip(RoundedCornerShape(9.dp))
                                .background(if (cur) BgInput else Color.Transparent)
                                .clickable { selected.value = i }
                                .padding(horizontal = 10.dp, vertical = 9.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Box(Modifier.size(6.dp).clip(RoundedCornerShape(3.dp)).background(if (cur) Gold else BorderC))
                            Spacer(Modifier.width(10.dp))
                            Text(s.name, color = if (cur) Gold else TextSecondary, fontSize = 13.sp, modifier = Modifier.weight(1f))
                        }
                    }
                }
            }
        }

        Spacer(Modifier.height(14.dp))

        // 内置播放器（含 21 键点动痕迹）
        Card(colors = CardDefaults.cardColors(containerColor = BgCard), shape = RoundedCornerShape(14.dp)) {
            Column(Modifier.padding(14.dp)) {
                Text("内置播放器", color = Gold, fontSize = 12.sp, fontWeight = FontWeight.Bold)
                Spacer(Modifier.height(6.dp))
                Text(nowNotes.value.ifBlank { "选择曲目后可试听" }, color = TextSecondary, fontSize = 12.sp)
                Spacer(Modifier.height(10.dp))
                PianoGrid(active = keyActive, modifier = Modifier.fillMaxWidth())
                Spacer(Modifier.height(12.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Button(
                        onClick = { engine.togglePause() },
                        enabled = selected.value >= 0,
                        colors = ButtonDefaults.buttonColors(
                            containerColor = Gold, contentColor = Color(0xFF2A2005),
                            disabledContainerColor = BgInput, disabledContentColor = TextMute,
                        ),
                        shape = RoundedCornerShape(10.dp),
                    ) {
                        Icon(if (playing.value) Icons.Filled.Pause else Icons.Filled.PlayArrow, null, Modifier.size(18.dp))
                        Spacer(Modifier.width(6.dp))
                        Text(if (playing.value) "暂停" else "播放", fontWeight = FontWeight.Bold)
                    }
                    Spacer(Modifier.width(8.dp))
                    OutlinedButton(
                        onClick = { engine.stop(); curSec.value = 0.0 },
                        shape = RoundedCornerShape(10.dp),
                    ) {
                        Icon(Icons.Filled.Stop, null, Modifier.size(18.dp), tint = TextSecondary)
                        Spacer(Modifier.width(6.dp)); Text("停止", color = TextSecondary)
                    }
                    Spacer(Modifier.width(12.dp))
                    Text(
                        String.format("%.1f / %.1f s", curSec.value, totalSec.value),
                        color = TextMute, fontSize = 12.sp,
                    )
                }
                Spacer(Modifier.height(8.dp))
                LinearProgressIndicator(
                    progress = {
                        if (totalSec.value > 0) (curSec.value / totalSec.value).toFloat().coerceIn(0f, 1f) else 0f
                    },
                    modifier = Modifier.fillMaxWidth().height(6.dp).clip(RoundedCornerShape(3.dp)),
                    color = Gold, trackColor = BgInput,
                )
            }
        }

        Spacer(Modifier.height(14.dp))

        // 执行器
        Card(colors = CardDefaults.cardColors(containerColor = BgCard), shape = RoundedCornerShape(14.dp)) {
            Column(Modifier.padding(14.dp)) {
                Text("连点器 · 悬浮窗（游戏内）", color = Gold, fontSize = 12.sp, fontWeight = FontWeight.Bold)
                Spacer(Modifier.height(10.dp))
                Row {
                    Button(
                        onClick = { startOverlay(context, calibrate = false) },
                        colors = ButtonDefaults.buttonColors(containerColor = Gold, contentColor = Color(0xFF2A2005)),
                        shape = RoundedCornerShape(10.dp),
                    ) { Text("显示连点器", fontWeight = FontWeight.Bold) }
                    Spacer(Modifier.width(8.dp))
                    OutlinedButton(onClick = { startOverlay(context, calibrate = true) }, shape = RoundedCornerShape(10.dp)) {
                        Icon(Icons.Filled.Tune, null, Modifier.size(18.dp), tint = Gold)
                        Spacer(Modifier.width(6.dp)); Text("校准点位", color = Gold)
                    }
                }
                Spacer(Modifier.height(8.dp))
                Text("打开原神进入弹琴界面后点「显示连点器」；要移动点位请点悬浮条上的「校」，「校」高亮时即可拖动（拖圆点=单个，拖空白=整体）。", color = TextMute, fontSize = 11.sp)
            }
        }

        Spacer(Modifier.height(14.dp))
        val acc = Permissions.hasAccessibility(context)
        Text("无障碍：" + if (acc) "已开启 ✓" else "未开启（连点不可用）", color = if (acc) Success else Danger, fontSize = 12.sp)
        Spacer(Modifier.height(20.dp))
    }
}

private fun startOverlay(context: Context, calibrate: Boolean) {
    val i = Intent(context, OverlayClickerService::class.java)
        .putExtra(OverlayClickerService.EXTRA_CALIBRATE, calibrate)
    context.startForegroundService(i)
}

private fun queryDisplayName(context: Context, uri: Uri): String? {
    var name: String? = null
    context.contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { c ->
        if (c.moveToFirst()) {
            val idx = c.getColumnIndex(OpenableColumns.DISPLAY_NAME)
            if (idx >= 0) name = c.getString(idx)
        }
    }
    return name ?: uri.lastPathSegment?.substringAfterLast('/')
}
