package com.genshin.piano.data

import android.content.Context

/**
 * 21 个连点点的屏幕坐标，用**百分比**(0..100) 存储，跨分辨率复用。
 * 运行时由覆盖层按实际屏幕尺寸换算成像素。
 */
class CalibrationStore(context: Context) {

    private val sp = context.getSharedPreferences("calibration", Context.MODE_PRIVATE)

    private val xs = FloatArray(21) { i -> 16f + Keymap.keys[i].col * 10f }
    private val ys = FloatArray(21) { i -> 40f + Keymap.keys[i].row * 13f }

    init { load() }

    fun x(i: Int): Float = xs[i]
    fun y(i: Int): Float = ys[i]

    fun set(i: Int, xPct: Float, yPct: Float) {
        xs[i] = xPct.coerceIn(1f, 99f)
        ys[i] = yPct.coerceIn(1f, 99f)
    }

    fun reset() {
        for (i in 0 until 21) {
            xs[i] = 16f + Keymap.keys[i].col * 10f
            ys[i] = 40f + Keymap.keys[i].row * 13f
        }
        save()
    }

    fun save() {
        sp.edit().apply {
            for (i in 0 until 21) {
                putFloat("x$i", xs[i])
                putFloat("y$i", ys[i])
            }
        }.apply()
    }

    fun load() {
        for (i in 0 until 21) {
            if (sp.contains("x$i")) {
                xs[i] = sp.getFloat("x$i", xs[i])
                ys[i] = sp.getFloat("y$i", ys[i])
            }
        }
    }
}
