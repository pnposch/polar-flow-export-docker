#!/bin/bash

# Set the range of years
start_year=2020
end_year=2025

# Loop through each year and month
for (( year=$start_year; year<=$end_year; year++ )); do
  for (( month=1; month<=12; month++ )); do
    docker exec export python3 polar-export.py $month $year
  done
done