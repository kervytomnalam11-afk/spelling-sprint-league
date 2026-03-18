[app]
title           = Spelling Sprint League
package.name    = spellingsprint
package.domain  = org.spellingsprint

source.dir      = .
source.include_exts = py,png,jpg,jpeg,json,atlas,ttf,otf

version         = 1.0

requirements    = python3,pygame

orientation     = landscape
fullscreen      = 1

android.api         = 33
android.minapi      = 21
android.ndk         = 25b
android.archs       = arm64-v8a, armeabi-v7a

android.permissions = INTERNET

android.allow_backup = True

# presplash / icon — replace these files in your repo to customise
# presplash.filename = %(source.dir)s/assets/presplash.png
# icon.filename      = %(source.dir)s/assets/icon.png

[buildozer]
log_level = 2
warn_on_root = 1
