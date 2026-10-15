package com.genshin.piano

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
                // App 启动时检查权限，缺则进引导页
                var ready by remember { mutableStateOf(Permissions.allGranted(context)) }
                if (ready) {
                    HomeScreen()
                } else {
                    OnboardingScreen(onDone = { ready = true })
                }
            }
        }
    }
}
