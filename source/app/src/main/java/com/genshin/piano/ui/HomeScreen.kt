package com.genshin.piano.ui

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Handler
import android.os.Looper
import android.provider.OpenableColumns
import android.widget.Toast
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
import androidx.compose.material.icons.filled.Close
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
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
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

/** 曲库列表最多显示几行，超出后列表内部滑动 */
private const val SONG_VISIBLE_ROWS = 5

/** 单行高度（dp），用于算列表的最大高度 */
private const val SONG_ROW_DP = 38

/** 文件选择器只显示这些 MIDI 类型 */
private val MIDI_MIME = arrayOf("audio/midi", "audio/x-midi", "audio/mid", "application/x-midi")

/** 主界面：导入 MIDI · 曲库 · 内置播放器（21 键点动）· 启动连点器 */
@Composable
fun HomeScreen(onOpenPermissions: () -> Unit = {}) {
    val context = LocalContext.current
    val store = remember { SongList(context) }
    val songs = remember { mutableStateListOf<Song>().apply { addAll(store.load()) } }
    val selected = remember { mutableStateOf(if (songs.isEmpty()) -1 else 0) }
    // 曲库被增删后手动触发一次重新解析（选中项索引可能没变，但内容变了）
    val reloadTick = remember { mutableStateOf(0) }

    val mainHandler = remember { Handler(Looper.getMainLooper()) }
    val playing = remember { mutableStateOf(false) }
    val keyActive = remember { mutableStateListOf<Boolean>().apply { repeat(21) { add(false) } } }
    val curSec = remember { mutableStateOf(0.0) }
    val totalSec = remember { mutableStateOf(0.0) }
    val nowNotes = remember { mutableStateOf("") }

    // 无障碍状态需要跟着「从系统设置页返回」刷新
    var permTick by remember { mutableStateOf(0) }
    val lifecycleOwner = LocalLifecycleOwner.current
    DisposableEffect(lifecycleOwner) {
        val obs = LifecycleEventObserver { _, e ->
            if (e == Lifecycle.Event.ON_RESUME) permTick++
        }
        lifecycleOwner.lifecycle.addObserver(obs)
        onDispose { lifecycleOwner.lifecycle.removeObserver(obs) }
    }

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

    // 选中曲目变化（或曲库增删）→ 解析 MIDI（IO 线程）并装载引擎
    LaunchedEffect(selected.value, reloadTick.value) {
        val s = songs.getOrNull(selected.value)
        engine.stop()
        curSec.value = 0.0
        keyActive.indices.forEach { keyActive[it] = false }
        if (s == null) {
            totalSec.value = 0.0
            nowNotes.value = ""
            return@LaunchedEffect
        }
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
            nowNotes.value = "无法解析「${s.name}」（可能不是标准 MIDI）"
        }
    }

    val picker = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocument()) { uri ->
        if (uri == null) return@rememberLauncherForActivityResult
        val name = queryDisplayName(context, uri) ?: "未命名.mid"

        // 只认标准 MIDI：读文件头前 4 字节必须是 "MThd"
        if (!isMidiFile(context, uri)) {
            Toast.makeText(context, "不是 MIDI 文件：$name", Toast.LENGTH_SHORT).show()
            return@rememberLauncherForActivityResult
        }
        if (songs.any { it.uri == uri.toString() }) {
            Toast.makeText(context, "「$name」已经在曲库里了", Toast.LENGTH_SHORT).show()
            return@rememberLauncherForActivityResult
        }
        runCatching {
            context.contentResolver.takePersistableUriPermission(uri, Intent.FLAG_GRANT_READ_URI_PERMISSION)
        }
        songs.add(Song(uri.toString(), name))
        store.save(songs)
        selected.value = songs.size - 1
        reloadTick.value++
    }

    fun deleteSelected() {
        val i = selected.value
        if (i < 0 || i >= songs.size) return
        engine.stop()
        curSec.value = 0.0
        val removed = songs.removeAt(i)
        store.save(songs)
        selected.value = if (songs.isEmpty()) -1 else i.coerceAtMost(songs.size - 1)
        reloadTick.value++
        Toast.makeText(context, "已删除：${removed.name}", Toast.LENGTH_SHORT).show()
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
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text("曲库", color = Gold, fontSize = 12.sp, fontWeight = FontWeight.Bold)
                    Spacer(Modifier.weight(1f))
                    if (songs.isNotEmpty()) {
                        Text(
                            "共 ${songs.size} 首" + if (songs.size > SONG_VISIBLE_ROWS) " · 可上下滑动" else "",
                            color = TextMute, fontSize = 11.sp,
                        )
                    }
                }
                Spacer(Modifier.height(9.dp))

                // 导入 + 删除（同一行，按钮做小）
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Button(
                        onClick = { picker.launch(MIDI_MIME) },
                        modifier = Modifier.height(34.dp),
                        contentPadding = PaddingValues(horizontal = 12.dp, vertical = 0.dp),
                        shape = RoundedCornerShape(9.dp),
                        colors = ButtonDefaults.buttonColors(
                            containerColor = Gold, contentColor = Color(0xFF2A2005),
                        ),
                    ) {
                        Icon(Icons.Filled.Add, null, Modifier.size(15.dp))
                        Spacer(Modifier.width(4.dp))
                        Text("导入 MIDI", fontSize = 12.sp, fontWeight = FontWeight.Bold)
                    }
                    Spacer(Modifier.width(8.dp))
                    OutlinedButton(
                        onClick = { deleteSelected() },
                        enabled = selected.value >= 0,
                        modifier = Modifier.height(34.dp),
                        contentPadding = PaddingValues(horizontal = 12.dp, vertical = 0.dp),
                        shape = RoundedCornerShape(9.dp),
                        colors = ButtonDefaults.outlinedButtonColors(disabledContentColor = TextMute),
                    ) {
                        Icon(
                            Icons.Filled.Close, null, Modifier.size(15.dp),
                            tint = if (selected.value >= 0) Danger else TextMute,
                        )
                        Spacer(Modifier.width(4.dp))
                        Text(
                            if (songs.isEmpty()) "删除" else "删除选中",
                            fontSize = 12.sp,
                            color = if (selected.value >= 0) Danger else TextMute,
                        )
                    }
                }
                Spacer(Modifier.height(10.dp))

                if (songs.isEmpty()) {
                    Text(
                        "还没有曲目，点「导入 MIDI」添加（只识别 .mid / .midi）",
                        color = TextMute, fontSize = 12.sp,
                    )
                } else {
                    // 最多显示 5 行，再多的在列表内部滑动
                    Column(
                        Modifier
                            .fillMaxWidth()
                            .heightIn(max = (SONG_ROW_DP * SONG_VISIBLE_ROWS).dp)
                            .verticalScroll(rememberScrollState())
                    ) {
                        songs.forEachIndexed { i, s ->
                            val cur = i == selected.value
                            Row(
                                Modifier.fillMaxWidth().clip(RoundedCornerShape(9.dp))
                                    .background(if (cur) BgInput else Color.Transparent)
                                    .clickable { selected.value = i }
                                    .padding(horizontal = 10.dp, vertical = 9.dp),
                                verticalAlignment = Alignment.CenterVertically,
                            ) {
                                Box(
                                    Modifier.size(6.dp).clip(RoundedCornerShape(3.dp))
                                        .background(if (cur) Gold else BorderC)
                                )
                                Spacer(Modifier.width(10.dp))
                                Text(
                                    s.name,
                                    color = if (cur) Gold else TextSecondary,
                                    fontSize = 13.sp,
                                    maxLines = 1,
                                    modifier = Modifier.weight(1f),
                                )
                            }
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
                OutlinedButton(
                    onClick = { stopOverlay(context) },
                    shape = RoundedCornerShape(10.dp),
                    modifier = Modifier.height(36.dp),
                    contentPadding = PaddingValues(horizontal = 12.dp, vertical = 0.dp),
                ) {
                    Icon(Icons.Filled.Close, null, Modifier.size(16.dp), tint = Danger)
                    Spacer(Modifier.width(6.dp))
                    Text("关闭悬浮窗", color = Danger, fontSize = 13.sp)
                }
                Spacer(Modifier.height(8.dp))
                Text(
                    "悬浮条默认折叠（只有 ▶ 和 ♪）；点 ♪ 展开全部控件，拖 ▶ 或 ♪ 可移动整条。" +
                        "关悬浮窗有三种方式：条上的 ✕、这里的按钮、或通知栏的「关闭悬浮窗」。",
                    color = TextMute, fontSize = 11.sp,
                )
            }
        }

        Spacer(Modifier.height(14.dp))
        val acc = remember(permTick) { Permissions.hasAccessibility(context) }
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(
                "无障碍：" + if (acc) "已开启 ✓" else "未开启（连点不可用）",
                color = if (acc) Success else Danger, fontSize = 12.sp,
            )
            Spacer(Modifier.weight(1f))
            TextButton(
                onClick = onOpenPermissions,
                contentPadding = PaddingValues(horizontal = 10.dp, vertical = 0.dp),
            ) { Text("权限设置", color = Gold, fontSize = 12.sp) }
        }
        Spacer(Modifier.height(20.dp))
    }
}

private fun startOverlay(context: Context, calibrate: Boolean) {
    val i = Intent(context, OverlayClickerService::class.java)
        .putExtra(OverlayClickerService.EXTRA_CALIBRATE, calibrate)
    context.startForegroundService(i)
}

/** 关闭悬浮窗（停止服务，两个覆盖窗口随之移除） */
private fun stopOverlay(context: Context) {
    context.stopService(Intent(context, OverlayClickerService::class.java))
    Toast.makeText(context, "已关闭悬浮窗", Toast.LENGTH_SHORT).show()
}

/** 真正判断是不是标准 MIDI：读文件头前 4 字节，必须是 "MThd" */
private fun isMidiFile(context: Context, uri: Uri): Boolean = runCatching {
    context.contentResolver.openInputStream(uri)?.use { ins ->
        val head = ByteArray(4)
        ins.read(head) == 4 && String(head, Charsets.US_ASCII) == "MThd"
    } ?: false
}.getOrDefault(false)

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
