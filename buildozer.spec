[app]
title           = Spelling Sprint League
package.name    = spellingsprint
package.domain  = org.spellingsprint

source.dir      = .
source.include_exts = py,png,jpg,jpeg,json,atlas,ttf,otf

version         = 1.0

requirements    = python3,pygame==2.1.3

orientation     = landscape
fullscreen      = 1

android.api     = 33
android.minapi  = 21
android.ndk     = 25b
android.archs   = arm64-v8a

android.permissions  = INTERNET
android.allow_backup = True

[buildozer]
log_level    = 2
warn_on_root = 1
