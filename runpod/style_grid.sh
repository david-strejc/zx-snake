#!/usr/bin/env bash
# Build one 9:16 clip showing the four style registers at once, so they can be judged side by side
# on a phone. Each quadrant keeps its own generated audio; the grid is silent on purpose.
#
#   top-left  flash    direct-flash night snapshot
#   top-right selfie   front-facing arm's-length
#   bottom-l  static   locked-off observational
#   bottom-r  glossy   the control: "cinematic golden hour" slop
set -euo pipefail
cd "$(dirname "$0")"

ffmpeg -y -v error \
  -i clips/st_flash.mp4 -i clips/st_selfie.mp4 -i clips/st_static.mp4 -i clips/st_glossy.mp4 \
  -filter_complex "
    [0:v]setpts=PTS/1.25,fps=30,scale=384:672,drawtext=text='FLASH':x=8:y=8:fontsize=22:fontcolor=white:borderw=2:bordercolor=black[a];
    [1:v]setpts=PTS/1.25,fps=30,scale=384:672,drawtext=text='SELFIE':x=8:y=8:fontsize=22:fontcolor=white:borderw=2:bordercolor=black[b];
    [2:v]setpts=PTS/1.25,fps=30,scale=384:672,drawtext=text='LOCKED OFF':x=8:y=8:fontsize=22:fontcolor=white:borderw=2:bordercolor=black[c];
    [3:v]setpts=PTS/1.25,fps=30,scale=384:672,drawtext=text='CINEMATIC (control)':x=8:y=8:fontsize=22:fontcolor=yellow:borderw=2:bordercolor=black[d];
    [a][b][c][d]xstack=inputs=4:layout=0_0|w0_0|0_h0|w0_h0,format=yuv420p[v]" \
  -map "[v]" -an -c:v libx264 -preset medium -crf 18 -movflags +faststart style_matrix.mp4

ffprobe -v error -show_entries format=duration -show_entries stream=width,height -of default=nw=1 style_matrix.mp4
