package com.genshin.piano.midi

import java.io.File
import java.io.InputStream

/** 一个可播放音符（时间已换算为秒）。 */
data class NoteEvent(
    val note: Int,          // MIDI 音符号 0..127
    val velocity: Int,
    val startSec: Double,
    val durationSec: Double,
)

/** 解析结果。 */
data class MidiData(
    val events: List<NoteEvent>,
    val trackCount: Int,
    val ticksPerBeat: Int,
    val totalDuration: Double,
    val hasChords: Boolean,
)

/**
 * 标准 MIDI 文件（SMF）解析器 —— 对齐 Windows 端 core/midi_parser.py 的行为：
 * 多轨合并、tempo map 精确换算、note_on/off 配对还原时长、和弦检测。
 */
object MidiParser {

    fun parseFile(path: String): MidiData = File(path).inputStream().use { parse(it) }

    fun parse(input: InputStream): MidiData {
        val d = input.readBytes()
        var pos = 0
        fun u8(): Int = d[pos++].toInt() and 0xFF
        fun u16(): Int = (u8() shl 8) or u8()
        fun u32(): Int { var v = 0; repeat(4) { v = (v shl 8) or u8() }; return v }
        fun skip(n: Int) { pos += n }
        fun ascii(n: Int): String { val s = String(d, pos, n, Charsets.US_ASCII); pos += n; return s }
        fun varint(): Int {
            var v = 0
            while (true) { val b = u8(); v = (v shl 7) or (b and 0x7F); if (b and 0x80 == 0) break }
            return v
        }

        require(d.size >= 14 && ascii(4) == "MThd") { "不是有效的 MIDI 文件" }
        val headerLen = u32()
        u16()                      // format
        val ntrks = u16()
        val division = u16()
        if (headerLen > 6) skip(headerLen - 6)

        val ticksPerBeat =
            if (division and 0x8000 != 0) 480 else (division and 0x7FFF).coerceAtLeast(1)

        val tempos = ArrayList<Pair<Int, Int>>()          // tick -> 微秒/拍
        val notes = ArrayList<IntArray>()                 // [tick, note, isOn(1/0), velocity]
        var trackCount = 0
        var trackWithNotes = 0

        while (pos + 8 <= d.size && trackCount < ntrks) {
            val id = ascii(4)
            val len = u32()
            val end = (pos + len).coerceAtMost(d.size)
            if (id != "MTrk") { pos = end; trackCount++; continue }

            var absTick = 0
            var running = -1
            var hasNotes = false

            while (pos < end) {
                absTick += varint()
                val b = d[pos].toInt() and 0xFF
                val status: Int
                if (b and 0x80 != 0) {
                    status = b
                    pos++
                    // 按 SMF 规范：只有通道消息(0x80..0xEF)才可作为 running status，
                    // 系统消息(0xF0/0xF7/0xFF)会使其作废。
                    running = if (status in 0x80..0xEF) status else -1
                } else {
                    status = running
                }
                if (status < 0) break

                when {
                    status and 0xF0 == 0x90 || status and 0xF0 == 0x80 -> {
                        val note = u8(); val vel = u8()
                        val on = (status and 0xF0 == 0x90) && vel > 0
                        notes.add(intArrayOf(absTick, note, if (on) 1 else 0, vel))
                        if (on) hasNotes = true
                    }
                    status and 0xF0 == 0xA0 || status and 0xF0 == 0xB0 ||
                        status and 0xF0 == 0xE0 -> { u8(); u8() }
                    status and 0xF0 == 0xC0 || status and 0xF0 == 0xD0 -> { u8() }
                    status == 0xFF -> {
                        val type = u8()
                        val mlen = varint()
                        if (type == 0x51 && mlen == 3) {
                            val tempo = (u8() shl 16) or (u8() shl 8) or u8()
                            tempos.add(absTick to tempo)
                        } else skip(mlen)
                    }
                    status == 0xF0 || status == 0xF7 -> { skip(varint()) }
                    else -> { /* 未知，尝试跳过 1 字节避免死循环 */ if (pos < end) pos++ }
                }
            }
            pos = end
            trackCount++
            if (hasNotes) trackWithNotes++
        }

        // 排序 tempo，构建 tick -> 秒 映射
        // ⚠️ 必须用 Double 运算：tick * tempo 轻松超过 Int 上限（如 187645 × 500000），
        // 用 Int 会静默溢出成负数，把整条时间轴压掉（3 分钟的歌会变成几秒）。
        tempos.sortBy { it.first }
        fun tickToSec(tick: Int): Double {
            var t = 0.0
            var cur = 500000
            var last = 0
            for ((tk, upq) in tempos) {
                if (tk > tick) break
                t += (tk - last).toDouble() * cur / ticksPerBeat / 1_000_000.0
                cur = upq
                last = tk
            }
            t += (tick - last).toDouble() * cur / ticksPerBeat / 1_000_000.0
            return t
        }

        // 合并所有轨的 note 事件，按 tick 排序后配对
        notes.sortBy { it[0] }
        val active = HashMap<Int, Pair<Int, Int>>()   // note -> (startTick, velocity)
        val out = ArrayList<NoteEvent>()
        for (e in notes) {
            val tick = e[0]; val note = e[1]; val on = e[2] == 1; val vel = e[3]
            if (on) {
                active[note] = tick to vel
            } else {
                val a = active.remove(note)
                if (a != null) {
                    val start = tickToSec(a.first)
                    val endT = tickToSec(tick)
                    out.add(NoteEvent(note, a.second, start, (endT - start).coerceAtLeast(0.0)))
                }
            }
        }
        out.sortBy { it.startSec }

        val total = out.maxOfOrNull { it.startSec + it.durationSec } ?: 0.0

        // 和弦检测：同一时刻多个音符
        val hasChords = out.groupBy { Math.round(it.startSec * 10000) }.any { it.value.size > 1 }

        return MidiData(
            events = out,
            trackCount = trackCount,
            ticksPerBeat = ticksPerBeat,
            totalDuration = total,
            hasChords = hasChords,
        )
    }
}
