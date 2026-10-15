package com.genshin.piano.overlay

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Intent
import android.graphics.Color as AColor
import android.graphics.PixelFormat
import android.graphics.drawable.GradientDrawable
import android.net.Uri
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.os.SystemClock
import android.text.TextUtils
import android.util.Log
import android.view.Gravity
import android.view.MotionEvent
import android.view.View
import android.view.WindowManager
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.Switch
import android.widget.TextView
import android.widget.Toast
import androidx.core.app.NotificationCompat
import com.genshin.piano.R
import com.genshin.piano.access.AccessibilityClickService
import com.genshin.piano.data.CalibrationStore
import com.genshin.piano.data.Keymap
import com.genshin.piano.data.KeymapAdapter
import com.genshin.piano.data.Song
import com.genshin.piano.data.SongList
import com.genshin.piano.midi.MidiParser
import com.genshin.piano.play.PlayerEngine
import com.genshin.piano.play.PlayerState
import kotlin.concurrent.thread

/**
 * 悬浮窗 + 21 键连点器（透明覆盖层）。
 *
 * 采用两个窗口：
 *  1) 控制条窗口：WRAP_CONTENT，可拖动，含开关 / 歌名 / 播放 / 选歌 / 隐藏点位。
 *  2) 点位窗口：仅覆盖 21 个点的包围盒；**非校准态设为不可触摸（FLAG_NOT_TOUCHABLE）**，
 *     保证不弹琴时完全不拦截游戏触摸 —— 图像不变、不误触。
 *
 * 坐标以百分比存储（CalibrationStore），运行时按屏幕尺寸换算像素。
 *
 * 播放：▶ 按钮驱动 PlayerEngine，音符回调 → 无障碍 dispatchGesture 点击对应点位。
 * 手势队列保证同一时刻只有一个手势在飞（同时按多个键/和弦待后续版本）。
 */
class OverlayClickerService : Service() {

    private lateinit var wm: WindowManager
    private lateinit var calib: CalibrationStore
    private lateinit var songStore: SongList
    private val mainHandler = Handler(Looper.getMainLooper())

    // 点位窗口
    private lateinit var pointsView: FrameLayout
    private lateinit var pointsLp: WindowManager.LayoutParams
    private val points = ArrayList<TextView>()

    // 控制条窗口
    private lateinit var barBox: LinearLayout
    private lateinit var barLp: WindowManager.LayoutParams
    private lateinit var barRow: LinearLayout
    private lateinit var songListBox: LinearLayout
    private lateinit var songLabel: TextView
    private lateinit var playChip: TextView
    private lateinit var eyeBtn: TextView
    private lateinit var calibChip: TextView
    private lateinit var calibHint: TextView

    private var calibrate = false
    private var enabled = true
    private var pointsVisible = true
    private var expanded = false
    private var songs: MutableList<Song> = mutableListOf()
    private var selectedSong = -1

    // 播放
    private var engine: PlayerEngine? = null
    private var loadedSongIndex = -1

    /** 一组待派发的点击（同刻和弦 = 一次手势的多条 stroke） */
    private data class TapGroup(val pts: List<Pair<Float, Float>>, val holdMs: Long, val queuedAtMs: Long)

    private val tapQueue = ArrayDeque<TapGroup>()
    private var tapBusy = false
    private var tapGen = 0

    // 诊断计数（真机调优用，Logcat 标签 PianoTap）
    private var statGroups = 0
    private var statDropped = 0
    private var statStrokeSum = 0
    private var statLagSum = 0L
    private var statMaxLag = 0L

    private val density get() = resources.displayMetrics.density
    private fun dp(v: Int) = (v * density).toInt()

    private val pointSize get() = dp(34)

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        startAsForeground()
        wm = getSystemService(WINDOW_SERVICE) as WindowManager
        calib = CalibrationStore(this)
        songStore = SongList(this)
        songs = songStore.load()
        if (songs.isNotEmpty()) selectedSong = 0

        buildPointsWindow()
        buildBarWindow()
        updatePointsLayout()
        applyPointsVisibility()
        applyPointsTouchable()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        // 服务可能是在用户导入 MIDI 之前就启动的，这里必须重新读一次曲库，
        // 否则悬浮窗永远显示"未选择曲目"。
        refreshSongs()
        if (intent?.getBooleanExtra(EXTRA_CALIBRATE, false) == true) {
            calibrate = true
            pointsVisible = true
            applyPointsVisibility()
            updateEyeChip()
            updateCalibChip()
            updateCalibHint()
            armCalibTimeout()
        }
        return START_STICKY
    }

    // ---------------- 前台通知 ----------------

    private fun startAsForeground() {
        val channelId = "piano_overlay"
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val nm = getSystemService(NOTIFICATION_SERVICE) as NotificationManager
            nm.createNotificationChannel(
                NotificationChannel(channelId, "连点器运行中", NotificationManager.IMPORTANCE_LOW)
            )
        }
        val notif = NotificationCompat.Builder(this, channelId)
            .setContentTitle("原神自动弹琴")
            .setContentText("悬浮连点器已就绪")
            .setSmallIcon(R.drawable.ic_launcher)
            .setOngoing(true)
            .build()
        startForeground(1001, notif)
    }

    // ---------------- 曲库 ----------------

    /** 重新读取曲库并刷新标题；曲目增删后调用 */
    private fun refreshSongs() {
        songs = songStore.load()
        if (selectedSong !in songs.indices) selectedSong = if (songs.isEmpty()) -1 else 0
        if (::songLabel.isInitialized) songLabel.text = selectedSongName()
        if (::songListBox.isInitialized && expanded) rebuildSongList()
    }

    // ---------------- 点位窗口 ----------------

    private fun buildPointsWindow() {
        pointsView = FrameLayout(this)
        Keymap.keys.forEachIndexed { i, k ->
            val tv = TextView(this).apply {
                text = "${k.pcKey}\n${k.label}"
                setTextColor(AColor.parseColor("#F4D88C"))
                textSize = 8f
                gravity = Gravity.CENTER
                background = circleDrawable()
            }
            tv.setOnTouchListener(pointTouch(i))
            pointsView.addView(tv, FrameLayout.LayoutParams(pointSize, pointSize))
            points.add(tv)
        }
        // 拖窗口空白处 = 整体平移 21 个点（跟拖单个圆点互不冲突）
        pointsView.setOnTouchListener(groupDragTouch())
        pointsLp = WindowManager.LayoutParams(
            dp(200), dp(200),
            overlayType(),
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or
                WindowManager.LayoutParams.FLAG_NOT_TOUCH_MODAL or
                WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN,
            PixelFormat.TRANSLUCENT
        ).apply { gravity = Gravity.TOP or Gravity.START }
        wm.addView(pointsView, pointsLp)
    }

    /** 依据百分比重新计算 21 点位置，并收缩窗口到包围盒 */
    private fun updatePointsLayout() {
        val dm = resources.displayMetrics
        val w = dm.widthPixels
        val h = dm.heightPixels
        val size = pointSize
        var minX = Int.MAX_VALUE; var minY = Int.MAX_VALUE
        var maxX = Int.MIN_VALUE; var maxY = Int.MIN_VALUE
        val px = IntArray(21); val py = IntArray(21)
        for (i in 0 until 21) {
            px[i] = (calib.x(i) / 100f * w).toInt()
            py[i] = (calib.y(i) / 100f * h).toInt()
            if (px[i] < minX) minX = px[i]
            if (py[i] < minY) minY = py[i]
            if (px[i] > maxX) maxX = px[i]
            if (py[i] > maxY) maxY = py[i]
        }
        val pad = size / 2 + dp(2)
        val boxLeft = (minX - pad).coerceAtLeast(0)
        val boxTop = (minY - pad).coerceAtLeast(0)
        val boxW = (maxX - minX) + pad * 2
        val boxH = (maxY - minY) + pad * 2

        pointsLp.x = boxLeft
        pointsLp.y = boxTop
        pointsLp.width = boxW
        pointsLp.height = boxH
        runCatching { wm.updateViewLayout(pointsView, pointsLp) }

        for (i in 0 until 21) {
            val lp = points[i].layoutParams as FrameLayout.LayoutParams
            lp.leftMargin = px[i] - boxLeft - size / 2
            lp.topMargin = py[i] - boxTop - size / 2
            lp.width = size
            lp.height = size
            points[i].layoutParams = lp
        }
    }

    private fun pointTouch(i: Int): View.OnTouchListener = View.OnTouchListener { _, e ->
        if (!calibrate || !pointsVisible) return@OnTouchListener false
        when (e.actionMasked) {
            MotionEvent.ACTION_DOWN -> true
            MotionEvent.ACTION_MOVE -> {
                val dm = resources.displayMetrics
                calib.set(i, e.rawX / dm.widthPixels * 100f, e.rawY / dm.heightPixels * 100f)
                updatePointsLayout()
                true
            }
            MotionEvent.ACTION_UP -> { calib.save(); armCalibTimeout(); true }
            MotionEvent.ACTION_CANCEL -> { armCalibTimeout(); true }
            else -> false
        }
    }

    private fun applyPointsVisibility() {
        val v = if (pointsVisible) View.VISIBLE else View.GONE
        points.forEach { it.visibility = v }
        applyPointsTouchable()      // 隐藏 ⇒ 立即不可触摸
    }

    /** 拖动窗口空白处 → 整体平移 21 个点 */
    private fun groupDragTouch(): View.OnTouchListener {
        var lastX = 0f
        var lastY = 0f
        return View.OnTouchListener { _, e ->
            if (!calibrate || !pointsVisible) return@OnTouchListener false
            when (e.actionMasked) {
                MotionEvent.ACTION_DOWN -> {
                    lastX = e.rawX; lastY = e.rawY; true
                }
                MotionEvent.ACTION_MOVE -> {
                    val dm = resources.displayMetrics
                    val dxPct = (e.rawX - lastX) / dm.widthPixels * 100f
                    val dyPct = (e.rawY - lastY) / dm.heightPixels * 100f
                    lastX = e.rawX; lastY = e.rawY
                    for (i in 0 until 21) calib.set(i, calib.x(i) + dxPct, calib.y(i) + dyPct)
                    updatePointsLayout()
                    true
                }
                MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> {
                    calib.save(); armCalibTimeout(); true
                }
                else -> false
            }
        }
    }

    /**
     * 只有「校准中 **且** 点位可见」时才接收触摸。
     * 点位一被隐藏立刻变回不可触摸 —— 隐藏后既不能拖动，也绝不会挡住游戏。
     */
    private fun applyPointsTouchable() {
        val touchable = calibrate && pointsVisible
        pointsLp.flags = WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or
            WindowManager.LayoutParams.FLAG_NOT_TOUCH_MODAL or
            WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN or
            (if (touchable) 0 else WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE)
        runCatching { wm.updateViewLayout(pointsView, pointsLp) }
    }

    // ---------------- 控制条窗口 ----------------

    private fun buildBarWindow() {
        barBox = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            background = barBg()
        }
        barRow = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setPadding(dp(6), dp(5), dp(6), dp(5))
        }
        barBox.addView(barRow)

        // 校准模式下才显示的提示条
        calibHint = TextView(this).apply {
            text = "校准中 · 拖圆点微调 / 拖空白整体移动"
            setTextColor(AColor.parseColor("#E9C46A"))
            textSize = 10f
            gravity = Gravity.CENTER
            setPadding(dp(8), 0, dp(8), dp(6))
            visibility = View.GONE
        }
        barBox.addView(calibHint)

        val handle = iconChip("≡").apply { setOnTouchListener(barDragTouch()) }
        val sw = Switch(this).apply {
            isChecked = true
            setOnCheckedChangeListener { _, checked ->
                enabled = checked
                barBox.alpha = if (enabled) 1f else 0.75f
                if (!enabled) stopPlayback()
            }
        }
        songLabel = TextView(this).apply {
            text = selectedSongName()
            setTextColor(AColor.parseColor("#F4D88C"))
            textSize = 11f
            maxLines = 1
            ellipsize = TextUtils.TruncateAt.END
            gravity = Gravity.CENTER
            setPadding(dp(6), 0, dp(6), 0)
        }
        playChip = iconChip("▶").apply { setOnClickListener { togglePlay() } }
        val listBtn = iconChip("♪").apply {
            setOnClickListener { toggleExpanded() }
        }
        eyeBtn = iconChip("👁").apply {
            setOnClickListener {
                pointsVisible = !pointsVisible
                applyPointsVisibility()     // 内部同步触摸性：隐藏后不可拖动、不挡游戏
                updateEyeChip()
                toast(if (pointsVisible) "点位已显示" else "点位已隐藏（不可拖动、不挡操作）")
            }
        }
        calibChip = iconChip("校").apply { setOnClickListener { toggleCalibrate() } }

        barRow.addView(handle)
        barRow.addView(sw, LinearLayout.LayoutParams(dp(38), dp(22)).apply { marginStart = dp(4) })
        barRow.addView(songLabel, LinearLayout.LayoutParams(0, dp(30), 1f))
        barRow.addView(playChip)
        barRow.addView(listBtn)
        barRow.addView(eyeBtn)
        barRow.addView(calibChip)
        updateEyeChip()
        updateCalibChip()
        updateCalibHint()

        songListBox = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            visibility = View.GONE
            setPadding(0, dp(2), 0, dp(4))
        }
        barBox.addView(songListBox)
        rebuildSongList()

        barLp = WindowManager.LayoutParams(
            WindowManager.LayoutParams.WRAP_CONTENT,
            WindowManager.LayoutParams.WRAP_CONTENT,
            overlayType(),
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or
                WindowManager.LayoutParams.FLAG_NOT_TOUCH_MODAL,
            PixelFormat.TRANSLUCENT
        ).apply {
            gravity = Gravity.TOP or Gravity.START
            x = dp(16)
            y = dp(16)
        }
        wm.addView(barBox, barLp)
    }

    private fun barDragTouch(): View.OnTouchListener {
        var startX = 0f; var startY = 0f; var mX = 0; var mY = 0
        return View.OnTouchListener { _, e ->
            when (e.actionMasked) {
                MotionEvent.ACTION_DOWN -> {
                    startX = e.rawX; startY = e.rawY; mX = barLp.x; mY = barLp.y; true
                }
                MotionEvent.ACTION_MOVE -> {
                    barLp.x = mX + (e.rawX - startX).toInt()
                    barLp.y = mY + (e.rawY - startY).toInt()
                    runCatching { wm.updateViewLayout(barBox, barLp) }
                    true
                }
                else -> false
            }
        }
    }

    private fun toggleExpanded() {
        expanded = !expanded
        if (expanded) refreshSongs()          // 展开时重读曲库，导入新歌后立刻可见
        songListBox.visibility = if (expanded) View.VISIBLE else View.GONE
        if (expanded) rebuildSongList()
    }

    private fun rebuildSongList() {
        songListBox.removeAllViews()
        if (songs.isEmpty()) {
            songListBox.addView(listItem("（还没有曲目，先在 App 里导入 MIDI）", false) {})
            return
        }
        songs.forEachIndexed { i, s ->
            songListBox.addView(listItem(if (i == selectedSong) "● ${s.name}" else "○ ${s.name}", i == selectedSong) {
                selectedSong = i
                songLabel.text = s.name
                expanded = false
                songListBox.visibility = View.GONE
                stopPlayback()                 // 换曲目先停掉当前播放
                rebuildSongList()
            })
        }
    }

    private fun listItem(text: String, current: Boolean, onClick: () -> Unit): TextView =
        TextView(this).apply {
            this.text = text
            textSize = 12f
            maxLines = 1
            ellipsize = TextUtils.TruncateAt.END
            setTextColor(AColor.parseColor(if (current) "#E9C46A" else "#A8B0D0"))
            setPadding(dp(12), dp(8), dp(12), dp(8))
            setOnClickListener { onClick() }
        }

    private fun selectedSongName(): String =
        songs.getOrNull(selectedSong)?.name ?: "未选择曲目"

    private fun updateEyeChip() {
        eyeBtn.background = chipBg(active = pointsVisible)
    }

    private fun updateCalibChip() {
        calibChip.background = chipBg(active = calibrate)
    }

    private fun updateCalibHint() {
        calibHint.visibility = if (calibrate) View.VISIBLE else View.GONE
    }

    /** 校准态若长时间无操作自动退出 —— 防止用户忘了退，点位层一直挡在游戏上 */
    private val calibTimeout = Runnable {
        if (calibrate) {
            calibrate = false
            applyPointsVisibility()
            updateCalibChip()
            updateCalibHint()
            toast("校准超时，已自动退出（点「校」可继续）")
        }
    }

    private fun armCalibTimeout() {
        mainHandler.removeCallbacks(calibTimeout)
        if (calibrate) mainHandler.postDelayed(calibTimeout, 45_000L)
    }

    /**
     * 悬浮条上的「校」按钮：进/出校准模式。
     * 校准只在悬浮窗里控制 —— 不再依赖从 App 传进来的那一次 intent，
     * 所以服务被系统重启后也能随时重新进校准，不会再出现"拖不动"。
     */
    private fun toggleCalibrate() {
        calibrate = !calibrate
        if (calibrate && !pointsVisible) pointsVisible = true   // 隐藏状态没法拖，自动显示
        applyPointsVisibility()                                 // 内部同步触摸性
        updatePointsLayout()
        updateEyeChip()
        updateCalibChip()
        updateCalibHint()
        armCalibTimeout()
        toast(
            if (calibrate) "校准模式：拖圆点对准琴键，拖空白处整体移动；再点「校」退出"
            else "已退出校准，点位恢复为不挡操作"
        )
    }

    /** 退出校准（开始演奏前自动调用，避免点位层吃掉游戏触摸） */
    private fun exitCalibrateIfNeeded() {
        if (!calibrate) return
        calibrate = false
        mainHandler.removeCallbacks(calibTimeout)
        applyPointsVisibility()
        updateCalibChip()
        updateCalibHint()
    }

    // ---------------- 播放 ----------------

    private fun setPlayChip(text: String) {
        if (::playChip.isInitialized) playChip.text = text
    }

    private fun toast(msg: String) = Toast.makeText(this, msg, Toast.LENGTH_SHORT).show()

    private fun stopPlayback() {
        engine?.stop()
        engine = null
        loadedSongIndex = -1
        synchronized(tapQueue) { tapQueue.clear() }
        tapGen++            // 让在飞手势的迟到回调失效
        tapBusy = false
        for (i in points.indices) flashPoint(i, false)
        setPlayChip("▶")
    }

    private fun togglePlay() {
        if (!enabled) { toast("连点器开关是关的，先打开"); return }
        val song = songs.getOrNull(selectedSong)
        if (song == null) { toast("先点 ♪ 展开并选一首曲目"); return }
        exitCalibrateIfNeeded()      // 演奏前退出校准，点位层不再拦截触摸

        val e = engine
        if (e == null || loadedSongIndex != selectedSong) { loadAndPlay(song, selectedSong); return }
        when (e.currentState) {
            PlayerState.PLAYING -> e.pause()
            else -> e.play()
        }
    }

    private fun loadAndPlay(song: Song, index: Int) {
        engine?.stop()
        engine = null
        loadedSongIndex = index
        setPlayChip("…")
        toast("正在解析 ${song.name}")

        thread(isDaemon = true, name = "overlay-midi-load") {
            val data = runCatching {
                contentResolver.openInputStream(Uri.parse(song.uri))?.use { MidiParser.parse(it) }
            }.getOrNull()
            mainHandler.post {
                if (data == null) {
                    loadedSongIndex = -1
                    setPlayChip("▶")
                    toast("MIDI 解析失败：${song.name}")
                    return@post
                }
                val e = buildEngine()
                e.load(data)
                engine = e
                if (!AccessibilityClickService.isReady()) toast("无障碍未开启：只会显示点位，不会真的点击")
                e.play()
            }
        }
    }

    private fun buildEngine(): PlayerEngine = PlayerEngine(
        keymap = KeymapAdapter(autoAdapt = true),
        // 单音回调不再用于派发：和弦统一在 onGroup 里一次出手势，
        // 否则一个 4 音和弦会变成 4 次主线程往返 + 4 次串行手势。
        onNoteStart = { _, _ -> },
        onNoteEnd = { idx -> mainHandler.post { flashPoint(idx, false) } },
        onProgress = { _, _, _ -> },
        onFinished = { mainHandler.post { setPlayChip("▶") } },
        onState = { st -> mainHandler.post { setPlayChip(if (st == PlayerState.PLAYING) "⏸" else "▶") } },
        onGroup = { notes, gapMs ->
            mainHandler.post {
                val pts = ArrayList<Pair<Float, Float>>(notes.size)
                val seen = HashSet<Int>(notes.size)
                for ((idx, _) in notes) {
                    flashPoint(idx, true)
                    if (seen.add(idx)) pts.add(pointXY(idx))   // 同键重复只发一条 stroke
                }
                enqueueGroup(pts, groupHoldMs(notes, gapMs))
            }
        },
    )

    /** 点位百分比 → 屏幕绝对像素（与 updatePointsLayout 同一套换算） */
    private fun pointXY(index: Int): Pair<Float, Float> {
        val dm = resources.displayMetrics
        return (calib.x(index) / 100f * dm.widthPixels) to (calib.y(index) / 100f * dm.heightPixels)
    }

    private fun flashPoint(i: Int, on: Boolean) {
        val tv = points.getOrNull(i) ?: return
        tv.background = circleDrawable(active = on)
        tv.setTextColor(AColor.parseColor(if (on) "#2A2005" else "#F4D88C"))
    }

    /**
     * 按住时长：既要贴近音符真实时长，又不能挡住下一组。
     *
     * 为什么必须限制：
     *   dispatchGesture 同一时刻只能有一个手势在飞（发新的会取消旧的），所以一个手势
     *   = 独占一段时间。如果按住 2 秒而下一组 0.1 秒后就到，后面的音全部迟到并无限堆积，
     *   听感就是"这句还没弹完，下一句已经压进来"。
     * 所以按住时长 = min(音符时长, 到下一组的间隔 - 派发开销)，最后一组才允许放长。
     */
    private fun groupHoldMs(notes: List<Pair<Int, Long>>, gapMs: Long): Long {
        val longest = notes.maxOfOrNull { it.second } ?: MIN_TAP_MS
        val budget = if (gapMs <= 0) MAX_HOLD_MS else gapMs - DISPATCH_OVERHEAD_MS
        return minOf(longest, budget).coerceIn(MIN_TAP_MS, MAX_HOLD_MS)
    }

    /** 同刻和弦 → 一个手势（多 stroke 多指同时按）。返回排入的点数。 */
    private fun enqueueGroup(pts: List<Pair<Float, Float>>, holdMs: Long): Int {
        if (pts.isEmpty()) return 0
        synchronized(tapQueue) { tapQueue.addLast(TapGroup(pts, holdMs, SystemClock.uptimeMillis())) }
        drainGroups()
        return pts.size
    }

    private fun drainGroups() {
        if (tapBusy) return
        val svc = AccessibilityClickService.instance
        if (svc == null) {
            synchronized(tapQueue) { tapQueue.clear() }   // 无障碍没开：不留积压
            return
        }
        while (true) {
            val g = synchronized(tapQueue) { tapQueue.removeFirstOrNull() } ?: return
            val lag = SystemClock.uptimeMillis() - g.queuedAtMs
            if (lag > MAX_LAG_MS) {
                // 背压：这一组已经过期到再发也没有意义了，丢掉。
                // 宁可少一个音，也绝不让整首曲子的时间轴越拖越后。
                statDropped++
                continue
            }
            statGroups++
            statStrokeSum += g.pts.size
            statLagSum += lag
            if (lag > statMaxLag) statMaxLag = lag

            val gen = ++tapGen
            tapBusy = true
            // 看门狗：万一手势回调不来（个别 ROM），不能让队列永久卡死
            mainHandler.postDelayed({
                if (tapBusy && tapGen == gen) { tapBusy = false; drainGroups() }
            }, g.holdMs + 1500L)

            val ok = svc.tapMulti(g.pts, g.holdMs) {
                mainHandler.post {
                    if (tapGen == gen) { tapBusy = false; drainGroups() }
                }
            }
            if (!ok) { tapBusy = false; continue }   // 派发被拒也不能卡死

            if (statGroups % 25 == 0) {
                Log.d(
                    TAG,
                    "groups=$statGroups strokes=$statStrokeSum dropped=$statDropped " +
                        "avgLag=${statLagSum / statGroups}ms maxLag=${statMaxLag}ms"
                )
            }
            return
        }
    }

    // ---------------- 样式 ----------------

    private fun circleDrawable(active: Boolean = false) = GradientDrawable().apply {
        shape = GradientDrawable.OVAL
        setColor(AColor.parseColor(if (active) "#F4D88C" else "#2FE9C46A"))
        setStroke(dp(1), AColor.parseColor("#E9C46A"))
    }

    private fun barBg() = GradientDrawable().apply {
        cornerRadius = dp(13).toFloat()
        setColor(AColor.parseColor("#F01A1F35"))
        setStroke(dp(1), AColor.parseColor("#B8860B"))
    }

    private fun chipBg(active: Boolean) = GradientDrawable().apply {
        cornerRadius = dp(8).toFloat()
        setColor(AColor.parseColor(if (active) "#B8860B" else "#2D365C"))
        setStroke(dp(1), AColor.parseColor("#4A5580"))
    }

    private fun iconChip(text: String): TextView = TextView(this).apply {
        this.text = text
        setTextColor(AColor.parseColor("#F4F1E0"))
        textSize = 15f
        gravity = Gravity.CENTER
        background = chipBg(active = false)
        layoutParams = LinearLayout.LayoutParams(dp(30), dp(30)).apply { marginStart = dp(4) }
    }

    // minSdk = 26，直接用 TYPE_APPLICATION_OVERLAY
    private fun overlayType(): Int = WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY

    // ---------------- 生命周期 ----------------

    override fun onDestroy() {
        mainHandler.removeCallbacks(calibTimeout)
        runCatching { engine?.stop() }
        engine = null
        runCatching { wm.removeView(pointsView) }
        runCatching { wm.removeView(barBox) }
        super.onDestroy()
    }

    companion object {
        const val EXTRA_CALIBRATE = "extra_calibrate"

        private const val TAG = "PianoTap"
        /** 单次点击最短按住（与 PC 端 MIN_HOLD 对齐） */
        private const val MIN_TAP_MS = 30L
        /** 单次按住绝对上限（长音再长也不能把手势占成这样，否则会阻塞后续） */
        private const val MAX_HOLD_MS = 1500L
        /** dispatchGesture 一次往返的估算开销，从"到下一组的间隔"里预留出来 */
        private const val DISPATCH_OVERHEAD_MS = 45L
        /** 超过这个延迟就不再补发，直接丢弃 —— 保证时间轴不漂移 */
        private const val MAX_LAG_MS = 150L
    }
}
