# ffmpeg Filter Chains — Exact Commands from Mazemaker Inception OS v7

Exact ffmpeg invocations used in the Mazemaker Inception OS film build.
All target 3840×2160 · 30fps · h264_nvenc.

---

## Pan Constants

```
W=3840 H=2160 FPS=30
LEAD=0.6  TAIL=1.2    # seconds of silence padding around each VO
INTRO=7.0  OUTRO=8.0  # card durations
```

---

## Panel Segment (even index, L→R pan)

```bash
D=$((LEAD + VO_DURATION + TAIL))
ffmpeg -y -loop 1 -framerate 30 -t $D \
  -i upscaled/style_20/00.png \
  -vf "scale=-2:2160:flags=lanczos,setsar=1,\
crop=3840:2160:x='min(max((iw-3840)*(t/$D),0),iw-3840)':y='(ih-2160)/2',\
eq=contrast=1.07:saturation=1.06:gamma=0.97,\
colorbalance=rs=-0.04:gs=-0.01:bs=0.05:rh=0.05:gh=0.02:bh=-0.05,\
vignette=PI/4.6,noise=alls=7:allf=t,\
drawtext=fontfile=/usr/share/fonts/TTF/JetBrainsMono-ExtraBold.ttf:\
text='I':x=140:y=h-260:fontsize=70:fontcolor=0xd4a843@0.85:\
alpha='if(lt(t,1),t,if(lt(t,$(echo "$D-1.6" | bc -l)),1,max(0,($D-t)/1.6)))':\
shadowcolor=black@0.6:shadowx=3:shadowy=3,\
drawtext=fontfile=/usr/share/fonts/TTF/JetBrainsMono-Bold.ttf:\
text='GENESIS':x=140:y=h-180:fontsize=48:fontcolor=0x2dd4bf@0.80:\
alpha='if(lt(t,1),t,if(lt(t,$(echo "$D-1.6" | bc -l)),1,max(0,($D-t)/1.6)))':\
shadowcolor=black@0.6:shadowx=3:shadowy=3,\
fade=t=in:st=0:d=0.7,fade=t=out:st=$(echo "$D-0.8" | bc -l):d=0.8,format=yuv420p" \
  -r 30 -c:v h264_nvenc -preset p6 -rc vbr -cq 20 -b:v 32M -maxrate 60M \
  -pix_fmt yuv420p -an work/film_seg_00.mp4
```

## Panel Segment (odd index, R→L + vertical drift)

```bash
ffmpeg -y -loop 1 -framerate 30 -t $D \
  -i upscaled/style_20/01.png \
  -vf "scale=-2:2320:flags=lanczos,setsar=1,\
crop=3840:2160:x='min(max((iw-3840)*(1-t/$D),0),iw-3840)':\
y='min(max((ih-2160)*(t/$D),0),ih-2160)',\
eq=contrast=1.07:saturation=1.06:gamma=0.97,\
colorbalance=rs=-0.04:gs=-0.01:bs=0.05:rh=0.05:gh=0.02:bh=-0.05,\
vignette=PI/4.6,noise=alls=7:allf=t,\
drawtext=fontfile=/usr/share/fonts/TTF/JetBrainsMono-ExtraBold.ttf:\
text='II':x=140:y=h-260:fontsize=70:fontcolor=0xd4a843@0.85:\
alpha='if(lt(t,1),t,if(lt(t,$(echo "$D-1.6" | bc -l)),1,max(0,($D-t)/1.6)))':\
shadowcolor=black@0.6:shadowx=3:shadowy=3,\
drawtext=fontfile=/usr/share/fonts/TTF/JetBrainsMono-Bold.ttf:\
text='AWAKENING':x=140:y=h-180:fontsize=48:fontcolor=0x2dd4bf@0.80:\
alpha='if(lt(t,1),t,if(lt(t,$(echo "$D-1.6" | bc -l)),1,max(0,($D-t)/1.6)))':\
shadowcolor=black@0.6:shadowx=3:shadowy=3,\
fade=t=in:st=0:d=0.7,fade=t=out:st=$(echo "$D-0.8" | bc -l):d=0.8,format=yuv420p" \
  -r 30 -c:v h264_nvenc -preset p6 -rc vbr -cq 20 -b:v 32M -maxrate 60M \
  -pix_fmt yuv420p -an work/film_seg_01.mp4
```

---

## Title Card (intro, 7s)

```bash
ffmpeg -y -f lavfi -t 7.000 -i color=c=0x07070d:s=3840x2160:r=30 \
  -vf "format=yuv420p,\
drawtext=fontfile=/usr/share/fonts/TTF/JetBrainsMono-ExtraBold.ttf:\
text='EVERY AI FORGETS YOU':x=(w-text_w)/2:y=900:\
fontsize=120:fontcolor=0xffffff:\
alpha='if(lt(t,0.8),t/0.8,if(lt(t,5.80),1,max(0,(7.00-t)/1.2)))':\
shadowcolor=black@0.7:shadowx=4:shadowy=4,\
drawtext=fontfile=/usr/share/fonts/TTF/JetBrainsMono-ExtraBold.ttf:\
text='STATELESS BY DESIGN':x=(w-text_w)/2:y=1050:\
fontsize=64:fontcolor=0x8a8a99:\
alpha='if(lt(t,0.8),t/0.8,if(lt(t,5.80),1,max(0,(7.00-t)/1.2)))':\
shadowcolor=black@0.7:shadowx=4:shadowy=4,\
drawtext=fontfile=/usr/share/fonts/TTF/JetBrainsMono-ExtraBold.ttf:\
text='UNTIL NOW':x=(w-text_w)/2:y=1200:\
fontsize=84:fontcolor=0x2dd4bf:\
alpha='if(lt(t,0.8),t/0.8,if(lt(t,5.80),1,max(0,(7.00-t)/1.2)))':\
shadowcolor=black@0.7:shadowx=4:shadowy=4,\
fade=t=in:st=0:d=0.6,fade=t=out:st=6.30:d=0.7" \
  -c:v h264_nvenc -preset p6 -rc vbr -cq 20 -b:v 32M -maxrate 60M \
  -pix_fmt yuv420p -an work/film_intro.mp4
```

## End Card (8s)

```bash
ffmpeg -y -f lavfi -t 8.000 -i color=c=0x07070d:s=3840x2160:r=30 \
  -vf "format=yuv420p,\
drawtext=fontfile=/usr/share/fonts/TTF/JetBrainsMono-ExtraBold.ttf:\
text='MAZEMAKER':x=(w-text_w)/2:y=780:\
fontsize=140:fontcolor=0xd4a843:\
alpha='if(lt(t,0.8),t/0.8,if(lt(t,6.80),1,max(0,(8.00-t)/1.2)))':\
shadowcolor=black@0.7:shadowx=4:shadowy=4,\
drawtext=fontfile=/usr/share/fonts/TTF/JetBrainsMono-ExtraBold.ttf:\
text='THE ONLY CODE THAT DREAMS':x=(w-text_w)/2:y=930:\
fontsize=58:fontcolor=0x2dd4bf:alpha=...,\
drawtext=fontfile=...:text='YOUR LOCAL MIND \u00b7 EVERYWHERE':...:fontsize=48:fontcolor=0xffffff,\
drawtext=fontfile=...:text='ANDROID SOON \u00b7 iOS NEXT \u00b7 ENCRYPTED ALWAYS':...:fontsize=40:fontcolor=0x8a8a99,\
drawtext=fontfile=...:text='mazemaker.online':...:fontsize=64:fontcolor=0xffffff,\
fade=t=in:st=0:d=0.6,fade=t=out:st=7.30:d=0.7" \
  -c:v h264_nvenc ... -an work/film_end.mp4
```

---

## Video Concat (lossless, copy codec)

```bash
echo "file 'work/film_intro.mp4'"  > work/concat.txt
echo "file 'work/film_seg_00.mp4'" >> work/concat.txt
...all segments...
echo "file 'work/film_end.mp4'"    >> work/concat.txt
ffmpeg -y -f concat -safe 0 -i work/concat.txt -c copy work/film_video.mp4
```

---

## Audio: VO with adelay+apad (per page)

```bash
# Per page: LEAD silence + VO + TAIL silence
ffmpeg -y -i voiceover_qwen/page_00.wav \
  -af "aresample=48000,aformat=channel_layouts=stereo,\
adelay=600|600,apad=whole_dur=28.400" \
  -t 28.400 -ar 48000 -ac 2 work/film_a_00.wav
```

## Audio: Music Bed (loop, normalized)

```bash
ffmpeg -y -stream_loop -1 -i trailer-soundtrack.flac \
  -t 198.100 \
  -af "aresample=48000,aformat=channel_layouts=stereo,\
loudnorm=I=-30:TP=-3:LRA=11,volume=0.9" \
  -ar 48000 -ac 2 work/film_bed.wav
```

## Audio: Sidechain Duck + Mix

```bash
ffmpeg -y -i work/film_vo_master.wav -i work/film_bed.wav \
  -filter_complex \
  "[0:a]aresample=48000,volume=1.4[vo];\
   [1:a][vo]sidechaincompress=threshold=0.04:ratio=8:attack=15:release=380[duck];\
   [vo][duck]amix=inputs=2:weights=1 1:normalize=0,\
   alimiter=limit=0.95,aresample=48000[a]" \
  -map "[a]" -ar 48000 -ac 2 work/film_final_audio.wav
```

---

## Final Mux

```bash
ffmpeg -y -i work/film_video.mp4 -i work/film_final_audio.wav \
  -map 0:v -map 1:a -c:v copy -c:a aac -b:a 256k -shortest \
  mazemaker-inception-os-film.mp4
```

---

## Trailer 90s Cut: VO Fragment Extraction

Extract trailing N seconds for the punch line:

```bash
# Punch line from page_03 (recall prism): "This is not search..."
ffmpeg -y -sseof -3.7 -i voiceover_qwen/page_03.wav \
  -af "afade=t=in:st=0:d=0.15,volume=1.4" \
  -t 3.7 work/vo_remember.wav

# Punch line from page_10 (federation): "Minds multiply..."
ffmpeg -y -sseof -6.0 -i voiceover_qwen/page_10.wav \
  -af "afade=t=in:st=0:d=0.15,volume=1.4" \
  -t 6.0 work/vo_minds.wav

# Closing from page_14 (morning): Full climax + mobile line
ffmpeg -y -sseof -13.8 -i voiceover_qwen/page_14.wav \
  -af "afade=t=in:st=0:d=0.3,volume=1.4" \
  -t 13.8 work/vo_close.wav
```

## Trailer 90s Cut: Audio Elements

```bash
# Drone (55Hz + 82.5Hz sub-bass)
ffmpeg -y -f lavfi -i sine=f=55:r=48000 -f lavfi -i sine=f=82.5:r=48000 \
  -filter_complex "[0][1]amix=2,tremolo=f=0.12:d=0.5,lowpass=f=170,\
aecho=0.8:0.7:55:0.3,volume=0.55" \
  -t $TOTAL -ar 48000 -ac 2 work/tr_drone.wav

# Thump (58Hz, 0.55s, lowpassed hit)
ffmpeg -y -f lavfi -i sine=f=58:d=0.55 \
  -af "afade=t=out:st=0.06:d=0.49,lowpass=f=140,volume=1.1" thump.wav

# Delayed audio element (for VO fragments and thumps at specific cuts)
ffmpeg -y -i source.wav \
  -af "aresample=48000,aformat=channel_layouts=stereo,volume=$VOL,\
adelay=${START_MS}|${START_MS},apad=whole_dur=$TOTAL" \
  -t $TOTAL -ar 48000 -ac 2 work/delayed_audio.wav
```
