#!/bin/bash
cd "$(dirname "$0")"
B=https://d8j0ntlcm91z4.cloudfront.net/user_36QRYf7SF1sWq9WPFwjX5YdoXtA
while read n f; do [ -s clips/clip_$n.mp4 ] || curl -s -o clips/clip_$n.mp4 "$B/$f.mp4" & done < urls.txt; wait; ls clips | wc -l
