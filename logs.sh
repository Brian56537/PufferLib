#!/bin/bash
output_file="logs.txt"
unique_names_file="unique_names.txt"
unique_moves_file="unique_moves.txt"

format_log_entry() {
  awk '/Slot:/,/^$/' "$1" | sed 's/^/  /'
}

# Find all .txt files in the current working directory
find . -type f -name "*.txt" -print0 | while IFS= read -r -d '' log_file; do
  # Extract unique names and moves
  format_log_entry "$log_file" | grep -o 'Name:.*' | sed 's/Name: //' >> "$unique_names_file"
  format_log_entry "$log_file" | grep -o 'Moves:.*' | sed 's/Moves: //' | tr ',' '\n' | sed '/^$/d' >> "$unique_moves_file"
done

# Sort and remove duplicates from unique names and moves
sort -u "$unique_names_file" > "$unique_names_file.tmp"
sort -u "$unique_moves_file" > "$unique_moves_file.tmp"
mv "$unique_names_file.tmp" "$unique_names_file"
mv "$unique_moves_file.tmp" "$unique_moves_file"

# Create the output file
{
  echo "============= Unique Pokemon ============="
  cat "$unique_names_file"
  echo
  echo "============== Unique Moves =============="
  cat "$unique_moves_file"
  echo
  echo "================== Log Entries =================="

  # Process all .txt files in the current working directory
  find . -type f -name "*.txt" -print0 | while IFS= read -r -d '' log_file; do
    echo "==============${log_file}=============="
    format_log_entry "$log_file"
  done
} > "$output_file"

# Clean up temporary files
rm "$unique_names_file" "$unique_moves_file"

echo "Done..."
