package com.genshin.piano

import android.content.Context
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.runtime.*
import androidx.compose.ui.platform.LocalContext
import com.genshin.piano.perm.OnboardingScreen
import com.genshin.piano.perm.Permissions
import com.genshin.piano.ui.HomeScreen
import com.genshin.piano.ui.theme.GenshinTheme

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            GenshinTheme {
                val context = LocalContext.current
                val prefs = remember { context.getSharedPreferences("app", Context.MODE_PRIVATE) }

                // 进主界面的条件：权限全部到位，或者用户曾经点过「直接进入」
                // （不强制授权 —— 未授权的功能在主界面里会显示状态，随时可回来开）
                var page by remember {
                    mutableStateOf(
                        if (Permissions.allGranted(context) || prefs.getBoolean("onboarded", false))
                            "home" else "onboard"
                    )
                }

                when (page) {
                    "home" -> HomeScreen(onOpenPermissions = { page = "onboard" })
                    else -> OnboardingScreen(onDone = {
                        prefs.edit().putBoolean("onboarded", true).apply()
                        page = "home"
                    })
                }
            }
        }
    }
}
