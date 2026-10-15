package com.genshin.piano.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.genshin.piano.data.Keymap
import com.genshin.piano.ui.theme.*

/**
 * 21 键网格（3 行 × 7 列）。active 表示当前按下的琴键 —— 用于"点动痕迹"。
 */
@Composable
fun PianoGrid(active: List<Boolean>, modifier: Modifier = Modifier, keyHeight: Int = 42) {
    val clefs = listOf("𝄞", "𝄡", "𝄢")
    Column(modifier) {
        for (r in 0..2) {
            Row(
                Modifier.fillMaxWidth().padding(vertical = 3.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    clefs[r], color = TextMute, fontSize = 13.sp,
                    modifier = Modifier.width(18.dp),
                    textAlign = androidx.compose.ui.text.style.TextAlign.Center,
                )
                for (c in 0..6) {
                    val i = Keymap.index(r, c)
                    val on = active.getOrElse(i) { false }
                    val k = Keymap.keys[i]
                    Box(
                        Modifier
                            .weight(1f)
                            .height(keyHeight.dp)
                            .padding(horizontal = 3.dp)
                            .clip(RoundedCornerShape(10.dp))
                            .background(if (on) Gold else BgInput)
                            .border(1.dp, if (on) GoldHi else BorderC, RoundedCornerShape(10.dp)),
                        contentAlignment = Alignment.Center,
                    ) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Text(
                                k.pcKey,
                                color = if (on) Color(0xFF2A2005) else TextSecondary,
                                fontSize = 12.sp,
                                fontWeight = if (on) FontWeight.Bold else FontWeight.Normal,
                            )
                            Text(
                                k.label,
                                color = if (on) Color(0xFF2A2005) else TextMute,
                                fontSize = 9.sp,
                            )
                        }
                    }
                }
            }
        }
    }
}
