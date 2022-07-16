#!/bin/bash
# 把一堆資料夾內的影片以2個號碼為一組產生中間幀

fileCount=$(ls *.png | wc -l)
# echo $fileCount

for i in $(seq 1 2 $fileCount);
do
  j=$((i+1))
  f1=$(printf "out%04d.png" $i)
  f2=$(printf "out%04d.png" $j)
  f3=$(printf "out%04d_.png" $i)
  echo "$f1 and $f2 are processing..."
  python BMBC/run.py --first $f1 --second $f2 --output $f3  
  echo "$f3 is completed."
done