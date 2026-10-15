package com.genshin.piano.data

/**
 * 21 键定义，与 PC 端 keymap_manager.py 的 DEFAULT_GENSHIN_KEYMAP 一一对应。
 *
 * 行(0=高音/1=中音/2=低音) × 列(0..6 → do..ti)；
 * 21 键 = 3 个八度 × 7 个白键（C 大调），不含黑键（黑键由适配算法就近处理）。
 */
data class PianoKey(
    val row: Int,
    val col: Int,
    val label: String,   // 简谱 do..ti
    val pcKey: String,   // 对应电脑端按键
    val midi: Int,       // MIDI 音高
)

object Keymap {
    private val NAMES = listOf("do", "re", "mi", "fa", "so", "la", "ti")
    private val KEYS = listOf(
        listOf("Q", "W", "E", "R", "T", "Y", "U"),  // 高音
        listOf("A", "S", "D", "F", "G", "H", "J"),  // 中音
        listOf("Z", "X", "C", "V", "B", "N", "M"),  // 低音
    )
    // 每行的起始白键：高 C5=72 / 中 C4=60 / 低 C3=48
    private val ROW_BASE = listOf(72, 60, 48)
    // C 大调白键半音偏移
    private val STEP = listOf(0, 2, 4, 5, 7, 9, 11)

    val keys: List<PianoKey> = buildList {
        for (r in 0..2) for (c in 0..6) {
            add(PianoKey(r, c, NAMES[c], KEYS[r][c], ROW_BASE[r] + STEP[c]))
        }
    }

    val rowNames = listOf("高音", "中音", "低音")

    fun index(row: Int, col: Int): Int = row * 7 + col
}
