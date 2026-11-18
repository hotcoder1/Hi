#!/usr/bin/env bash
# Builds a 6-minute fake GTA stream recording: test-pattern "gameplay", a facecam box
# at the bottom-left (x=40 y=770 w=480 h=270 of 1920x1080), quiet room noise, a loud
# moment at 3:00 and a smaller one at 1:10. Chat (chat.json) spikes at ~3:06-3:20.
set -eu
ffmpeg -hide_banner -loglevel error -y -f lavfi -i "testsrc2=s=1920x1080:rate=30" \
  -f lavfi -i "color=c=0x335577:s=480x270:r=30" -f lavfi -i "anoisesrc=d=360:c=pink:a=0.02" \
  -f lavfi -i "anoisesrc=d=3:c=white:a=0.5" -f lavfi -i "sine=f=300:d=2" \
  -filter_complex "[0:v][1:v]overlay=40:770[v];[3:a]aresample=48000,adelay=180000|180000,apad[s1];[4:a]aresample=48000,volume=0.6,adelay=70000|70000,apad[s2];[2:a]aresample=48000[n];[n][s1][s2]amix=inputs=3:normalize=0:duration=first[a]" \
  -map "[v]" -map "[a]" -t 360 -c:v libx264 -preset ultrafast -crf 30 -c:a aac -b:a 128k stream.mp4
