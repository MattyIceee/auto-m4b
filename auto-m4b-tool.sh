#!/bin/bash

DEFAULT_SLEEP_TIME=30s

add_trailing_slash() {
    # adds a trailing slash to path
    local path="$1"
    if [[ ! "$path" == */ ]]; then
        path="$path/"
    fi
    echo "$path"
}

rm_trailing_slash() {
    # removes a trailing slash from path
    local path="$1"
    if [[ "$path" == */ ]]; then
        path="${path%?}"
    fi
    echo "$path"
}

rm_leading_dot_slash() {
    # removes a leading ./ from path if it exists
    local path="$1"
    if [[ "$path" == ./* ]]; then
        path="${path#./}"
    fi
    echo "$path"
}

# set m to 1
m=1

#variable defenition
inboxfolder="${INBOX_FOLDER:-"/volume1/Downloads/#done/#books/#convert/inbox/"}"
outputfolder="${OUTPUT_FOLDER:-"/volume1/Downloads/#done/#books/#convert/converted/"}"
donefolder="${DONE_FOLDER:-"/volume1/Downloads/#done/#books/#convert/processed/"}"
fixitfolder="${FIXIT_FOLDER:-"/volume1/Downloads/#done/#books/#convert/fix/"}"
backupfolder="${BACKUP_FOLDER:-"/volume1/Downloads/#done/#books/#convert/backup/"}"

remote_buildfolder="${BUILD_FOLDER:-"/volume1/Downloads/#done/#books/#convert/#tmp/build/"}"
remote_mergefolder="${MERGE_FOLDER:-"/volume1/Downloads/#done/#books/#convert/#tmp/merge/"}"
remote_binfolder="${BIN_FOLDER:-"/volume1/Downloads/#done/#books/#convert/#tmp/delete/"}"

buildfolder="${BUILD_FOLDER:-"/tmp/auto-m4b/build/"}"
# buildfolder="$remote_buildfolder"
mergefolder="${MERGE_FOLDER:-"/tmp/auto-m4b/merge/"}"
binfolder="${BIN_FOLDER:-"/tmp/auto-m4b/delete/"}"

audio_exts=( 
    -name '*.mp3' 
    -o -name '*.m4a' 
    -o -name '*.m4b' 
    -o -name '*.wma'
)

other_exts=(
    -name '*.jpg'
    -o -name '*.jpeg'
    -o -name '*.png'
    -o -name '*.gif'
    -o -name '*.bmp'
    -o -name '*.tiff'
    -o -name '*.svg'
    -o -name '*.epub'
    -o -name '*.mobi'
    -o -name '*.azw'
    -o -name '*.pdf'
    -o -name '*.txt'
    -o -name '*.log'
)
# -----------------------------------------------------------------------
# Log startup notice
# -----------------------------------------------------------------------
# Create a file at /tmp/auto-m4b/started.txt with the current date and time if it does not exist
# If it does exist, echo startup notice
# If it does, do nothing.

if [ ! -f "/tmp/auto-m4b/started.txt" ]; then
    sleep 5
    mkdir -p "/tmp/auto-m4b/"
    touch "/tmp/auto-m4b/started.txt"
    current_local_time=$(date +"%Y-%m-%d %H:%M:%S")
    echo "auto-m4b started at $current_local_time", watching "$inboxfolder" >> "/tmp/auto-m4b/started.txt"
    echo "Starting auto-m4b..."
    echo "Watching \"$inboxfolder\" for books to convert ⌐O-O"
fi

draw_line() {
    printf '%.0s-' {1..80}
    echo
}

swap_first_last() {
    local _name="$1"
    if echo "$_name" | grep -q ','; then
      local _lastname=$(echo "$_name" | perl -n -e '/^(.*?), (.*?)$/ && print "$1"')
      local _givenname=$(echo "$_name" | perl -n -e '/^(.*?), (.*?)$/ && print "$2"')
    else
      local _lastname=$(echo "$_name" | perl -n -e '/^.*\s(\S+)$/ && print "$1"')
      local _givenname=$(echo "$_name" | perl -n -e '/^(.*?)\s\S+$/ && print "$1"')
    fi

    # If there is a given name, swap the first and last name and return it
    if [ -n "$_givenname" ]; then
        echo "$_givenname $_lastname"
    else
        # Otherwise, return the original name
        echo "$_name"
    fi
}

extract_folder_info() {
    local folder_name="$1"

    local author_pattern="^(.*?)[\W\s]*[-_–—\(]"
    local book_title_pattern="(?<=[-_–—])[\W\s]*(?<book_title>[\w\s]+?)\s*(?=\d{4}|\(|\[|$)"
    local year_pattern="(?P<year>\d{4})"
    local narrator_pattern="narrat(ed by|or)\W+(?<narrator>[\w\s.-]+?)[.\s]*(?:$|\(|\[|$)"

    # Replace single occurrences of . with spaces
    folder_name=$(echo "$folder_name" | sed 's/\./ /g')

    local dir_author=$(echo "$folder_name" | perl -n -e "/$author_pattern/ && print \$1")
    local dir_author=$(swap_first_last "$dir_author")

    local dir_author=$(echo "$givennames $lastname")
    local dir_title=$(echo "$folder_name" | perl -n -e "/$book_title_pattern/ && print \$+{book_title}")
    local dir_year=$(echo "$folder_name" | perl -n -e "/$year_pattern/ && print \$+{year}")
    local dir_narrator=$(echo "$folder_name" | perl -n -e "/$narrator_pattern/i && print \$+{narrator}")

    local dir_extrajunk="$folder_name"

    # Iterate through properties in reverse order of priority
    for property in "dir_narrator" "dir_year" "dir_title" "dir_author"; do
      local property_value=$(eval echo "\$$property")
      if [ -n "$property_value" ]; then
        # Split dir_extrajunk on property_value
        dir_extrajunk=$(echo "$dir_extrajunk" | awk -F"$property_value" '{print $2}')
        # Trim leading and contiguous .,)]} and whitespace
        dir_extrajunk=$(echo "$dir_extrajunk" | sed -E 's/^[[:space:],.)}\]]*//')
        break  # Add break to exit loop after first non-empty property
      fi
    done
}

basename() {
    local _basename
    if [ -z "$1" ]; then
        while read -r _basename; do
            _basename=$(echo "$_basename" | sed 's/\/$//' | awk -F/ '{print $NF}')
            echo "$_basename"
        done
    else
        _basename=$(echo "$1" | sed 's/\/$//' | awk -F/ '{print $NF}')
        echo "$_basename"
    fi
}

rm_audio_ext() {
    local _string
    if [ -z "$1" ]; then
        while read -r _string; do
            echo "$_string" | sed 's/\(\.m\(4a\|4b\|p3\)\)$//i'
        done
    else
        echo "$1" | sed 's/\(\.m\(4a\|4b\|p3\)\)$//i'
    fi
}

rm_ext() {
    local _string
    if [ -z "$1" ]; then
        while read -r _string; do
            echo "$_string" | sed 's/\.[^.]*$//'
        done
    else
        echo "$1" | sed 's/\.[^.]*$//'
    fi
}

get_ext() {
    local _string
    if [ -z "$1" ]; then
        while read -r _string; do
            echo "$_string" | sed 's/^.*\.//'
        done
    else
        echo "$1" | sed 's/^.*\.//'
    fi
}

escape_special_chars() {
    local _string="$1"
    echo "$_string" | sed 's/[][()*?|&]/\\&/g'
}

ensure_dir_exists_and_is_writable() {
    local _dir="$1"
    local _exit_on_error="${2:-"true"}"
    if [ ! -d "$_dir" ]; then
        echo "\"$_dir\" does not exist, creating it..."
        mkdir -p "$_dir"
    fi

    if [ ! -w "$_dir" ]; then
        if [ "$_exit_on_error" == "true" ]; then
            echo " *** Error: $_dir is not writable by current user. Please fix permissions and try again."
            exit 1
        else
            echo " *** Warning: $_dir is not writable by current user, this may result in data loss."
            return 1
        fi
        echo " *** Error: $_dir is not writable by current user. Please fix permissions and try again."
        exit 1
    fi
}

cp_dir() {

    # Remove trailing slash from source and add trailing slash to destination
    local _source_dir=$(rm_trailing_slash "$1")
    local _dest_dir=$(add_trailing_slash "$2")

    # Check if both dirs exist, otherwise exit with error
    if [ ! -d "$_source_dir" ]; then
        echo " *** Error: Source directory \"$_source_dir\" does not exist"
        exit 1
    fi

    if [ ! -d "$_dest_dir" ]; then
        echo " *** Error: Destination directory \"$_dest_dir\" does not exist"
        exit 1
    fi

    # Make sure both paths are dirs
    if [ ! -d "$_source_dir" ]; then
        echo " *** Error: Source \"$_source_dir\" is not a directory"
        exit 1
    fi

    if [ ! -d "$_dest_dir" ]; then
        echo " *** Error: Destination \"$_dest_dir\" is not a directory"
        exit 1
    fi

    cp -rf "$_source_dir"* "$_dest_dir"
}

cp_file_to_dir() {

    # Add trailing slash to destination
    local _source_file="$1"
    local _dest_dir=$(add_trailing_slash "$2")

    # Check if both dirs exist, otherwise exit with error
    if [ ! -f "$_source_file" ]; then
        echo " *** Error: Source file \"$_source_file\" does not exist"
        exit 1
    fi

    if [ ! -d "$_dest_dir" ]; then
        echo " *** Error: Destination directory \"$_dest_dir\" does not exist"
        exit 1
    fi

    # Make sure destination path is a dir
    if [ ! -d "$_dest_dir" ]; then
        echo " *** Error: Destination \"$_dest_dir\" is not a directory"
        exit 1
    fi

    cp -rf "$_source_file" "$_dest_dir"
}

mv_dir() {

    # Remove trailing slash from source and add trailing slash to destination
    local _source_dir=$(rm_trailing_slash "$1")
    local _dest_dir=$(add_trailing_slash "$2")

    # Check if both dirs exist, otherwise exit with error
    if [ ! -d "$_source_dir" ]; then
        echo " *** Error: Source directory \"$_source_dir\" does not exist"
        exit 1
    fi

    if [ ! -d "$_dest_dir" ]; then
        echo " *** Error: Destination directory \"$_dest_dir\" does not exist"
        exit 1
    fi

    # Make sure both paths are dirs
    if [ ! -d "$_source_dir" ]; then
        echo " *** Error: Source \"$_source_dir\" is not a directory"
        exit 1
    fi

    if [ ! -d "$_dest_dir" ]; then
        echo " *** Error: Destination \"$_dest_dir\" is not a directory"
        exit 1
    fi

    # Move the source dir to the destination dir by moving all files in source dir to dest dir
    # Overwrite existing files, then remove the source dir
    mv "$_source_dir"* "$_dest_dir"
    rm -rf "$_source_dir"
}

mv_file_to_dir() {

    # Add trailing slash to destination
    local _source_file="$1"
    local _dest_dir=$(add_trailing_slash "$2")

    # Check if both dirs exist, otherwise exit with error
    if [ ! -f "$_source_file" ]; then
        echo " *** Error: Source file \"$_source_file\" does not exist"
        exit 1
    fi

    if [ ! -d "$_dest_dir" ]; then
        echo " *** Error: Destination directory \"$_dest_dir\" does not exist"
        exit 1
    fi

    # Make sure destination path is a dir
    if [ ! -d "$_dest_dir" ]; then
        echo " *** Error: Destination \"$_dest_dir\" is not a directory"
        exit 1
    fi

    mv "$_source_file" "$_dest_dir"
}

cd_merge_folder() {
    # take optional argument to cd to a subfolder
    local _subfolder="$1"
    cd "$mergefolder$_subfolder" || return
}

cd_inbox_folder() {
    # take optional argument to cd to a subfolder
    local _subfolder="$1"
    cd "$inboxfolder$_subfolder" || return
}

rmdir_force() {
    local _dir=$(rm_trailing_slash "$1")
    local _exit_on_error="${2:-"true"}"
    # 1. Silently try and remove the directory
    # 2. Try to ls the parent directory to make sure the directory was removed
    # 3. If it was not removed, try to rename it to -old and remove it again
    # 4. If it was not removed, exit with error
    # 5. If it was remove successfully, recreate it

    rm -rf "$_dir" 2>/dev/null
    basename=$(basename "$_dir")
    parent_dir=$(dirname "$_dir")

    why="     This can happen if another network device is using the folder (e.g. a Mac with Finder open to the folder)."
    
    # find in parent dir a dir with the same name as the one we are trying to delete
    found=$(find "$parent_dir" -maxdepth 1 -type d -name "$basename" -print0)
    if [ -n "$found" ]; then
        echo " *** Warning: Unable to delete \"$_dir\", renaming it to -old and trying again..."
        mv "$_dir" "$_dir-old"

        # check if the dir was renamed successfully
        if [ ! -d "$_dir-old" ]; then
            echo " *** Error: Unable to rename \"$_dir\" to \"$_dir-old\""
            echo "$why"
            if [ "$_exit_on_error" == "true" ]; then
                exit 1
            else
                return 1
            fi
        fi

        rm -rf "$_dir-old" 2>/dev/null
        if ls "$parent_dir" | grep -q "$_dir"; then
            echo " *** Error: Unable to delete \"$_dir\", please delete it manually and try again."
            echo "$why"
            if [ "$_exit_on_error" == "true" ]; then
                exit 1
            else
                return 1
            fi
        fi
    fi
}

clean_workdir() {
    local _dir=$(rm_trailing_slash "$1")
    # 1. Silently try and remove the directory
    # 2. Try to ls the parent directory to make sure the directory was removed
    # 3. If it was not removed, try to rename it to -old and remove it again
    # 4. If it was not removed, exit with error
    # 5. If it was remove successfully, recreate it

    rmdir_force "$_dir" 
    
    mkdir -p "$_dir" 2>/dev/null

    if [ ! -w "$_dir" ]; then
        echo " *** Error: $_dir is not writable by current user. Please fix permissions and try again."
        sleep 30
        exit 1
    fi

    # Make sure dir is empty, otherwise error
    if [ -n "$(ls -A "$_dir")" ]; then
        echo " *** Error: $_dir is not empty; please empty it manually and try again."
        echo "$why"
        sleep 30
        exit 1
    fi
}

log_results() {
    # takes the original book's path and the result of the book and logs to $outputfolder/auto-m4b.log
    # format: [date] [time] [original book relative path] [info] ["result"=success|failed] [failure-message]
    local _book_src=$(basename "$1")
    # Quality: 128 kb/s @ 44.1 kHzz | Type: .mp3 | Files: 2 | Size: 11M 
    # pad quality with spaces to 28 characters
    local _quality=$(printf '%-19s' "$bitrate_friendly @ $samplerate_friendly")
    local _count=$(printf '%-9s' "$audio_files_count files")
    local _info=$(echo Quality: "$_quality | .$file_type | $_count | $audio_files_size")
    local _result="$2"
    local _elapsed="$3"

    # pad the relative path with spaces to 70 characters
    _book_src=$(printf '%-70s' "\"$_book_src\"")

    # get current date and time
    local _datetime=$(date +"%Y-%m-%d %H:%M:%S")

    # pad result with spaces to 9 characters
    _result=$(printf '%-9s' "[$_result]")

    # log the results
    echo "$_datetime  $_result $_book_src $_info $_elapsed" >> "$outputfolder/auto-m4b.log"
}

get_log_entry() {
    # looks in the log file to see if this book has been converted before and returns the log entry or ""
    local _book_src=$(basename "$1")
    local _log_entry=$(grep "$_book_src" "$outputfolder/auto-m4b.log")
    echo "$_log_entry"
}

human_elapsed_time() {
    # make friendly elapsed time as HHh:MMm:SSs but don't show hours if 0
    # e.g. 00m:52s, 12m:52s, 1h:12m:52s 

    local _elapsedtime="$1"

    local _hours=$(bc <<< "scale=0; $_elapsedtime/3600")
    local _minutes=$(bc <<< "scale=0; ($_elapsedtime%3600)/60")
    local _seconds=$(bc <<< "scale=0; $_elapsedtime%60")
    local _human_elapsed=$(printf "%02dh:%02dm:%02ds\n" $_hours $_minutes $_seconds | sed 's/^0//;s/^0*h.//;s/^0(?!m)//')
    echo "$_human_elapsed"
}

get_size() {
    # takes a file or directory and returns the size in either bytes or human readable format, only counting audio files
    # if no path specified, assume current directory
    local _path="${1:-"."}"
    local _format="${2:-"bytes"}"
    local _size=$(du -sb "$_path" | awk '{print $1}')
    if [ "$_format" == "human" ]; then
        _size=$(echo "$_size" | numfmt --to=iec)
    fi
    echo "$_size"
}

get_duration() {
    # takes a file or directory and returns the length in seconds of all audio files
    # if no path specified, assume current directory
    # takes a "human" arg that returns the length in human readable format, rounding to the nearest minute
    local _path="${1:-"."}"
    local _format="${2:-"bytes"}"

    # check if path exists and whether is a dir or single file. If single file, return length of it, otherwise return length of all files in dir
    if [ ! -e "$_path" ]; then
        echo "Path \"$_path\" does not exist."
        exit 1
    elif [ -f "$_path" ]; then

        # make sure it is in audio_exts otherwise throw
        if [[ ! $(find "$_path" -type f \( "${audio_exts[@]}" \)) ]]; then
            echo "File \"$_path\" is not an audio file."
            exit 1
        fi

        local _length=$(ffprobe -hide_banner -loglevel 0 -of flat -i "$_path" -show_entries format=duration -of default=noprint_wrappers=1:nokey=1)
        if [ "$_format" == "human" ]; then
          _length=$(printf "%.0f" "$_length")  # Round up to the nearest second
          _length=$(human_elapsed_time "$_length")
      fi
        echo "$_length"
    elif [ -d "$_path" ]; then
        
        # make sure there are some audio files in the dir. Get a list of them all, and then the count, and if count is 0 exit. Otherwise, loop files and add up length
        
        _files=$(find "$_path" -type f \( "${audio_exts[@]}" \))
        _count=$(echo "$_files" | wc -l)
        if [ $_count -eq 0 ]; then
            echo "No audio files found in \"$_path\"."
            exit 1
        fi

        local _length=0
        while read -r _file; do
            _length=$(echo "$_length + $(get_duration "$_file")" | bc)
        done <<< "$_files"

        if [ "$_format" == "human" ]; then
            # if length has a decimal value that is less than 0.1, round down to nearest second, otherwise round up to nearest second
            local _decimal=$(echo "$_length" | sed 's/^[0-9]*\.//')
            if [ "$_decimal" -lt 1 ]; then
                _length=$(printf "%.0f" "$_length")  # Round down to the nearest second
            else
                _length=$(printf "%.0f" "$_length")  # Round up to the nearest second
            fi
            _length=$(human_elapsed_time "$_length")
        fi
        echo "$_length"
    fi
    
}

extract_metadata() {
    sample_audio=$(find . -maxdepth 1 -type f \( "${audio_exts[@]}" \) | head -n 1)

    echo -e "\nSampling \"$(rm_leading_dot_slash "$sample_audio")\" for id3 tags and quality information..."

    bitrate=$(ffprobe -hide_banner -loglevel 0 -of flat -i "$sample_audio" -select_streams a -show_entries format=bit_rate -of default=noprint_wrappers=1:nokey=1)
    samplerate=$(ffprobe -hide_banner -loglevel 0 -of flat -i "$sample_audio" -select_streams a -show_entries stream=sample_rate -of default=noprint_wrappers=1:nokey=1)

    # read id3 tags of mp3 file
    id3_title=$(ffprobe -hide_banner -loglevel 0 -of flat -i "$sample_audio" -select_streams a -show_entries format_tags=title -of default=noprint_wrappers=1:nokey=1)
    id3_artist=$(ffprobe -hide_banner -loglevel 0 -of flat -i "$sample_audio" -select_streams a -show_entries format_tags=artist -of default=noprint_wrappers=1:nokey=1)
    id3_albumartist=$(ffprobe -hide_banner -loglevel 0 -of flat -i "$sample_audio" -select_streams a -show_entries format_tags=album_artist -of default=noprint_wrappers=1:nokey=1)
    id3_album=$(ffprobe -hide_banner -loglevel 0 -of flat -i "$sample_audio" -select_streams a -show_entries format_tags=album -of default=noprint_wrappers=1:nokey=1)
    id3_sortalbum=$(ffprobe -hide_banner -loglevel 0 -of flat -i "$sample_audio" -select_streams a -show_entries format_tags=sort_album -of default=noprint_wrappers=1:nokey=1)
    id3_date=$(ffprobe -hide_banner -loglevel 0 -of flat -i "$sample_audio" -select_streams a -show_entries format_tags=date -of default=noprint_wrappers=1:nokey=1)
    id3_year=$(echo "$id3_date" | grep -Eo '[0-9]{4}')

    # Title:
    if [ -z "$id3_title" ] && [ -z "$id3_album" ] && [ -z "$id3_sortalbum" ]; then
        # If no id3_title, id3_album, or id3_sortalbum, use the extracted title
        title="$dir_title"
    else
        # If album or sort album is in title, use album or sort album
        # Otherwise, use album, then sort album, then extracted title
        if echo "$id3_album" | grep -q -i "$id3_title"; then
            title="$id3_album"
        elif echo "$id3_sortalbum" | grep -q -i "$id3_title"; then
            title="$id3_sortalbum"
        elif [ -n "$id3_album" ]; then
            title="$id3_album"
        elif [ -n "$id3_sortalbum" ]; then
            title="$id3_sortalbum"
        else
            title="$id3_title"
        fi
    fi
    echo "- Title: $title"


    # Album:
    if [ -n "$id3_album" ]; then
        album="$id3_album"
    elif [ -n "$id3_sortalbum" ]; then
        album="$id3_sortalbum"
    else
        album="$dir_title"
    fi
    echo "- Album: $album"

    if [ -n "$id3_sortalbum" ]; then
        sort_album="$id3_sortalbum"
    elif [ -n "$id3_album" ]; then
        sort_album="$id3_album"
    else
        sort_album="$dir_title"
    fi
    # echo "  Sort album: $sort_album"

    # Artist:
    if [ -n "$id3_albumartist" ] && [ -n "$id3_artist" ] && [ "$id3_albumartist" != "$id3_artist" ]; then
        # Artist and Album Artist are different, use Album Artist for both and Artist for narrator
        artist="$id3_albumartist"
        albumartist="$id3_albumartist"
        narrator="$id3_artist"
    elif [ -n "$id3_albumartist" ] && [ -z "$id3_artist" ]; then
        # Only Album Artist is set, using it for both
        artist="$id3_albumartist"
        albumartist="$id3_albumartist"
    elif [ -n "$id3_artist" ] && [ -z "$id3_albumartist" ]; then
        # Only Artist is set, using it for both
        artist="$id3_artist"
        albumartist="$id3_artist"
    elif [ -n "$id3_albumartist" ]; then
        # Album Artist is set, prefer it
        artist="$id3_albumartist"
        albumartist="$id3_albumartist"
    elif [ -n "$id3_artist" ]; then
        # Album Artist is not set, use Artist
        artist="$id3_artist"
        albumartist="$id3_artist"
    else
        # Neither Artist nor Album Artist is set, use Author for both
        artist="$dir_author"
        albumartist="$dir_author"
    fi

    # Narrator
    if [ -z "$narrator" ]; then
        narrator="$dir_narrator"
    fi
    # Swap first and last names if a comma is present
    artist=$(swap_first_last "$artist")
    author=$artist
    albumartist=$(swap_first_last "$albumartist")
    narrator=$(swap_first_last "$narrator")

    echo "- Author: $artist"
    # echo "  Album artist: $albumartist"
    echo "- Narrator: $narrator"

    # Date:
    if [ -n "$id3_date" ] && [ -z "$dir_year" ]; then
        date="$id3_date"
    elif [ -n "$dir_year" ] && [ -z "$id3_date" ]; then
        date="$dir_year"
    elif [ -n "$id3_date" ] && [ -n "$dir_year" ]; then
        if [ "$id3_year" -lt "$dir_year" ]; then
            date="$id3_date"
        else
            date="$dir_year"
        fi
    fi
    echo "- Date: $date"
    # extract 4 digits from date
    year=$(echo "$date" | grep -Eo '[0-9]{4}')
    
    # Comment:
    #      - Use this for the narrator, in the format "Narrated by <narrator>"
    #      - If narrator is unknown, clear this field

    if [ -n "$narrator" ]; then
        comment="Narrated by $narrator"
    else
        comment=""
    fi

    # convert bitrate and sample rate to friendly to kbit/s, rounding to nearest tenths, e.g. 44.1 kHz
    bitrate_friendly="$(echo "$bitrate" | awk '{printf "%.0f", int($1/1000)}') kb/s"
    bitrate="$(echo "$bitrate" | awk '{printf "%.0f", int($1/1000)}')k"
    samplerate_friendly="$(echo "$samplerate" | awk '{printf "%.1f", $1/1000}') kHz"
    echo -e "- Quality: $bitrate_friendly @ $samplerate_friendly"

    # Description:
    #      - Write all extracted properties, and "Original folder name: <folder name>" to this field, e.g.
    #        Book title: <book title>
    #        Author: <author>
    #        Date: <date>
    #        Narrator: <narrator>
    #        Quality: <bitrate_friendly> @ <samplerate_friendly>
    #        Original folder name: <folder name>
    #      - this needs to be newline-separated (\n does not work, use $'\n' instead)
    
    # Save description to description.txt alongside the m4b file
    description_file="$inboxfolder$book/description.txt"

    # Get the total size of the audio files in dir
    audio_files_size=$(get_size "." "human")
    audio_files_length=$(get_duration "." "human")

    # Write the description to the file with newlines, ensure utf-8 encoding
    echo -e "Book title: $title\n\
Author: $author\n\
Date: $date\n\
Narrator: $narrator\n\
Quality: $bitrate_friendly @ $samplerate_friendly\n\
Original folder: $book\n\
Original file type: .$file_type\n\
Original size: $audio_files_size\n\
Original length: $audio_files_length" > "$description_file"

    # build m4b-tool command switches based on which properties are defined
    # --name[=NAME]                              $title
    # --sortname[=SORTNAME]                      $title
    # --album[=ALBUM]                            $title
    # --sortalbum[=SORTALBUM]                    $title
    # --artist[=ARTIST]                          $author
    # --sortartist[=SORTARTIST]                  $author
    # --genre[=GENRE]                            always Audiobook
    # --writer[=WRITER]                          $author
    # --albumartist[=ALBUMARTIST]                $author
    # --year[=YEAR]                              $year
    # --description[=DESCRIPTION]                $description
    # --comment[=COMMENT]                        $comment
    # --encoded-by[=ENCODED-BY]                  always PHNTM

    id3tags=""
                    
    if [ -n "$title" ]; then
        id3tags=" --name=\"$title\" --sortname=\"$title\" --album=\"$title\" --sortalbum=\"$title\""
    fi

    if [ -n "$author" ]; then
        id3tags="$id3tags --artist=\"$author\" --sortartist=\"$author\" --writer=\"$author\" --albumartist=\"$author\""
    fi

    if [ -n "$year" ]; then
        id3tags="$id3tags --year=\"$year\""
    fi

    if [ -n "$comment" ]; then
        id3tags="$id3tags --comment=\"$comment\""
    fi

    id3tags="$id3tags --encoded-by=\"PHNTM\" --genre=\"Audiobook\""
}

# Set move to "done" folder or delete from inbox when done by ENV ON_COMPLETE=move|delete
on_complete="${ON_COMPLETE:-"move"}"

# Set debug mode by ENV DEBUG=Y
debug="${DEBUG:-"N"}"
debug_switch=$( [ "$debug" = "Y" ] && echo "--debug" || echo "-q" )

# Adjust the number of cores depending on the ENV CPU_CORES
CPUcores=$( [ -z "$CPU_CORES" ] && nproc --all || echo "$CPU_CORES" )
config="$CPUcores CPU cores /"

# Adjust the interval of the runs depending on the ENV SLEEPTIME
sleeptime=$( [ -z "$SLEEPTIME" ] && echo "$DEFAULT_SLEEP_TIME" || echo "$SLEEPTIME" )
config="$config $sleeptime sleep /"

# Adjust the max chapter length depending on MAX_CHAPTER_LENGTH
maxchapterlength=$( ([ -z "$MAX_CHAPTER_LENGTH" ] && echo "15,30" || echo "$MAX_CHAPTER_LENGTH") )
maxchapterlength_friendly=$(echo "$maxchapterlength" | sed 's/,/-/g;s/$/m/')
maxchapterlength=$( echo "$maxchapterlength" | awk -F, '{print $1*60","$2*60}' )
config="$config Max chapter length: $maxchapterlength_friendly /"

# If SKIP_COVERS is set to Y, skip the cover image; default is N
[ "$SKIP_COVERS" = "Y" ] && skipcoverimage=" --no-cover-image" || skipcoverimage=""
config="$config Cover images: "$( [ "$SKIP_COVERS" = "Y" ] && echo "off" || echo "on" )

# Check if "VERSION" is set to "latest" or "stable" and set the m4b-tool version accordingly
if [ "$VERSION" = "latest" ]; then
    m4btool="m4b-tool-pre"
    config="$config / m4b-tool latest (preview)"
else
    m4btool="m4b-tool"
    config="$config / m4b-tool stable"
fi

# continue until $m  5
while [ $m -ge 0 ]; do

    # -----------------------------------------------------------------------
    # Ready to start
    # -----------------------------------------------------------------------
    
    cd_inbox_folder

    # Check if there are audio files in the inbox folder. If none, sleep and exit
    if [ -z "$(find . -maxdepth 2 -type f \( "${audio_exts[@]}" \) -print0)" ]; then
        sleep $sleeptime
        exit 0
    fi

    current_local_time=$(date +"%Y-%m-%d %H:%M:%S")
    echo -e "--------------------------auto-m4b $current_local_time--------------------------"
    echo "$config"

    # Remove fix folder if there are no non-hidden files in it (check recursively)
    if [ -d "$fixitfolder" ] && [ -z "$(find "$fixitfolder" -not -path '*/\.*' -type f)" ]; then
        echo "Removing fix folder, it is empty..."
        rmdir_force "$fixitfolder" "false"
    fi

    # Pre-clean working folders
    clean_workdir "$mergefolder"
    clean_workdir "$buildfolder"
    clean_workdir "$binfolder"
    
    #for each folder, check if current user has write access to each folder and exit if not
    for folder in "$mergefolder" "$outputfolder" "$inboxfolder" "$backupfolder" "$binfolder" "$buildfolder" "$donefolder"; do
        ensure_dir_exists_and_is_writable "$folder"
    done

    echo "Checking for new books in \"$inboxfolder\""

    # Check if there are any directories modified in the last minute
    unfinished_dirs=$(find . -maxdepth 1 -type d -mmin -1)

    # Move single audio files into their own folders
    find . -maxdepth 1 -type f \( "${audio_exts[@]}" \) -print0 | while IFS= read -r -d $'\0' audio_file; do
        # Extract base name without extension
        file_name=$(basename "$audio_file")
        base_name=$(rm_audio_ext "$file_name")
        ext=$(get_ext "$file_name")
        target_dir="$base_name"
        unique_target="$target_dir/$file_name"

        # If the file is an m4b, we can send it straight to the output folder.
        # if a file of the same name exists, rename the incoming file to prevent data loss using (copy), (copy 1), (copy 2) etc.
        if [ "$ext" == "m4b" ]; then
            echo "Moving \"$audio_file\" to completed folder, it is already an m4b..."
            target_dir="$outputfolder"
            unique_target="$target_dir/$file_name"
        else
            echo "Moving \"$audio_file\" into its own folder..."
            mkdir -p "$target_dir"
        fi

        if [ -f "$unique_target" ]; then
            echo "(A file with the same name already exists in \"./$target_dir\", renaming the incoming file to prevent data loss)"

            # using a loop, first try to rename the file to append (copy) to the end of the file name.
            # if that fails, try (copy 1), (copy 2) etc. until it succeeds
            i=0
            # first try to rename to (copy)
            unique_target="$target_dir/$base_name (copy).$ext"
            while [ -f "$unique_target" ]; do
                i=$((i+1))
                unique_target="$target_dir/$base_name (copy $i).$ext"
            done
        fi

        mv_file_to_dir "$audio_file" "$target_dir"
               
        # Check that the file was moved successfully by checking that the file exists in the new directory
        # and does not exist in the inbox folder
        if [ -f "$unique_target" ]; then
            echo "Successfully moved to \"$unique_target\""
        else
            echo "Error moving to \"$unique_target\""
        fi
    done
    
    # Find folders with 3+ levels deep and move to fix that contain audio files
    find . -mindepth 3 -maxdepth 3 -type f \( "${audio_exts[@]}" \) -print0 | while IFS= read -r -d $'\0' nested; do
        echo "Moving \"$nested\" to fix folder - the file order cannot be determined because it has nested subfolders..."
        ensure_dir_exists_and_is_writable "$fixitfolder"
        mv_dir "$nested" "$fixitfolder"
    done

    # Find directories containing audio files, handling single quote if present
    audio_dirs=$(find . -type f \( "${audio_exts[@]}" \) -exec dirname {} + | sort | uniq)

    # If no books to convert, echo, sleep, and exit
    if [ -z "$audio_dirs" ]; then
        echo "No books to convert, next check in $sleeptime"
        sleep $sleeptime
        exit 0
    fi

    books_count=$(echo "$audio_dirs" | wc -l)

    echo -e "Found $(echo "$books_count") book(s) to convert"
    
    echo "$audio_dirs" | while IFS= read -r book_rel_path; do

        # get basename of book
        book=$(basename "$book_rel_path")

        draw_line

        # check if the current dir was modified in the last 30s and skip if so
        if [ "$(find "$book_rel_path" -maxdepth 0 -mmin -0.5)" ]; then
            echo "Skipping \"$book_rel_path\", it was recently updated and may still be copying"
            continue
        fi
        
        echo -e "\nPreparing to convert \"$book\""

        # check if book is a set of mp3 files that need to be converted to m4b
        mp3_count=$(find "$book_rel_path" -type f -name '*.mp3' | wc -l)
        m4a_count=$(find "$book_rel_path" -type f -name '*.m4a' | wc -l)
        m4b_count=$(find "$book_rel_path" -type f -name '*.m4b' | wc -l)
        wma_count=$(find "$book_rel_path" -type f -name '*.wma' | wc -l)

        is_mp3=$( [ "$mp3_count" -gt 0 ] && echo "TRUE" || echo "FALSE" )
        is_m4a=$( [ "$m4a_count" -gt 0 ] && echo "TRUE" || echo "FALSE" )
        is_m4b=$( [ "$m4b_count" -gt 0 ] && echo "TRUE" || echo "FALSE" )
        is_wma=$( [ "$wma_count" -gt 0 ] && echo "TRUE" || echo "FALSE" )

        # get full path of book (remove leading ./ if relative path)
        book_full_path=$inboxfolder$(echo "$book_rel_path" | sed 's/^\.\///')
        
        if [ "$is_m4b" == "TRUE" ]; then
            file_type="m4b"
        elif [ "$is_m4a" == "TRUE" ]; then
            file_type="m4a"
        elif [ "$is_mp3" == "TRUE" ]; then
            file_type="mp3"
        elif [ "$is_wma" == "TRUE" ]; then
            file_type="wma"
        else
            echo " *** Error: \"$book_full_path\""
            echo "     This folder does not contain any known audio files, skipping..."
            continue
        fi

        # Count the number of audio files in the book folder and get a human readable filesize
        audio_files_count=$(find "$book_full_path" -type f \( "${audio_exts[@]}" \) | wc -l)
        audio_files_size=$(get_size "$book_full_path" "human")

        echo ""
        echo "- Path: $book_full_path"
        echo "- Audio files: $audio_files_count"
        echo "- Total size: $audio_files_size"
        echo "- File type: .$file_type"
        echo ""

        # Check if a copy of this book is in fixitfolder and bail
        if [ -d "$fixitfolder$book" ]; then
            echo " *** Error: A copy of this book is in the "fix" folder, please fix it and try again."
            continue
        fi

        # Check if a copy of this book is in the done folder and bail
        # if [ -d "$donefolder$book" ]; then
        #     echo "Found a copy of this book in \"$donefolder\", it has probably already been converted"
        #     echo "Skipping this book"
        #     continue
        # fi
        
        # Copy files to backup destination        
        if [ "$MAKE_BACKUP" == "N" ]; then
            echo "Skipping making a backup"
        elif [ -z "$(ls -A "$book_full_path")" ]; then
            echo "Skipping making a backup (folder is empty)"
        else
            echo "Making a backup copy in \"$backupfolder\"..."
            cp_dir "$book_full_path" "$backupfolder"

            # Check that files count and folder size match
            orig_files_count=$(find "$book_full_path" -type f \( "${audio_exts[@]}" \) | wc -l)
            orig_files_size=$(get_size "$book_full_path" "human")
            orig_bytes=$(get_size "$book_full_path" "bytes")

            backup_files_count=$(find "$backupfolder$book" -type f \( "${audio_exts[@]}" \) | wc -l)
            backup_files_size=$(get_size "$backupfolder$book" "human")
            backup_bytes=$(get_size "$backupfolder$book" "bytes")

            if [ "$orig_files_count" == "$backup_files_count" ] && [ "$orig_files_size" == "$backup_files_size" ]; then
                echo "Backup successful - $backup_files_count files ($backup_files_size)"
            elif [ "$orig_files_count" -le "$backup_files_count" ] && [ "$orig_bytes" -le "$backup_bytes" ]; then
                echo "Backup successful - but expected $orig_files_count files ($orig_files_size), found $backup_files_count files ($backup_files_size)"
                echo "Assuming this is a previous backup and continuing"
            else
                echo "Backup failed - expected $orig_files_count files ($orig_files_size), found $backup_files_count files ($backup_files_size)"
                echo "Skipping this book"
                continue
            fi
        fi

        
        extract_folder_info "$book"

        # Set up destination paths
        build_m4bfile="$buildfolder$book/$book.m4b"
        final_m4bfile="$outputfolder$book/$book.m4b"
        logfile="./m4b-tool.log"

        cd_inbox_folder "$book"

        extract_metadata

        # if output file already exists, check if OVERWRITE_EXISTING is set to Y; if so, overwrite, if not, exit with error
        if [ -f "$final_m4bfile" ]; then
            if [ "$OVERWRITE_EXISTING" == "N" ] && [ -s "$final_m4bfile" ]; then
                echo -e "\n *** Error: Output file already exists and OVERWRITE_EXISTING is N, skipping \"$book\""
                continue
            else
                echo -e "\n *** Warning: Output file already exists, it and any similar .m4b files will be overwritten"
                # delete all m4b files in output folder that have $book as a substring, and echo " *** Deleted {file}"
                find "$outputfolder" -maxdepth 1 -type f -name "*$book*.m4b" -print0 | while IFS= read -r -d $'\0' m4b_file; do
                    echo " *** Deleted \"$m4b_file\""
                    rm "$m4b_file"
                done
                sleep 2
            fi
        fi

        # Move from inbox to merge folder
        echo -e "\nAdding files to queue & building \"$book.m4b\"..."
        cp_dir "$book_full_path" "$mergefolder"

        cd_merge_folder "$book"

        # Pre-create tempdir for m4b-tool in "$buildfolder$book-tmpfiles" and ensure writable

        clean_workdir "$buildfolder$book"
        clean_workdir "$buildfolder$book/$book-tmpfiles"       

        # Remove any existing log file
        rm -f "$logfile"
        
        starttime=$(date +%s)
        starttime_friendly=$(date +"%Y-%m-%d %H:%M:%S")

        if [ "$is_mp3" = "TRUE" ] || [ "$is_wma" = "TRUE" ]; then

            echo -e "Starting $file_type ➜ m4b conversion [$starttime_friendly]..."

            $m4btool merge . -n $debug_switch --audio-bitrate="$bitrate" --audio-samplerate="$samplerate"$skipcoverimage --use-filenames-as-chapters --no-chapter-reindexing --max-chapter-length="$maxchapterlength" --audio-codec=libfdk_aac --jobs="$CPUcores" --output-file="$build_m4bfile" --logfile="$logfile" "$id3tags" >$logfile 2>&1
            
        elif [ "$is_m4a" = "TRUE" ] || [ "$is_m4b" = "TRUE" ]; then

            echo -e "Starting merge/passthrough ➜ m4b [$starttime_friendly]..."

            # Merge the files directly as chapters (use chapters.txt if it exists) instead of converting
            # Get existing chapters from file    
            chapters=$(ls ./*chapters.txt 2> /dev/null | wc -l)
            chaptersfile=$(ls ./*chapters.txt 2> /dev/null | head -n 1)
            chaptersopt=$([ "$chapters" != "0" ] && echo "--chapters-file=\"$chaptersfile\"" || echo ""])
            chapters_switch=$([ "$chapters" == "0" ] && echo "--use-filenames-as-chapters --no-chapter-reindexing" || echo ""])

            if [ "$chapters" != "0" ]; then
                echo Setting chapters from chapters.txt file...
            fi
            $m4btool merge . -n $debug_switch $chapters_switch --audio-codec=copy --jobs="$CPUcores" --output-file="$build_m4bfile" --logfile="$logfile" "$chaptersopt" >$logfile 2>&1
        fi

        # echo " *** Error: [TEST] m4b-tool failed to convert \"$book\""
        # echo "     Moving \"$book\" to fix folder..."
        # mv_dir "$mergefolder$book" "$fixitfolder"
        # cp "$logfile" "$fixitfolder$book/m4b-tool.$book.log"
        # log_results "$book_full_path" "FAILED" ""
        # break

        # Check m4b-tool.log in output dir for "ERROR" in caps; if found, exit with error
        if grep -q -i "ERROR" "$logfile"; then

            # ignorable errors:
            ###################
            # an error occured, that has not been caught:
            # Array
            # (
            #     [type] => 8192
            #     [message] => Implicit conversion from float 9082109.64 to int loses precision
            #     [file] => phar:///usr/local/bin/m4b-tool/src/library/M4bTool/Parser/SilenceParser.php
            #     [line] => 61
            # )
            ###################
            # regex: an error occured[\s\S]*?Array[\s\S]*?Implicit conversion from float[\s\S]*?\)
            ###################
            # store the full text of the error in a variable

            ignorable_errors=( 
                "Failed to save key" 
                "Implicit conversion from float" 
            )

            found_ignorable_error=""
            for ignorable_error in "${ignorable_errors[@]}"; do
                found_ignorable_error=$(grep -i -Pzo "an error occured[\s\S]*?$ignorable_error[\s\S]*?\)" "$logfile")
                if [ -n "$found_ignorable_error" ]; then
                    break
                fi
            done

            # Also ignore if the line complains about ffmpeg version mismatch
            if [ -z "$found_ignorable_error" ]; then
                found_ignorable_error=$(grep -i -Pzo "ffmpeg version .* or higher is .* likely to cause errors" "$logfile")
            fi

            # if no ignorable errors are in log, throw error
            if [ -z "$found_ignorable_error" ]; then
                # get the line from the log file that contains "ERROR"
                error_line=$(grep -i "ERROR" "$logfile" | head -n 1)
                echo " *** Error: m4b-tool found an error in the log when converting \"$book\""
                echo "     Message: $error_line"
                echo -e "\nMoving \"$book\" to fix folder..."
                
                if [ "$(ensure_dir_exists_and_is_writable "$fixitfolder" "false")" != "1" ]; then
                    mv_dir "$mergefolder$book" "$fixitfolder"

                    # move every file from $inboxfolder$book to $fixitfolder$book but do not overwrite
                    mv -v -n "$inboxfolder$book/"* "$fixitfolder$book" 2>/dev/null

                    # delete files from $inboxfolder$book if they also exist in $fixitfolder$book
                    find "$inboxfolder$book" -maxdepth 1 -type f -exec basename {} \; | while IFS= read -r file; do
                        if [ -f "$fixitfolder$book/$file" ]; then
                            rm "$inboxfolder$book/$file"
                        fi
                    done

                    # remove inbox folder if it is empty
                    if ! rmdir "$inboxfolder$book" 2>/dev/null; then
                        echo " *** Warning: Some files from \"$inboxfolder$book\" couldn't be moved"
                    fi

                    cp "$logfile" "$fixitfolder$book/m4b-tool.$book.log"
                    log_results "$book_full_path" "FAILED" ""
                    continue
                fi
                echo "     See \"$logfile\" for details"
            fi
        fi

        # Make sure the m4b file was created
        if [ ! -f "$build_m4bfile" ]; then
            echo " *** Error: m4b-tool failed to convert \"$book\", no output file was found"
            echo "     Moving \"$book\" to fix folder..."
            if [ "$(ensure_dir_exists_and_is_writable "$fixitfolder" "false")" != "1" ]; then
                mv_dir "$mergefolder$book" "$fixitfolder"
                cp "$logfile" "$fixitfolder$book/m4b-tool.$book.log"
                log_results "$book_full_path" "FAILED" ""
            fi
            continue
        fi

        # create outputfolder
        mkdir -p "$outputfolder$book" 2>/dev/null

        # Copy log file to output folder as $buildfolder$book/m4b-tool.$book.log
        mv "$logfile" "$book.m4b-tool.log"

        # Remove reserved filesystem chars from "$bitrate_friendly @ $samplerate_friendly" (replace kb/s with kbps)
        desc_quality=$(echo "$bitrate_friendly @ $samplerate_friendly" | sed 's/kb\/s/kbps/g')

        # Get size of new m4b file and append to description.txt file
        m4b_file_size=$(get_size "$build_m4bfile" "human")
        echo -e "Converted size: $m4b_file_size" >> "$description_file"

        m4b_audio_lenth=$(get_duration "$build_m4bfile" "human")
        echo -e "Converted length: $m4b_audio_lenth" >> "$description_file"

        # Rename description.txt to $book-[$desc_quality].txt
        mv "$description_file" "$book [$desc_quality].txt"

        # Move all built audio files to output folder
        find "$buildfolder$book" -maxdepth 1 -type f \( "${audio_exts[@]}" \) -exec mv {} "$outputfolder$book/" \;
        # Copy other jpg, png, and txt files to output folder
        find "$mergefolder$book" -maxdepth 1 -type f \( "${other_exts[@]}" \) -exec mv {} "$outputfolder$book/" \;
        find "$buildfolder$book" -maxdepth 1 -type f \( "${other_exts[@]}" \) -exec mv {} "$outputfolder$book/" \;

        # Remove description.txt from output folder if "$book [$desc_quality].txt" exists
        if [ -f "$outputfolder$book/$book [$desc_quality].txt" ]; then
            rm "$outputfolder$book/description.txt"
        else # otherwise, warn that the description.txt file is missing
            echo " *** Notice: The description.txt is missing (reason unknown)"
        fi

        elapsedtime=$(($(date +%s) - $starttime))
        elapsedtime_friendly=$(human_elapsed_time "$elapsedtime")

        
        echo "Finished in $elapsedtime_friendly"
        log_results "$book_full_path" "SUCCESS" "$elapsedtime_friendly"

        echo "Moving to \"$final_m4bfile\"..."
        mv_dir "$mergefolder$book" "$binfolder"
        
        if [ "$on_complete" = "move" ]; then
            echo "Archiving original..."
            mv_dir "$inboxfolder$book" "$donefolder"
        elif [ "$on_complete" = "delete" ]; then
            echo "Deleting original..."
            rm -rf "$inboxfolder$book"
        fi

        # Check if for some reason this is still in the inbox and warn
        if [ -d "$inboxfolder$book" ]; then
            echo " *** Warning: \"$book\" is still in the inbox folder, it should have been archived or deleted"
            echo "     To prevent this book from being converted again, move it out of the inbox folder"
        fi
        
        echo -e "\nDone processing \"$book\""

        # cd back to inbox folder
        cd_inbox_folder
    done
        
    # clear the folders
    echo -e "\nCleaning up temp folders..."
    rm -r "$binfolder"* 2>/dev/null
    rm -r "$mergefolder"* 2>/dev/null
    rm -r "$buildfolder"* 2>/dev/null
    # Delete -tmpfiles dir
    rm -rf "$outputfolder$book/$book-tmpfiles" 2>/dev/null

    echo -e "Finished converting all books, next check in $sleeptime\n"
	
    sleep $sleeptime
    exit 0 # uncomment here to have script restart after each run
done
