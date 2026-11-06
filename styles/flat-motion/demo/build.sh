#!/bin/sh
# Rebuild "One Orange" from scratch: sh styles/flat-motion/demo/build.sh (run from anywhere). Needs ffmpeg 7+ for mux.sh.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
LIB=${LIB:-$(cd "$HERE/../../.." && pwd)}; export LIB
[ -f "$LIB/core/render/video.mjs" ] || { echo "set LIB to the library folder"; exit 1; }
PY="$LIB/.venv/bin/python"; O=$(dirname "$HERE")
F="$HERE/fonts"; G=https://raw.githubusercontent.com/google/fonts/main/ofl                      # 0. OFL fonts, fetched once
[ -f "$F/GochiHand-Regular.ttf" ] || curl -sSfL -o "$F/GochiHand-Regular.ttf" "$G/gochihand/GochiHand-Regular.ttf"
[ -f "$F/CaveatBrush-Regular.ttf" ] || curl -sSfL -o "$F/CaveatBrush-Regular.ttf" "$G/caveatbrush/CaveatBrush-Regular.ttf"
cd "$LIB"; mkdir -p "$HERE/out"
node "$HERE/tools/timeline.mjs" > "$HERE/out/timeline.json"                                     # 1. timeline → JSON
node core/render/events.mjs "$HERE"                                                             # 2. sound events → events.json
"$PY" "$HERE/music/score.py"                                                                    # 3. synthesized score → music/stems
"$PY" "$HERE/mix.py"                                                                            # 4. foley + ambience + score → out/mix.wav
node core/render/readcheck.mjs "$HERE"                                                          # 5. on-screen words stay long enough
node core/render/video.mjs "$HERE" --fps 24 --workers 4 --out "$HERE/out/video.mp4"             # 6. frames (12 drawings/s, 24 fps out)
sh core/render/mux.sh "$HERE/out/video.mp4" "$HERE/out/mix.wav" "$O/flat-motion.mp4" 24 0       # 7. −14 LUFS, no grain
node core/render/still.mjs "$HERE" 3.5 12.8 --prefix s_ --out "$HERE/out/still"                 # 8. stills
node core/render/still.mjs "$HERE" 0 --q test=model --prefix model_ --out "$HERE/out/still"
cp "$HERE/out/still/s_3.5.jpg" "$HERE/stills/styleframe.jpg"; cp "$HERE/out/still/s_12.8.jpg" "$O/poster.jpg"
cp "$HERE/out/still/model_0.jpg" "$HERE/stills/modelsheet.jpg"
