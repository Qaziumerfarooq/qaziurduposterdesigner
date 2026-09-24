[app]

# (str) Title of your application
title = Qazi Urdu Poster Designer

# (str) Package name
package.name = qaziurduposter

# (str) Package domain (needs at least one dot)
package.domain = org.qazi

# (str) Source code where the main.py lives
source.dir = .

# (list) Source files to include (all extensions under source.dir)
source.include_exts = py,png,jpg,jpeg,kv,atlas,ttf,otf,icns

# (str) Application versioning
version = 1.0.0

# (list) Application requirements (pip / recipe names)
requirements = python3,kivy,hostpython3,pygments,docutils,arabic_reshaper,python-bidi,pillow,reportlab,fonttools,plyer

# (str) Custom source folders for requirements (comma separated)
# None

# (str) Presplash / icon used by desktop tools
icon.filename = icon.png

# (str) Presplash animation source (android)
presplash.filename = icon.png

# (str) Orientation (one of: portrait, landscape, sensor, user)
orientation = portrait

# (bool) Indicate if the application should be fullscreen or not
fullscreen = 0

# (list) Android permissions
android.permissions = INTERNET,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE

# (str) Android application class (default org.kivy.android.PythonActivity)
# android.appclass = org.kivy.android.PythonActivity

# (str) Android private libraries directory
# android.private_libs_arch = arm64-v8a

# (str) Android API level (targetSdkVersion)
android.api = 33

# (str) Minimum API level (minSdkVersion)
android.minapi = 21

# (str) Android architecture(s) to build for (comma separated)
android.archs = arm64-v8a
# android.archs = arm64-v8a,armeabi-v7a

# (bool) Ask the OS to keep the legacy external-storage behaviour (pre-11)
android.legacy_storage = True

# (bool) Enable AndroidX
android.enable_androidx = True

# (bool) Backup/restore
android.allow_backup = False

# (bool) Show the android loading animation
# android.use_animations = True

# (str) Android icon in the resources (relative to source.cwd)
# android.icon.filename = icon.png

# (int) Log level for the app (0..2)
android.log_level = 1

# (bool) Auto run main.py on Android (python-for-android)
# android.entrypoint = main.py

# (str) Kivy tools: version branch of kivy
p4a.branch = master

# (list) Gradle options to run when building the APK
# android.gradle_options = --offline

# (bool) Set the gradle to always use the sdk guaranteed by buildozer
# android.gradle_sdk = false


[buildozer]

# (int) Log level (0 = error, 1 = info, 2 = debug)
log_level = 1

# (path) Directory where the source code lives (relative to this spec)
source.dir = .

# (str) Global user directory for buildozer
# buildozer_dir = ~/.buildozer

# (str) Global directory where buildozer stores the Android SDK/NDK
# android_sdk_dir = ~/.buildozer/android/platform

# (str) Global directory where buildozer stores the Gradle files
# gradle_dir = ~/.buildozer/android/platform/gradle-workspace

# (bool) Wait for a successful build result before starting the debugger
# debug = false

# (str) Set the Android platform api version used to build
# android_api = 33