package com.genshin.piano.play

import com.genshin.piano.data.Jianpu
import com.genshin.piano.data.Keymap
import com.genshin.piano.data.KeymapAdapter
import com.genshin.piano.midi.MidiData
import java.util.PriorityQueue
import kotlin.concurrent.thread

enum class PlayerState { STOPPED, PLAYING, PAUSED }

/**
 * 播放引擎（对齐 Windows 端 core/player.py）：
 * - 按音符开始时间分组（同刻 = 和弦）
 * - 最小堆管理"释放"事件，支持长按持续音
 * - 暂停时冻结时间轴
 * 输出为 21 键序号（index）的按下/抬起回调，由 UI 或无障碍注入层消费。
 */
class PlayerEngine(
    private val keymap: KeymapAdapter,
    private val onNoteStart: (index: Int, durationMs: Long) -> Unit,
    private val onNoteEnd: (index: Int) -> Unit,
    private val onProgress: (curSec: Double, totalSec: Double, notes: List<String>) -> Unit,
    private val onFinished: () -> Unit,
    private val onState: (PlayerState) -> Unit = {},
    /**
     * 同一时刻的一组音符（和弦）**一次性**回调，用于注入层。
     *
     * @param notes [(键索引, 该音真实时长ms)]
     * @param gapMs 到下一组的时间间隔（墙钟 ms）；最后一组为 -1
     *
     * 注入层（无障碍点击）需要"每组一次"而不是"每个音一次"：一个手势的多条 stroke 就能
     * 同时按下一整个和弦。gapMs 用来限制按住时长，保证手势在下一组到来前结束，不阻塞队列。
     */
    private val onGroup: ((notes: List<Pair<Int, Long>>, gapMs: Long) -> Unit)? = null,
) {
    @Volatile
    var speed: Float = 1f
        set(value) { field = value.coerceIn(0.1f, 5f) }

    @Volatile
    private var state = PlayerState.STOPPED

    private var thread: Thread? = null

    @Volatile private var stopFlag = false
    @Volatile private var paused = false
    private val pauseLock = Object()

    private var groups: List<Pair<Double, List<Pair<Int, Double>>>> = emptyList()
    private var totalSec = 0.0

    private data class Release(val time: Double, val seq: Int, val index: Int)
    private val heap = PriorityQueue<Release>(compareBy<Release>({ it.time }, { it.seq }))
    private val held = HashMap<Int, Pair<Double, Int>>()
    private var seq = 0

    val currentState: PlayerState get() = state

    /** 已装载的可演奏音符数（适配不到 21 键的音符不计入） */
    val playableCount: Int get() = groups.sumOf { it.second.size }

    val isLoaded: Boolean get() = groups.isNotEmpty()

    fun load(data: MidiData) {
        stop()
        totalSec = data.totalDuration
        val map = HashMap<Long, MutableList<Pair<Int, Double>>>()
        for (e in data.events) {
            val r = keymap.resolve(e.note) ?: continue
            val key = Math.round(e.startSec * 100000.0)
            map.getOrPut(key) { mutableListOf() }.add(r.index to e.durationSec)
        }
        groups = map.entries.sortedBy { it.key }
            .map { (it.key / 100000.0) to it.value }
    }

    fun play() {
        if (state == PlayerState.PLAYING) return
        if (state == PlayerState.PAUSED) {
            paused = false
            synchronized(pauseLock) { pauseLock.notifyAll() }
            setState(PlayerState.PLAYING)
            return
        }
        if (groups.isEmpty()) return
        stopFlag = false
        paused = false
        setState(PlayerState.PLAYING)
        thread = thread(start = true, isDaemon = true, name = "piano-player") { loop() }
    }

    fun pause() {
        if (state == PlayerState.PLAYING) {
            paused = true
            setState(PlayerState.PAUSED)
        }
    }

    fun togglePause() {
        // STOPPED 状态下必须能"开始播放"，否则第一次点播放按钮毫无反应
        when (state) {
            PlayerState.PLAYING -> pause()
            PlayerState.PAUSED -> play()
            PlayerState.STOPPED -> play()
        }
    }

    fun stop() {
        stopFlag = true
        paused = false
        synchronized(pauseLock) { pauseLock.notifyAll() }
        thread?.join(1000)
        thread = null
        releaseAll()
        setState(PlayerState.STOPPED)
    }

    // ---------------- 内部 ----------------

    private fun setState(s: PlayerState) {
        state = s
        onState(s)
    }

    private fun scheduleRelease(index: Int, time: Double) {
        heap.add(Release(time, seq, index))
        held[index] = time to seq
        seq++
    }

    private fun popDue(start: Double, t0: Double) {
        val now = System.nanoTime() / 1e9
        while (heap.isNotEmpty()) {
            val r = heap.peek()
            val abs = start + (r.time - t0) / speed
            if (abs > now) break
            heap.poll()
            if (held[r.index] == (r.time to r.seq)) {
                held.remove(r.index)
                onNoteEnd(r.index)
            }
        }
    }

    private fun nextReleaseAbs(start: Double, t0: Double): Double? =
        heap.peek()?.let { start + (it.time - t0) / speed }

    private fun releaseAll() {
        if (held.isNotEmpty()) {
            val keys = held.keys.toList()
            held.clear()
            keys.forEach { onNoteEnd(it) }
        }
        heap.clear()
    }

    private fun sleepUntil(deadline: Double) {
        val s = deadline - System.nanoTime() / 1e9
        if (s > 0) {
            val ms = (minOf(s, 0.002) * 1000).toLong().coerceAtLeast(1)
            Thread.sleep(ms)
        }
    }

    private fun loop() {
        if (groups.isEmpty()) return
        releaseAll()
        var start = System.nanoTime() / 1e9
        val t0 = groups.first().first

        for (gi in groups.indices) {
            val (time, notes) = groups[gi]
            if (stopFlag) break
            var target = start + (time - t0) / speed
            while (true) {
                if (stopFlag) break
                popDue(start, t0)
                if (System.nanoTime() / 1e9 >= target) break
                val nextRel = nextReleaseAbs(start, t0)
                var deadline = if (nextRel == null) target else minOf(target, nextRel)
                if (paused) {
                    val ps = System.nanoTime() / 1e9
                    synchronized(pauseLock) {
                        while (paused && !stopFlag) pauseLock.wait()
                    }
                    val pd = System.nanoTime() / 1e9 - ps
                    start += pd; target += pd; deadline += pd
                }
                sleepUntil(deadline)
            }
            if (stopFlag) break
            popDue(start, t0)

            val plan = ArrayList<Pair<Int, Double>>()
            for ((idx, dur) in notes) {
                if (held.containsKey(idx)) releaseKey(idx)
                plan.add(idx to dur)
            }
            for ((idx, dur) in plan) {
                val holdMid = maxOf(MIN_HOLD * speed, dur - RELEASE_GAP * speed)
                scheduleRelease(idx, time + holdMid)
                onNoteStart(idx, (holdMid * 1000).toLong())
            }
            onProgress(time, totalSec, notes.map { Jianpu.fromMidi(Keymap.keys[it.first].midi) })

            // 整组（和弦）一次性交给注入层；gapMs 为墙钟时间下到下一组的间隔
            onGroup?.let { cb ->
                val gapMs = if (gi + 1 < groups.size) {
                    (((groups[gi + 1].first - time) / speed) * 1000).toLong()
                } else -1L
                cb(plan.map { it.first to (it.second * 1000).toLong() }, gapMs)
            }
        }

        // 等待尾音全部释放（暂停时同样冻结时间轴）
        while (heap.isNotEmpty() && !stopFlag) {
            var next = nextReleaseAbs(start, t0) ?: break
            while (System.nanoTime() / 1e9 < next) {
                if (stopFlag) break
                if (paused) {
                    val ps = System.nanoTime() / 1e9
                    synchronized(pauseLock) { while (paused && !stopFlag) pauseLock.wait() }
                    val pd = System.nanoTime() / 1e9 - ps
                    start += pd
                    next += pd
                }
                Thread.sleep(2)
            }
            popDue(start, t0)
        }

        releaseAll()
        if (!stopFlag) onFinished()
        setState(PlayerState.STOPPED)
    }

    companion object {
        const val MIN_HOLD = 0.03
        const val RELEASE_GAP = 0.03
    }

    private fun releaseKey(index: Int) {
        held.remove(index)
        onNoteEnd(index)
    }
}
