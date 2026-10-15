package com.genshin.piano.access

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.GestureDescription
import android.content.Intent
import android.graphics.Path
import android.view.accessibility.AccessibilityEvent

/**
 * 无障碍服务：用 dispatchGesture 在屏幕坐标模拟"按下→保持→抬起"。
 * 保持时长 = 音符时长，用于还原长音。
 */
class AccessibilityClickService : AccessibilityService() {

    override fun onServiceConnected() {
        super.onServiceConnected()
        instance = this
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        // 无需监听界面事件
    }

    override fun onInterrupt() {}

    override fun onUnbind(intent: Intent?): Boolean {
        if (instance === this) instance = null
        return super.onUnbind(intent)
    }

    /**
     * 在屏幕像素坐标 (x, y) 点击。
     * @param pressMillis 按住时长（毫秒），长音需更长
     * @return 是否成功派发手势
     */
    fun tap(x: Float, y: Float, pressMillis: Long = 60L, onDone: (() -> Unit)? = null): Boolean =
        tapMulti(listOf(x to y), pressMillis, onDone)

    /**
     * **同时**按住多个点 —— 真·多指和弦。
     *
     * 关键：一个 GestureDescription 里可以放多条 StrokeDescription，每条 stroke 就是一个独立
     * 手指。所有 stroke 的起始偏移都为 0，于是它们**同时按下**；各自的 duration 决定各自何时抬起。
     * 这样同刻的和弦只需要**一次** dispatchGesture，而不是每个音排一次（原来会退化成琶音，
     * 而且 4 音和弦要占掉 4 次手势的时间，直接把时间轴拖崩）。
     *
     * dispatchGesture 同一时刻只允许一个手势在飞，所以调用方仍需串行 —— 但串行的单位从
     * "每个音"变成了"每一组（和弦）"，开销直接降到 1/N。
     *
     * @param points 屏幕坐标列表；超过 [GestureDescription.getMaxStrokeCount]（一般 10）的忽略
     * @param pressMillis 每条 stroke 的按住时长
     */
    fun tapMulti(
        points: List<Pair<Float, Float>>,
        pressMillis: Long,
        onDone: (() -> Unit)? = null,
    ): Boolean {
        if (points.isEmpty()) return false
        val limit = GestureDescription.getMaxStrokeCount()
        val builder = GestureDescription.Builder()
        var n = 0
        for ((x, y) in points) {
            if (n >= limit) break
            val path = Path().apply { moveTo(x, y) }
            builder.addStroke(
                GestureDescription.StrokeDescription(path, 0L, pressMillis.coerceAtLeast(1L))
            )
            n++
        }
        if (n == 0) return false
        return dispatchGesture(builder.build(), callback(onDone), null)
    }

    private fun callback(onDone: (() -> Unit)?) = object : AccessibilityService.GestureResultCallback() {
        override fun onCompleted(description: GestureDescription?) { onDone?.invoke() }
        override fun onCancelled(description: GestureDescription?) { onDone?.invoke() }
    }

    companion object {
        @Volatile
        var instance: AccessibilityClickService? = null
            private set

        fun isReady(): Boolean = instance != null
    }
}
