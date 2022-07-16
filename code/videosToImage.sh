#!/bin/bash
# 把一部以30秒為一個間隔取連續的兩幀，取得十筆測資

# pick 8 frames every 5 seconds.
# ffmpeg -i in.mp4 -vf "select='if(not(floor(mod(t,5)))*lt(ld(1),1),st(1,1)+st(2,n)+st(3,t));if(eq(ld(1),1)*lt(n,ld(2)+8),1,if(trunc(t-ld(3)),st(1,0)))'" -vsync 0 out%03d.png
# Change the 5 in mod(t,5) for the interval, in seconds. And the 8 in ld(2)+8 for the number of frames to select.

# BASEDIR=$(dirname "$0")
# echo "Hello World."
# echo "${BASEDIR}/$i"

for i in *.mp4;
  do name=`echo "$i" | cut -d'.' -f1`
  echo "$name"
  ffmpeg -i "$i" -vf "select='if(not(floor(mod(t,20)))*lt(ld(1),1),st(1,1)+st(2,n)+st(3,t));if(eq(ld(1),1)*lt(n,ld(2)+2),1,if(trunc(t-ld(3)),st(1,0)))'" -vsync 0 "out%04d.png"
done