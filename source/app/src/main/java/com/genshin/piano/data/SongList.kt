package com.genshin.piano.data

import android.content.Context

/** 一首曲目：用户导入的 MIDI 文件。 */
data class Song(
    val uri: String,
    val name: String,
    val durationSec: Double = 0.0,
)

/**
 * 曲库：目前由用户自己导入 MIDI 文件，简单持久化到 SharedPreferences。
 * （解析时长/音符数需要 MIDI 解析器，后续接入 core/ 或 Kotlin 端再补。）
 */
class SongList(context: Context) {

    private val sp = context.getSharedPreferences("songs", Context.MODE_PRIVATE)

    /** 读取曲库：每行 "uri\u0001name\u0001duration" */
    fun load(): MutableList<Song> {
        val raw = sp.getString("list", "") ?: ""
        if (raw.isBlank()) return mutableListOf()
        return raw.split("\n").mapNotNull { line ->
            val p = line.split("\u0001")
            if (p.size >= 2) Song(p[0], p[1], p.getOrNull(2)?.toDoubleOrNull() ?: 0.0) else null
        }.toMutableList()
    }

    fun save(songs: List<Song>) {
        val raw = songs.joinToString("\n") { "${it.uri}\u0001${it.name}\u0001${it.durationSec}" }
        sp.edit().putString("list", raw).apply()
    }
}
