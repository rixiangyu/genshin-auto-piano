# 原神自动弹琴 · 安卓版

PC 版（Python + PySide6，模拟键盘按键）的安卓移植：**读取 MIDI 文件 → 在手机屏幕上自动点击原神的 21 个琴键**。

安卓端靠**无障碍服务模拟屏幕触摸**，**不需要 root、不修改游戏、不需要越狱**。

---

## 一、这个目录里有什么

| 文件 / 目录 | 说明 |
|---|---|
| `GenshinAutoPiano-debug-v1.0.apk` | **可直接安装的这一版 App**（debug 签名，15.1 MB） |
| `source/` | **完整安卓工程源码**（Kotlin + Jetpack Compose），以后改代码就在这里 |
| `README.md` | 本文件：总览 + 上手 + 排错 |
| `01-开发全过程纪要.md` | 从 PC 版到安卓版的完整过程：需求演进、技术选型、**每一个 bug 的根因与修复**、真机验证数据 |
| `02-项目结构与修改指南.md` | 代码结构、每个文件职责、**「想改 X 该动哪里」索引**、常量速查、命令速查 |

> 文档是给「以后要小改动」的自己看的：先看 `02` 找位置，改动后照 `02` 末尾的命令构建即可。
> 新家路径已经是**纯英文**，不再需要 AGP 的中文路径绕过开关，构建比原来更干净。

---

## 二、30 秒上手

1. 手机安装 `GenshinAutoPiano-debug-v1.0.apk`
2. 首次打开会列出 **4 项权限**，逐个点「去开启」：

   | 权限 | 作用 | 不开的后果 |
   |---|---|---|
   | 所有文件访问 | 读取你导入的 MIDI | 无法导入曲目 |
   | 悬浮窗 | 显示控制条和 21 个连点点 | 连点器无法显示 |
   | **无障碍服务** | **模拟手指点击屏幕** | **完全弹不了（核心权限）** |
   | 通知 | 前台服务保活 | 只影响后台存活 |

   4 项全绿后底部「进入应用」按钮才会亮。

3. 主界面点「导入 MIDI」→ 选你自己的 `.mid` 文件（可多选，会存进曲库）
4. **打开原神 → 进入弹琴界面**（能看到 21 个琴键）
5. 切回本 App → 点「显示连点器」→ 悬浮条出现在屏幕上
6. 点悬浮条上的「**校**」→ 把 21 个圆点拖到琴键上 → 再点「校」退出校准
7. 点悬浮条上的 **▶** → 开始自动弹奏

> ⚠️ **顺序很重要**：一定要**先**进原神弹琴界面、**再**校准。不校准就用，21 个点会落在屏幕中央，点到别的地方去。

---

## 三、悬浮窗（控制条）说明

折叠态只有一条小横条，展开态才有歌单。**整条都可以拖**（拖左侧的柄）。

| 控件 | 位置 | 作用 |
|---|---|---|
| `⠿` 柄 | 最左 | 按住拖动整个悬浮条 |
| 开关 | 第二 | 连点器总开关 |
| 歌名 | 中间 | 显示当前选中曲目 |
| `▶` / `⏸` | 右侧 | **开始 / 暂停**（游戏内真实点击） |
| `♪` | 右侧 | 展开 / 收起歌单（收起后手机就不显示歌单） |
| `👁` | 右侧 | 显示 / 隐藏 21 个连点点（不弹琴时隐藏，防误触） |
| `校` | 右侧 | **进入 / 退出校准模式**（拖动 21 个点） |

**校准模式下的操作**

- 拖**某一个圆点** = 单独微调这个点
- 拖**空白处** = 整组 21 个点一起平移（快速对位用）
- 45 秒无操作会**自动退出**校准；点 `▶` 播放前也会自动退出 —— 防止点位层一直挡在游戏上
- 点 `校` 时若有隐藏中的点，会自动把点显示出来（隐藏状态是拖不到的）

**安全设计**：非校准态下，点位层带 `FLAG_NOT_TOUCHABLE`，**完全不拦截屏幕触摸** —— 不弹琴时不会误触，游戏操作不受任何影响。

---

## 四、21 键映射表

原神琴界面 3 行 × 7 列 = 21 个白键（C 大调，跨 3 个八度），与 PC 版**完全一致**：

```
行0 高音  midi 72~83   Q W E R T Y U
行1 中音  midi 60~71   A S D F G H J
行2 低音  midi 48~59   Z X C V B N M
```

MIDI 里超出这个范围或落在黑键上的音，会按 4 级策略自动适配：

1. **精确**命中 → 直接用
2. **差八度** → 移到相邻八度
3. **黑键** → 就近落到旁边白键
4. 都不行 → 丢弃

> 实测你那份 `星茶会.mid`：**2305 / 2305 音符 100% 适配成功**。

---

## 五、常见问题

### Q1：点了「去开启」但无障碍还是显示未开启
**这是 MIUI（小米）的额外限制**：通过 adb 或第三方途径设进去的无障碍服务，会被 MIUI 的安全中心撤销。请**在手机上手动开**：App 内点「去开启」→ 在系统列表里找到「原神自动弹琴 · 点击」→ 打开 → 按 MIUI 弹窗确认（可能要勾「仍然允许」）。

### Q2：21 个点拖不动
先确认两点：
1. 点过「**校**」按钮了吗？只有**校准模式 + 点位可见**时才会接收触摸。
2. 点是不是被隐藏了？(`👁` 状态) —— 隐藏时不可拖动是**故意设计**的。

### Q3：弹出来的和电脑不一样 / 一秒钟弹好几个
2026-10-15 那版已修（真和弦 + 背压 + 长音放开）。如果新版还有问题，看 `01-开发全过程纪要.md` 的「Bug 8」，并注意：**原神手机版是否支持多指同时按**需要真机确认，若游戏只认 1~2 指，3~4 音和弦会丢音 —— 那是游戏侧限制，需要改策略（见 `02` 的改动索引）。

### Q4：曲目时长显示不对
已修复（`Int32` 溢出导致 3 分钟变 4.5 秒）。若再遇到，优先怀疑**时间换算的整数类型**，详见纪要 Bug 4。

### Q5：屏幕最下面一排琴键点不到
点位坐标按**应用可用高度**换算，最下方约 230px 是系统栏死区，放不了点。**音准没问题**（绘制和注入共用同一套换算），只是那条带子放不下点。如果原神琴界面太靠下，可以调游戏里的画面设置或使用全面屏手势隐藏导航栏。

---

## 六、从源码构建

### 环境（本机）

| 项 | 位置 |
|---|---|
| JDK | `D:\工具\java\jdk-21.0.12.1+1` |
| Android SDK | `D:\Android\Sdk`（platform-tools / platforms;android-34 / build-tools;34.0.0） |
| Android Studio（可选） | `D:\工具\Android Studio\bin\studio64.exe` |

`source/local.properties` 里的 `sdk.dir` 已指向 `D:\Android\Sdk`，换机器需要改这一行。

### 命令行构建（本机一直在用这条）

```powershell
$sdk="D:\Android\Sdk"
$env:ANDROID_HOME=$sdk; $env:ANDROID_SDK_ROOT=$sdk
$env:JAVA_HOME="D:\工具\java\jdk-21.0.12.1+1"
Set-Location "D:\my project\Genshin Impact auto-play piano Android version\source"
java -Xmx2g -classpath "gradle\wrapper\gradle-wrapper.jar" org.gradle.wrapper.GradleWrapperMain --no-daemon assembleDebug
```

产物：`source\app\build\outputs\apk\debug\app-debug.apk`

### 编译 + 装到手机 + 重授权限（一条龙）

```powershell
$adb="D:\Android\Sdk\platform-tools\adb.exe"
$pkg="com.genshin.piano"
& $adb install -r "source\app\build\outputs\apk\debug\app-debug.apk"
& $adb shell appops set $pkg MANAGE_EXTERNAL_STORAGE allow
& $adb shell appops set $pkg SYSTEM_ALERT_WINDOW allow
& $adb shell pm grant $pkg android.permission.POST_NOTIFICATIONS
# 注意顺序：accessibility_enabled 必须写在服务列表之前，否则会被系统清掉
& $adb shell settings put secure accessibility_enabled 1
& $adb shell settings put secure enabled_accessibility_services "$pkg/$pkg.access.AccessibilityClickService"
```

> `adb install -r` **会重置权限**（appops 和无障碍都要重设），所以每次装完都跑一遍上面这几行。

### 版本信息

| 项 | 值 |
|---|---|
| 包名 | `com.genshin.piano` |
| 版本 | versionCode 1 / versionName 1.0 |
| minSdk / targetSdk / compileSdk | 26 / 34 / 34 |
| AGP / Kotlin / Gradle | 8.5.2 / 1.9.24 / 8.7 |
| Compose BOM | 2024.06.00（compiler ext 1.5.14） |
| UI | Jetpack Compose + Material 3 |

---

## 七、目前已知的限制 / 以后可以做的

| # | 项目 | 状态 |
|---|---|---|
| 1 | **App 内置播放器没有声音** | 只有 21 键视觉点动。要出声可用 `AudioTrack` 合成（音色比真钢琴单薄，因为没有音源库） |
| 2 | **和弦多指精度** | 已用「一个手势多条 stroke」实现同时按下，但**原神手机版是否响应多指**需真机确认 |
| 3 | 屏幕底部约 230px 死区 | 点位放不进去（见 Q5） |
| 4 | Windows 版界面美化 | 原型已做（`ui-prototype.html`），**尚未改 PC 版代码** |

详见 `01-开发全过程纪要.md` 末尾的「待办」。

---

## 八、Git 与交接

本目录已初始化为 Git 仓库（`main` 分支）。

### 常用操作

```bash
cd "D:\my project\Genshin Impact auto-play piano Android version"
git status                # 看改了什么
git add -A                # 暂存全部改动
git commit -m "改了什么"   # 提交
git log --oneline         # 看历史
git diff                  # 看未暂存的改动
```

### 提交前要知道的

- **构建产物不会进仓库**：`.gitignore` 已忽略 `build/`、`.gradle/`、`*.log`
- **`source/local.properties` 不在仓库里** —— 它指向本机的 `D:\Android\Sdk`，换机器要自己建一个
- **根目录的 `GenshinAutoPiano-debug-v1.0.apk` 会提交** —— 它是"这一版"的交付物，需要能随时 `git checkout` 找回（即使以后代码改坏了，这一版永远在历史里）

### 换新模型 / 换人来接手

把这句话丢给它就行：

> 先读 `README.md`（总览 + 上手 + FAQ）→ 再读 `02-项目结构与修改指南.md`（**找改动位置**，里面有「想改 X → 动哪里」速查表和「绝对不要改」清单）→ 查 `01-开发全过程纪要.md`（**每个 bug 的根因**）。改完照 02 的构建命令编译装机验证。

> ⚠️ 唯一需要提醒新模型的：**别改 `MidiParser.kt` 里的时间运算类型**（`Int` 会静默溢出，3 分钟的歌变 4.5 秒，见纪要 Bug 4）。
