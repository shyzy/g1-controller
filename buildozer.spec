[app]

title = G1 Controller
package.name = g1controller
package.domain = com.unitree.g1app
source.dir = .
source.include_exts = py,png,jpg,html,json,txt
version = 1.0.0

requirements = python3,kivy==2.3.0,unitree_webrtc_connect,evdev,curl_cffi,pycryptodome

android.permissions = INTERNET,ACCESS_WIFI_STATE,CHANGE_WIFI_STATE,ACCESS_NETWORK_STATE
android.api = 33
android.minapi = 26
android.ndk = 25c
android.sdk = 33
android.gradle_dependencies = 'com.google.android.material:material:1.9.0'
android.enable_androidx = True

orientation = landscape

osx.python_version = 3
osx.kivy_version = 2.3.0

[buildozer]

log_level = 2
warn_on_root = 1

[app:android]

android.archs = arm64-v8a
android.accept_sdk_license = True
