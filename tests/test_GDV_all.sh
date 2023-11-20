#!/bin/bash

directory="samples/allvulnerable"
zip_file="samples/allvulnerable.tar.gz"

if [ ! -d "$directory" ]; then
    tar -xzf "$zip_file" -C "samples/"
    echo "Extracted $zip_file to $directory"
fi

index=0
count=0
total_files=$(find $directory -maxdepth 1 -type f -name "*.wasm" | wc -l)

if [ ! -d "$directory" ]; then
  echo "Directory not found: $directory"
  exit 1
fi

for file in "$directory"/*; do
  if [[ -f "$file" && "$file" == *.wasm ]]; then
    index=$((index + 1))
    echo "Analyzing file: $file ($index/$total_files)"
    output=$(python3 main.py -f "$file")
    if [ "${output: -1}" == "1" ]; then
      count=$((count + 1))
    fi
  fi
done

echo "Total number of files analyzed: $index"
echo "Detected Groundhog Day Vulnerabilities: $count"