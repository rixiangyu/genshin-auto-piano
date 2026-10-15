package com.genshin.piano.data

/**
 * 把任意 MIDI 音符适配到 21 键之一，对齐 Windows 端 core/keymap_manager.py 的
 * resolve_key 四级算法：exact（直接映射）→ shift（八度移位）→ near（黑键就近白键）→ 无法适配。
 */
class KeymapAdapter(var autoAdapt: Boolean = true) {

    private val midiToIndex: Map<Int, Int> =
        Keymap.keys.withIndex().associate { (i, k) -> k.midi to i }

    private val lo = Keymap.keys.minOf { it.midi }
    private val hi = Keymap.keys.maxOf { it.midi }

    private val blackPcs = intArrayOf(1, 3, 6, 8, 10)

    data class Resolved(val index: Int, val mode: String)

    /** 返回适配结果；无法适配返回 null。 */
    fun resolve(note: Int): Resolved? {
        midiToIndex[note]?.let { return Resolved(it, "exact") }
        if (!autoAdapt) return null

        var n = note
        if (hi - lo >= 12) {
            while (n < lo) n += 12
            while (n > hi) n -= 12
        }
        if (n in lo..hi) {
            if (n != note) midiToIndex[n]?.let { return Resolved(it, "shift") }
            if ((n % 12) in blackPcs) {
                for (cand in intArrayOf(n - 1, n + 1)) {
                    midiToIndex[cand]?.let { return Resolved(it, "near") }
                }
            }
        }
        return null
    }

    /** 简谱名（用于界面显示/进度），如 60 -> 中音1 */
    fun jianpu(note: Int): String = Jianpu.fromMidi(note)
}

/** 简谱换算（对齐 midi_to_jianpu）。 */
object Jianpu {
    private val SHARP_STEPS = arrayOf(
        "1", "#1", "2", "#2", "3", "4", "#4", "5", "#5", "6", "#6", "7"
    )

    fun fromMidi(note: Int): String {
        val oct = note / 12 - 5
        val step = SHARP_STEPS[((note % 12) + 12) % 12]
        val name = when {
            oct == 0 -> "中音"
            oct > 0 -> "倍".repeat(oct - 1) + "高音"
            else -> "倍".repeat(-oct - 1) + "低音"
        }
        return name + step
    }
}
