package com.genshin.piano.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

// 原神暗金调色板（与 Windows 端 utils/style.py 保持一致，双端同款观感）
val BgDark = Color(0xFF1A1F35)
val BgPanel = Color(0xFF232A47)
val BgCard = Color(0xFF252C4B)
val BgInput = Color(0xFF2D365C)
val BorderC = Color(0xFF4A5580)
val TextPrimary = Color(0xFFF4F1E0)
val TextSecondary = Color(0xFFA8B0D0)
val TextMute = Color(0xFF6E789C)
val Gold = Color(0xFFE9C46A)
val GoldHi = Color(0xFFF4D88C)
val Amber = Color(0xFFB8860B)
val Success = Color(0xFF7CB342)
val Danger = Color(0xFFE06C75)

private val GenshinColors = darkColorScheme(
    primary = Gold,
    onPrimary = Color(0xFF2A2005),
    secondary = Amber,
    onSecondary = TextPrimary,
    background = BgDark,
    onBackground = TextPrimary,
    surface = BgCard,
    onSurface = TextPrimary,
    surfaceVariant = BgInput,
    onSurfaceVariant = TextSecondary,
    outline = BorderC,
    error = Danger,
    onError = Color(0xFF2A0505),
)

@Composable
fun GenshinTheme(content: @Composable () -> Unit) {
    MaterialTheme(colorScheme = GenshinColors, content = content)
}
