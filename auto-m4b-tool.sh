#!/bin/bash

add_trailing_slash() {
    # adds a trailing slash to path if it is an existing dir and path is missing /
    local path="$1"
    if [ -d "$path" ] && [[ ! "$path" == */ ]]; then
        path="$path/"
    fi
    echo "$path"
}

rm_trailing_slash() {
    # removes a trailing slash from path if it is an existing dir and path has /
    local path="$1"
    if [ -d "$path" ] && [[ "$path" == */ ]]; then
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

echo -e "\n------------------------------------auto-m4b------------------------------------"

# set m to 1
m=1

#variable defenition
inboxfolder="${INBOX_FOLDER:-"/volume1/Downloads/#done/#books/#convert/inbox/"}"
outputfolder="${OUTPUT_FOLDER:-"/volume1/Downloads/#done/#books/#convert/completed/"}"
fixitfolder="${FIXIT_FOLDER:-"/volume1/Downloads/#done/#books/#convert/fix/"}"
buildfolder="${BUILD_FOLDER:-"/volume1/Downloads/#done/#books/#convert/#tmp/building/"}"
mergefolder="${MERGE_FOLDER:-"/volume1/Downloads/#done/#books/#convert/#tmp/merge/"}"
backupfolder="${BACKUP_FOLDER:-"/volume1/Downloads/#done/#books/#convert/#tmp/backup/"}"
binfolder="${BIN_FOLDER:-"/volume1/Downloads/#done/#books/#convert/#tmp/delete/"}"
audio_exts=( -name '*.mp3' -o -name '*.m4a' -o -name '*.m4b' )
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
)

#ensure the expected folder-structure
mkdir -p "$mergefolder"
mkdir -p "$outputfolder"
mkdir -p "$inboxfolder"
mkdir -p "$fixitfolder"
mkdir -p "$backupfolder"
mkdir -p "$buildfolder"
mkdir -p "$binfolder"

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

#for each folder, check if current user has write access to each folder and exit if not
for folder in "$mergefolder" "$outputfolder" "$inboxfolder" "$fixitfolder" "$backupfolder" "$binfolder" "$buildfolder"; do
	if [ ! -w "$folder" ]; then
		echo "Error: $folder is not writable by current user. Please fix permissions and try again."
        sleep 30
		exit 1
	fi
done

# Adjust the number of cores depending on the ENV CPU_CORES
CPUcores=$( [ -z "$CPU_CORES" ] && nproc --all || echo "$CPU_CORES" )
config="$CPUcores CPU cores /"

# Adjust the interval of the runs depending on the ENV SLEEPTIME
sleeptime=$( [ -z "$SLEEPTIME" ] && echo "30s" || echo "$SLEEPTIME" )
config="$config $sleeptime sleep /"

# Adjust the max chapter length depending on MAX_CHAPTER_LENGTH
maxchapterlength=$( ([ -z "$MAX_CHAPTER_LENGTH" ] && echo "15,30" || echo "$MAX_CHAPTER_LENGTH") )
maxchapterlength_friendly=$(echo "$maxchapterlength" | sed 's/,/-/g;s/$/m/')
maxchapterlength=$( echo "$maxchapterlength" | awk -F, '{print $1*60","$2*60}' )
config="$config Max chapter length: $maxchapterlength_friendly /"

# If SKIP_COVERS is set to Y, skip the cover image; default is N
[ "$SKIP_COVERS" = "Y" ] && skipcoverimage=" --no-cover-image" || skipcoverimage=""
config="$config Cover images "$( [ "$SKIP_COVERS" = "Y" ] && echo "off" || echo "on" )"/"

echo "$config"

# continue until $m  5
while [ $m -ge 0 ]; do
    
    cd_inbox_folder

    current_local_time=$(date +"%Y-%m-%d %H:%M:%S")
    echo -e "------------------------------$current_local_time-------------------------------"

    echo "Checking for new books in \"$inboxfolder\""

    # Move single audio files into their own folders
    # Loop through audio files one-level deep
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

        mv "$audio_file" "$unique_target"
               
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
        echo "Moving \"$nested\" to fix folder, it has nested subfolders..."
        mv "$nested" "$fixitfolder"
    done

    # Find directories containing a single m4b audio file and move them to the output folder
    # find . -maxdepth 1 -type d -exec sh -c 'set -- "$1"/*m4b; [ -f "$1" ] && [ $# -eq 1 ]' sh {} \; -print0 | while IFS= read -r -d $'\0' m4b_dir; do
    #     m4b_basename=$(basename "$m4b_dir")
    #     echo "Moving \"$m4b_dir\" to \"$outputfolder\"..."
    #     mv "$m4b_dir" "$outputfolder"
    # done

    # Find directories containing audio files (mp3, m4a, m4b)
    audio_dirs=$(find . -type f \( "${audio_exts[@]}" \) -exec dirname {} \; | sort | uniq)

    # Extract the base names of the directories
    books=$(echo "$audio_dirs" | xargs -I {} basename {})

    # If no books to convert, echo, sleep, and exit
    if [ -z "$books" ]; then
        echo "No books to convert, next run in $sleeptime"
        sleep $sleeptime
        exit 0
    fi

    books_count=$(echo "$books" | wc -l)

    echo -e "Found $(echo "$books_count") book(s) to convert"
    
    echo "$audio_dirs" | while IFS= read -r book_rel_path; do

         # check if book is a set of mp3 files that need to be converted to m4b
        is_mp3=$(find "$book_rel_path" -type f -name '*.mp3' | wc -l)
        is_m4a=$(find "$book_rel_path" -type f -name '*.m4a' | wc -l)
        is_m4b=$(find "$book_rel_path" -type f -name '*.m4b' | wc -l)
        
        # get full path of book (remove leading ./ if relative path)
        book_full_path=$inboxfolder$(echo "$book_rel_path" | sed 's/^\.\///')
        
        # get basename of book
        book=$(echo "$book_rel_path" | xargs -I {} basename {})

        draw_line

        echo -e "\nPreparing to convert [$book]"

        # Count the number of audio files in the book folder and get a human readable filesize
        audio_files_count=$(find "$book_full_path" -type f \( "${audio_exts[@]}" \) | wc -l)
        audio_files_size=$(du -sh "$book_full_path" | awk '{print $1}')

        echo ""
        echo "- Path: $book_full_path"
        echo "- Audio files: $audio_files_count"
        echo "- Total size: $audio_files_size"
        echo "- File type: ."$( [ "$is_mp3" -gt 0 ] && echo "mp3" || [ "$is_m4a" -gt 0 ] && echo "m4a" || echo "m4b" )
        echo ""
        
        # Copy files to backup destination        
        if [ "$MAKE_BACKUP" == "N" ]; then
            echo "Skipping making a backup"
        elif [ -z "$(ls -A "$book_full_path")" ]; then
            echo "Skipping making a backup (folder is empty)"
        else
            echo "Making a backup copy in \"$backupfolder\"..."
            backupfolder_no_slash=$(rm_trailing_slash "$backupfolder")
            cp -rf "$book" "$backupfolder_no_slash"
            if [ $? -eq 0 ]; then
                echo "Backup successful"
            else
                echo "Backup failed"
                exit 1
            fi
        fi
        
        extract_folder_info "$book"

        # Set up destination paths
        out_m4bfile="$buildfolder$book/$book.m4b"
        out_chaptersfile="$buildfolder$book/$book.chapters.txt"
        logfile="./m4b-tool.log"

        
        cd_inbox_folder "$book"

        if [ "$is_mp3" -gt 0 ]; then

            sample_audio=$(find . -maxdepth 1 -type f \( "${audio_exts[@]}" \) | head -n 1)

            echo -e "\nSampling \"$(rm_leading_dot_slash "$sample_audio")\" for id3 tags and quality information..."

            # Move book to merge folder and cd to merge folder
            # echo "Moving \"$book\" to merge folder..."
            # mv "$book_full_path" "$mergefolder"
            # cd_merge_folder

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

            # Set variables based on the extracted information, if it is set.
            # Rules (for each property):
            #   1. If id3 tag is not set, use the extracted information
            #   2. If id3 tag is set, check if it matches (case insensitive) the extracted information
            #   3. If it matches, use the id3 tag
            #   4. If it doesn't match, but there is extracted info, use the extracted info
            #   5. If it doesn't match and there is no extracted info, use the id3 tag
            #   6. If there is no extracted info and no id3 tag, use the full folder name

            # Specific rules by property (all case-insensitive):

            # Title:
            #   - If title *contains* the values from album or sort album, use the title
            #   - If it does not, but there is an album or sort album, use album first, then sort album as title
            #   - If there is no album or sort album, use the extracted title

            if [ -z "$id3_title" ] && [ -z "$id3_album" ] && [ -z "$id3_sortalbum" ]; then
                # If no id3_title, id3_album, or id3_sortalbum, use the extracted title
                title="$dir_title"
            else
                # If album or sort album is in title, use title
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
            #   - If id3_album exists, use it
            #   - If not, use id3_sortalbum
            #   - If neither exists, use the extracted title

            if [ -n "$id3_album" ]; then
                album="$id3_album"
            elif [ -n "$id3_sortalbum" ]; then
                album="$id3_sortalbum"
            else
                album="$dir_title"
            fi
            echo "- Album: $album"

            # Sort Album:
            #   - If id3_sortalbum exists, use it
            #   - If not, use id3_album
            #   - If neither exists, use the extracted title

            if [ -n "$id3_sortalbum" ]; then
                sort_album="$id3_sortalbum"
            elif [ -n "$id3_album" ]; then
                sort_album="$id3_album"
            else
                sort_album="$dir_title"
            fi
            # echo "  Sort album: $sort_album"

            # Artist and Album Artist logic:
            #   - If both id3_albumartist and id3_artist exist and are not the same: artist=id3_albumartist, albumartist=id3_albumartist, narrator=id3_artist
            #   - If no id3_artist and id3_albumartist exists: artist=id3_albumartist, albumartist=id3_albumartist
            #   - If id3_artist exists and no id3_albumartist: artist=id3_artist, albumartist=id3_artist
            #   - If neither id3_artist nor id3_albumartist exist: artist=dir_author, albumartist=dir_author

            if [ -n "$id3_albumartist" ] && [ -n "$id3_artist" ] && [ "$id3_albumartist" != "$id3_artist" ]; then
                artist="$id3_albumartist"
                albumartist="$id3_albumartist"
                narrator="$id3_artist"
            elif [ -n "$id3_albumartist" ] && [ -z "$id3_artist" ]; then
                artist="$id3_albumartist"
                albumartist="$id3_albumartist"
            elif [ -n "$id3_artist" ] && [ -z "$id3_albumartist" ]; then
                artist="$id3_artist"
                albumartist="$id3_artist"
            else
                artist="$dir_author"
                albumartist="$dir_author"
            fi

            # Narrator
            #      - If has not yet been defined, use dir_narrator or leave blank
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
            #   - If id3_date exists and dir_year does not, use id3_date
            #   - If dir_year exists and id3_date does not, use dir_year
            #   - If both exist, compare the years and use the oldest
            #   - If neither exist, leave blank
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
            bitrate_prop="$(echo "$bitrate" | awk '{printf "%.0f", int($1/1000)}')k"
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

            # Write the description to the file with newlines, ensure utf-8 encoding
            echo -e "Book title: $title\nAuthor: $author\nDate: $date\nNarrator: $narrator\nQuality: $bitrate_friendly @ $samplerate_friendly\nOriginal folder: $book" > "$description_file"

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

            # if output file already exists, check if OVERWRITE_EXISTING is set to Y; if so, overwrite, if not, exit with error
            if [ -f "$out_m4bfile" ]; then
                if [ "$OVERWRITE_EXISTING" == "N" ] && [ -s "$out_m4bfile" ]; then
                    echo -e "\n *** Error: Output file already exists and OVERWRITE_EXISTING is N, skipping \"$book\""
                    break
                else
                    echo -e "\n *** Warning: Output file already exists, overwriting \"$book\""
                    # delete the existing completed folder
                    rm -rf "$buildfolder$book"
                    echo " *** Deleted \"$buildfolder$book\""
                    sleep 2
                fi
            fi
        fi

        # Move from inbox to merge folder
        echo -e "\nAdding files to queue & building:"
        cp "$book_full_path" "$mergefolder"

        cd_merge_folder "$book"
                            
        # Pre-create tempdir for m4b-tool in "$buildfolder$book-tmpfiles" and ensure writable
        mkdir -p "$buildfolder$book"
        # If "$buildfolder$book/$book-tmpfiles" exists, delete it and re-create it
        if [ -d "$buildfolder$book/$book-tmpfiles" ]; then
            rm -rf "$buildfolder$book/$book-tmpfiles"
        fi
        mkdir -p "$buildfolder$book/$book-tmpfiles"
        if [ ! -w "$buildfolder$book/$book-tmpfiles" ]; then
            echo " *** Error: \"$buildfolder$book/$book-tmpfiles\" is not writable by current user. Please fix permissions and try again."
            sleep 30
            exit 1
        fi

        # Remove any existing log file
        rm -f "$logfile"

        if [ "$is_mp3" -gt 0 ]; then

            echo "$buildfolder$book/{converted}.m4b"
            echo -e "\nStarting mp3 ➜ m4b conversion..."

            {
                m4b-tool merge . -n -q --audio-bitrate="$bitrate_prop" --audio-samplerate="$samplerate"$skipcoverimage --use-filenames-as-chapters --no-chapter-reindexing --max-chapter-length="$maxchapterlength" --audio-codec=libfdk_aac --jobs="$CPUcores" --output-file="$out_m4bfile" --logfile="$logfile""$id3tags"
            } || {
                echo " *** Error: m4b-tool failed to convert \"$book\""
                cp "$logfile" "$buildfolder$book/m4b-tool.$book.log"
                # move to fixitfolder for manual fixing
                mv "$mergefolder$book" "$fixitfolder"
                break
            }
            
        elif [ "$is_m4a" -gt 0 ] || [ "$is_m4b" -gt 0 ]; then

            echo "$buildfolder$book/{merged}.m4b"
            echo -e "\nStarting merge (passthrough ➜ m4b)..."

            # Merge the files directly as chapters (use chapters.txt if it exists) instead of converting
            # Get existing chapters from file    
            chapters=$(ls ./*chapters.txt 2> /dev/null | wc -l)
            chaptersfile=$(ls ./*chapters.txt 2> /dev/null | head -n 1)
            chaptersopt=$([ "$chapters" != "0" ] && echo "--chapters-file=\"$chaptersfile\"" || echo ""])

            if [ "$chapters" != "0" ]; then
                echo Setting chapters from chapters.txt file...
            fi
            m4b-tool merge . -n -q --use-filenames-as-chapters --no-chapter-reindexing --audio-codec=copy --jobs="$CPUcores" --output-file="$out_m4bfile" --logfile="$logfile" "$chaptersopt"
        fi

        # Check m4b-tool.log in output dir for "ERROR" in caps; if found, exit with error
        if grep -q -i "ERROR" "$logfile"; then
            echo " *** Error: m4b-tool failed to convert \"$book\""
            # move to fixitfolder for manual fixing
            cp "$logfile" "$buildfolder$book/m4b-tool.$book.log"
            cp -r "$mergefolder$book" "$fixitfolder"

            mv "$mergefolder$book" "$fixitfolder"
            break
        fi

        # Copy log file to output folder as $buildfolder$book/m4b-tool.$book.log
        cp "$logfile" "$buildfolder$book/m4b-tool.$book.log"

        # Copy other jpg, png, and txt files to output folder
        find . -maxdepth 1 -type f \( "${other_exts[@]}" \) -exec cp {} "$buildfolder$book/" \;

        # Move merge folder to bin folder
        mv "$mergefolder$book" "$binfolder"

        echo "Finished converting \"$book\""

        # Move the completed folder to the output folder
        mv "$buildfolder$book" "$outputfolder"

        # Remove the source in inboxfolder
        rm -rf "$inboxfolder$book"
    done
        
    # clear the folders
    echo -e "\nCleaning up temp folders..."
    rm -r "$binfolder"* 2>/dev/null
    rm -r "$mergefolder"* 2>/dev/null
    rm -r "$buildfolder"* 2>/dev/null
    # Delete -tmpfiles dir
    rm -rf "$outputfolder$book/$book-tmpfiles" 2>/dev/null

    echo "Finished converting all books, next run in $sleeptime"
	
    sleep $sleeptime
    exit 0 # uncomment here to have script restart after each run
done
