#!/bin/bash
DEFAULT_SLEEP_TIME=30s

# set m to 1
m=1

#variable defenition
inboxfolder="${INBOX_FOLDER:-"/volume1/Downloads/#done/#books/#convert/inbox/"}"
# outputfolder="${OUTPUT_FOLDER:-"/volume1/Downloads/#done/#books/#convert/converted/"}"
outputfolder="${OUTPUT_FOLDER:-"/volume1/Books/Audiobooks/_Updated plex copies/"}"
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
    -iname '*.mp3' 
    -o -iname '*.m4a' 
    -o -iname '*.m4b' 
    -o -iname '*.wma'
)

other_exts=(
    -iname '*.jpg'
    -o -iname '*.jpeg'
    -o -iname '*.png'
    -o -iname '*.gif'
    -o -iname '*.bmp'
    -o -iname '*.tiff'
    -o -iname '*.svg'
    -o -iname '*.epub'
    -o -iname '*.mobi'
    -o -iname '*.azw'
    -o -iname '*.pdf'
    -o -iname '*.txt'
    -o -iname '*.log'
)

hidden_files=(
    -iname '.DS_Store'
    -o -iname '._*'
    -o -iname '.AppleDouble'
    -o -iname '.LSOverride'
    -o -iname '.Spotlight-V100'
    -o -iname '.Trashes'
    -o -iname '__MACOSX'
    -o -iname 'ehthumbs.db'
    -o -iname 'Thumbs.db'
    -o -iname '@eaDir'
)

# -----------------------------------------------------------------------
# Printing and fancy colors
# -----------------------------------------------------------------------

# Initialize a variable to store the last output
__last_output=""
__last_line_was_empty=false
__last_line_was_alert=false
__last_line_ends_with_newline=false

line_is_empty() {
    # Check if the line is entirely whitespace
    if [ -z "$*" ] || [[ "$*" =~ ^\s*$ ]]; then
        echo "true"
    else
        echo "false"
    fi
}

line_ends_with_newline() {
    # Check if the line ends with a newline
    if [[ "$*" =~ \n$ ]]; then
        echo "true"
    else
        echo "false"
    fi
}

tint() {
    echo -ne "\033[38;5;${1}m${*:2}\033[m"
}

# Custom echo function that also stores the output
ecko() {
    local _this_line_is_empty=$(line_is_empty "$@")
    local _this_line_ends_with_newline=$(line_ends_with_newline "$@")
    local _color=""
    local _text="$*"

    if [ "$__last_line_was_empty" = true ] && [ "$_this_line_is_empty" = true ]; then
        return
    fi

    if [[ "$1" == "color:"* ]]; then
        _color="${1#color:}"
        _text="\033[38;5;${_color}m${*:2}\033[0m"
    fi

    if [ "$__last_line_was_alert" = true ] && [ "$_this_line_is_empty" = true ]; then
        echo -ne "$_text"
    elif [ "$__last_line_was_empty" = true ]; then
        echo -e "$(strip_leading_newlines "$_text")"
    else
        echo -e "$_text"
    fi

    __last_line_was_alert=false
    __last_line_was_empty=$_this_line_is_empty
    __last_line_ends_with_newline=$_this_line_ends_with_newline
}

print_underline() {
    ecko "\033[4m$1\033[0m"
}

__default="256"

__grey="242"
print_grey() {
    ecko "color:$__grey" "$@"
}

__dark_grey="237"
print_dark_grey() {
    ecko "color:$__dark_grey" "$@"
}

__light_grey="250"
print_light_grey() {
    ecko "color:$__light_grey" "$@"
}

__aqua="43"
print_aqua() {
    ecko "color:$__aqua" "$@"
}

__green="78"
print_green() {
    ecko "color:$__green" "$@"
}

__blue="33"
print_blue() {
    ecko "color:$__blue" "$@"
}

__purple="99"
print_purple() {
    ecko "color:$__purple" "$@"
}

__amber="214"
print_amber() {
    ecko "color:$__amber" "$@"
}

__orange="208"
__orange_accent="214"
print_orange() {
    ecko "color:$__orange" "$@"
}

__red="161"
__red_accent="204"
print_red() {
    ecko "color:$__red" "$@"
}

__pink="205"
print_pink() {
    ecko "color:$__pink" "$@"
}

print_list() {
    ecko "color:$__grey" "$@"
}

_print_alert() {
    local _color="$1"
    local _accent_color="${2:-"$_color"}"
    local _line="$3"

    _line=$(trim_newlines "$_line")
    
    if [ "$__last_line_was_empty" = true ] || [ "$__last_line_ends_with_newline" = true ] || [ "$__last_line_was_alert" = true ]; then
        _line=$(strip_leading_newlines " *** $_line")
    else
        _line="\n *** $_line"
    fi

    # Do a regex match on _line to see if it contains {{some text}}. If so, replace it with accent color
    # then reset color to _color after
    # do this for every instance of {{some text}}
    _line=$(echo "$_line" | perl -pe 's/\{\{(.*?)\}\}/\033[38;5;'"$_accent_color"'m$1\033[38;5;'"$_color"'m/g')

    if [ "$__last_line_was_alert" = true ]; then
        tint "$_color" "$_line\n"
    else
        ecko "color:$_color" "$_line\n"
    fi

    __last_line_was_alert=true
    __last_line_was_empty=false
}


print_error() {
    _print_alert $__red $__red_accent "$@"
}

print_warning() {
    _print_alert $__orange $__orange_accent "$@"
}

print_notice() {
    _print_alert $__light_grey $__default "$@"
}

tint_path() {
    tint $__purple "$@"
}

tint_aqua() {
    tint $__aqua "$@"
}

tint_amber() {
    tint $__amber "$@"
}

tint_light_grey() {
    tint $__light_grey "$@"
}

tint_warning() {
    tint $__orange "$@"
}

tint_warning_accent() {
    tint $__orange_accent "$@"
}

tint_error() {
    tint $__red "$@"
}

tint_error_accent() {
    tint $__red_accent "$@"
}

tinted_mp3() {
    if [ -z "$1" ]; then
        tint $__pink "mp3"
    else
        tint $__pink "$@"
    fi
}

tinted_m4b() {
    if [ -z "$1" ]; then
        tint_aqua "m4b"
    else
        tint_aqua "$@"
    fi
}

tinted_file() {

    # if there are 2+ args, and the first one is in the allowed list, use it
    local _known_file_types=( "mp3" "m4b" "m4a" "wma" )

    # if $1 matches any of the known file types or .{known-file-type}, set is_known_file_type to true
    local _is_known_file_type=false
    for file_type in "${_known_file_types[@]}"; do
        if [[ "$1" =~ $file_type ]]; then
            _is_known_file_type=true
            break
        fi
    done

    # line is $2 if it exists else $1
    local _line="${2:-"$1"}"

    if [ "$_is_known_file_type" = true ]; then
        if [[ "$1" =~ "mp3" ]]; then
            tinted_mp3 "$_line"
        elif [[ "$1" =~ "m4b" ]]; then
            tinted_m4b "$_line"
        elif [[ "$1" =~ "m4a" ]]; then
            tint $__blue "$_line"
        elif [[ "$1" =~ "wma" ]]; then
            tint $__amber "$_line"
        fi
    else
        # otherwise, use default
        tint $__default "$@"
    fi
}

divider() {
    print_dark_grey "$(printf '%.0s-' {1..80})"
}

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


# -----------------------------------------------------------------------
# Log startup notice
# -----------------------------------------------------------------------
# Create a file at /tmp/auto-m4b/started.txt with the current date and time if it does not exist
# If it does exist, ecko startup notice
# If it does, do nothing.

if [ ! -f "/tmp/auto-m4b/running" ]; then
    sleep 5
    mkdir -p "/tmp/auto-m4b/"
    touch "/tmp/auto-m4b/running"
    current_local_time=$(date +"%Y-%m-%d %H:%M:%S")
    echo "auto-m4b started at $current_local_time", watching "$inboxfolder" >> "/tmp/auto-m4b/running"
    print_aqua "\nStarting auto-m4b..."
    ecko "Watching $(tint_path "$inboxfolder") for books to convert ⌐◒-◒\n"
fi

swap_first_last() {
    local _name="$1"
    local _lastname=""
    local _givenname=""

    if echo "$_name" | grep -q ','; then
      _lastname=$(echo "$_name" | perl -n -e '/^(.*?), (.*?)$/ && print "$1"')
      _givenname=$(echo "$_name" | perl -n -e '/^(.*?), (.*?)$/ && print "$2"')
    else
      _lastname=$(echo "$_name" | perl -n -e '/^.*\s(\S+)$/ && print "$1"')
      _givenname=$(echo "$_name" | perl -n -e '/^(.*?)\s\S+$/ && print "$1"')
    fi

    # If there is a given name, swap the first and last name and return it
    if [ -n "$_givenname" ]; then
        echo "$_givenname $_lastname"
    else
        # Otherwise, return the original name
        echo "$_name"
    fi
}

author_pattern="^(.*?)[\W\s]*[-_–—\(]"
book_title_pattern="(?<=[-_–—])[\W\s]*(?<book_title>[\w\s]+?)\s*(?=\d{4}|\(|\[|$)"
year_pattern="(?P<year>\d{4})"
narrator_pattern="(?:read by|narrated by|narrator)\W+(?<narrator>(?:\w+(?:\s\w+\.?\s)?[\w-]+))(?:\W|$)"
extract_folder_info() {
    local _folder_name="$1"

    # Replace single occurrences of . with spaces
    _folder_name=$(echo "$_folder_name" | sed 's/\./ /g')

    local dir_author=$(echo "$_folder_name" | perl -n -e "/$author_pattern/ && print \$1")
    local dir_author=$(swap_first_last "$dir_author")

    local dir_author=$(echo "$givennames $lastname")
    local dir_title=$(echo "$_folder_name" | perl -n -e "/$book_title_pattern/ && print \$+{book_title}")
    local dir_year=$(echo "$_folder_name" | perl -n -e "/$year_pattern/ && print \$+{year}")
    local dir_narrator=$(echo "$_folder_name" | perl -n -e "/$narrator_pattern/i && print \$+{narrator}")

    local dir_extrajunk="$_folder_name"

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

pluralize() {
    local _count="$1"
    local _singular="$2"
    local _default_plural="${_singular}s"
    local _plural="${3:-"$_default_plural"}"

    if [ "$_count" -eq 1 ]; then
        echo "$_singular"
    elif [ "$_count" -gt 1 ] || [ "$_count" -eq 0 ]; then
        echo "$_plural"
    else
        echo "$_singular(s)"
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
        ecko "$(tint_path "$_dir") does not exist, creating it..."
        mkdir -p "$_dir"
    fi

    if [ ! -w "$_dir" ]; then
        if [ "$_exit_on_error" == "true" ]; then
            print_error "Error: {{$_dir}} is not writable by current user, please fix permissions and try again"
            exit 1
        else
            print_warning "Warning: {{$_dir}} is not writable by current user, this may result in data loss"
            return 1
        fi
    fi
}

cp_dir() {

    # Remove trailing slash from source and add trailing slash to destination
    local _source_dir=$(rm_trailing_slash "$1")
    local _dest_dir=$(add_trailing_slash "$2")

    # Check if both dirs exist, otherwise exit with error
    if [ ! -d "$_source_dir" ]; then
        print_error "Error: Source directory {{$_source_dir}} does not exist"
        exit 1
    fi

    if [ ! -d "$_dest_dir" ]; then
        print_error "Error: Destination directory {{$_dest_dir}} does not exist"
        exit 1
    fi

    # Make sure both paths are dirs
    if [ ! -d "$_source_dir" ]; then
        print_error "Error: Source {{$_source_dir}} is not a directory"
        exit 1
    fi

    if [ ! -d "$_dest_dir" ]; then
        print_error "Error: Destination {{$_dest_dir}} is not a directory"
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
        print_error "Error: Source file {{$_source_file}} does not exist"
        exit 1
    fi

    if [ ! -d "$_dest_dir" ]; then
        print_error "Error: Destination directory {{$_dest_dir}} does not exist"
        exit 1
    fi

    # Make sure destination path is a dir
    if [ ! -d "$_dest_dir" ]; then
        print_error "Error: Destination {{$_dest_dir}} is not a directory"
        exit 1
    fi

    cp -rf "$_source_file" "$_dest_dir"
}

join_paths() {
    local _path1=$(rm_trailing_slash "$1")
    local _path2=$(rm_leading_dot_slash "$2")
    echo "$_path1/$_path2"
}

get_total_dir_size() {
    # Takes a path and returns the total size of all files in the path
    # If no path is specified, uses current directory
    local _path="${1:-"."}"
    du -s "$_path" | awk '{print $1}'
}

ok_to_del() {
    local _path="$1"
    local _max_size="${2:-"10240"}"  # default to 10kb
    local _ignore_hidden="${3:-"true"}"  # default to true

    src_dir_size=$(get_total_dir_size "$_source_dir")
    if [ "$_ignore_hidden" = "true" ]; then
        files_count=$(ls "$_source_dir" | wc -l)
    else
        files_count=$(ls -A "$_source_dir" | wc -l)
    fi

    #ok to delete if no visible files or if size is less than 10kb
    [ "$files_count" -eq 0 ] || [ "$src_dir_size" -lt "$_max_size" ] && echo "true" || echo "false"
}

mv_dir() {

    # Remove trailing slash from source and add trailing slash to destination
    local _source_dir=$(rm_trailing_slash "$1")
    local _dest_dir=$(add_trailing_slash "$2")

    # valid overwrite modes are "skip" (default), "overwrite", and "overwrite-silent"
    local _overwrite_mode="${3:-"skip"}"

    # Create destination dir if it doesn't exist
    if [ ! -d "$_dest_dir" ]; then
        mkdir -p "$_dest_dir" >/dev/null 2>&1
    fi

    # Check if both dirs exist, otherwise exit with error
    if [ ! -d "$_source_dir" ]; then
        print_error "Error: Source directory $(tint_error "$_source_dir") does not exist"
        exit 1
    fi

    if [ ! -d "$_dest_dir" ]; then
        print_error "Error: Destination directory $(tint_error "$_dest_dir") does not exist"
        exit 1
    fi

    # Make sure both paths are dirs
    if [ ! -d "$_source_dir" ]; then
        print_error "Error: Source $(tint_error "$_source_dir") is not a directory"
        exit 1
    fi

    if [ ! -d "$_dest_dir" ]; then
        print_error "Error: Destination $(tint_error "$_dest_dir") is not a directory"
        exit 1
    fi

    # Move the source dir to the destination dir by moving all files in source dir to dest dir
    # Overwrite existing files, then remove the source dir

    files_expecting_overwrite=$(ls -A "$_source_dir" | while read -r file; do
        if [ -f "$_dest_dir/$file" ]; then
            ecko "$file"
        fi
    done)

    if [ "$_overwrite_mode" == "overwrite" ]; then
        print_warning "Warning: Some files in {{$_dest_dir}} will be replaced with files from {{$_source_dir}}:"
        for file in $files_expecting_overwrite; do
            print_orange "     - $file"
        done
    fi

    if [ -z "$files_expecting_overwrite" ] || [ "$_overwrite_mode" == "skip" ]; then
        mv -n "$_source_dir"* "$_dest_dir" >/dev/null 2>&1
    else
        mv -f "$_source_dir"* "$_dest_dir" >/dev/null 2>&1 
    fi
    

    find "$_source_dir" -type f \( "${hidden_files[@]}" \) -delete >/dev/null 2>&1

    failed_to_mv=$(ls -A "$_source_dir" | while read -r file; do
        if [ ! -f "$_dest_dir/$file" ]; then
            echo "$file"
        fi
    done)
    
    if [ -n "$failed_to_mv" ]; then

        print_error "Error moving files: some files in {{$_source_dir}} could not be moved:"
        # print files with print_error that didn't move, nicely indended with " - "
        ls -A "$_source_dir" | while read -r file; do
            print_red "     - $file"
        done
        return 1
    fi

    if [ "$(ok_to_del "$_source_dir")" = "true" ]; then
        rm -rf "$_source_dir"
    fi
}

mv_file_to_dir() {

    # Add trailing slash to destination
    local _source_file="$1"
    local _dest_dir=$(add_trailing_slash "$2")

    # Check if both dirs exist, otherwise exit with error
    if [ ! -f "$_source_file" ]; then
        print_error "Error: Source file {{$_source_file}} does not exist"
        exit 1
    fi

    if [ ! -d "$_dest_dir" ]; then
        print_error "Error: Destination directory {{$_dest_dir}} does not exist"
        exit 1
    fi

    # Make sure destination path is a dir
    if [ ! -d "$_dest_dir" ]; then
        print_error "Error: Destination {{$_dest_dir}} is not a directory"
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

handle_single_m4b() {
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
            target_dir="$outputfolder"
            unique_target="$target_dir/$file_name"
            ecko "Moving to completed folder (already an m4b) → $(tint_path "$unique_target")"
        else
            ecko "Moving book into its own folder → $(tint_path "$unique_target")"
            mkdir -p "$target_dir"
        fi

        if [ -f "$unique_target" ]; then
            ecko "(A file with the same name already exists in $(tint_path ."/$target_dir"), renaming incoming file to prevent data loss)"

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
            ecko "Successfully moved to $(tint_path "$unique_target")"
        else
            print_error "Error: Failed to move to {{$unique_target}}"
        fi
    done
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
        print_warning "Warning: Unable to delete {{$_dir}}, renaming it to -old and trying again..."
        mv "$_dir" "$_dir-old"

        # check if the dir was renamed successfully
        if [ ! -d "$_dir-old" ]; then
            print_error "Error: Unable to rename this folder, please delete it manually and try again"
            ecko "$why"
            if [ "$_exit_on_error" == "true" ]; then
                exit 1
            else
                return 1
            fi
        fi

        rm -rf "$_dir-old" 2>/dev/null
        if ls "$parent_dir" | grep -q "$_dir"; then
            print_error "Error: Unable to delete {{$_dir}}, please delete it manually and try again"
            print_red "$why"
            if [ "$_exit_on_error" == "true" ]; then
                exit 1
            else
                return 1
            fi
        fi
    fi
}

find_dirs_with_audio_files() {
    # Takes a path and counts the number of distinct folders/subfolders that contain audio files, including . root
    # Returns the count of unique paths found

    # Returns 0 if
    # - no audio files found in any dir, including .

    # Returns 1 if
    # - audio files found in . but nowhere else
    # - audio files found in ./subfolder/ but nowhere else
    # - audio files found in ./subfolder/nextfolder/ but nowhere else

    # Returns 2 if
    # - audio files found in . and in ./subfolder/
    # - audio files found in . and in ./subfolder/nextfolder/
    # - audio files found in ./subfolder/ and in ./subfolder/nextfolder/
    # - audio files found in ./subfolder/ and in ./otherfolder/
    
    # etc.

    local _path="$1"
    local _mindepth="$2"
    local _maxdepth="$3"

    if [ -n "$_mindepth" ]; then
        _mindepth=" -mindepth $_mindepth"
    fi
    if [ -n "$_maxdepth" ]; then
        _maxdepth=" -maxdepth $_maxdepth"
    fi

    # get a list of all subfolders that contain audio files, n levels deep.
    # get the top level folder of each of those subfolders, then | sort | uniq to get a list of unique top level folders
    find "$_path"$_mindepth$_maxdepth -type f \( "${audio_exts[@]}" \) -exec dirname {} + | cut -d'/' -f2- | sort | uniq
}

get_uniq_root_dirs() {
    # Takes the output from a "find" command and returns the unique root dirs
    
    # e.g. if find returns:
    # ./folder1/file1
    # ./folder1/file2
    # ./folder2/file3
    # ./folder2/file4

    # this function will return:
    # ./folder1
    # ./folder2

    local _paths="$1"

    # first trim the leading ./, then use cut -d'/' -f1
    echo "$_paths" | sed 's/^\.\///' | cut -d'/' -f1 | sort | uniq
}

get_root_dir() {
    # Takes a path and returns the root dir
    # e.g. /path/to/folder1/folder2/file1 becomes /path
    #      ./folder1/folder2/file1 becomes folder1
    #      ./this-file.txt becomes .

    local _path="$1"

    # if arg is empty, throw
    if [ -z "$_path" ]; then
        print_error "Error: get_root_dir() requires a path as an argument."
        return 1
    fi

    # if path ends in a file extension or is a file, get the dirname and recursive call get_root_dir
    # make sure to only allow .ext files, not .ext/ folders or ./ext folders
    if [ -f "$_path" ] || echo "$_path" | grep -q -E '\.[a-zA-Z0-9]+$'; then
        _path=$(dirname "$_path")
        get_root_dir "$_path"
        return
    fi

    # if path begins with / and > 0 chars, return the first dir e.g. /path/ or /path >> path
    # if path begins with ./ and > 2 chars, return the second dir e.g. ./path/ or ./path >> path
    # if path does not start with / or ./, but contains a /, get the left-most part before /
    # if path is ./, return .
    # if path is . or /, return as-is

    # if path is ./, return .
    if [ "$_path" = "./" ] || [ "$_path" = "." ]; then
        echo "."
    elif [ "$_path" = "/" ]; then
        echo "/"
    else
        [[ "$_path" =~ ^\.?/ ]] && echo "$_path" | cut -d'/' -f2 || echo "$_path" | cut -d'/' -f1
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
        print_error "Error: {{$_dir}} is not writable by current user, please fix permissions and try again"
        sleep $sleeptime
        exit 1
    fi

    # Make sure dir is empty, otherwise error
    if [ -n "$(ls -A "$_dir")" ]; then
        print_error "Error: {{$_dir}} is not empty, please empty it manually and try again"
        sleep $sleeptime
        exit 1
    fi
}

log_results() {
    # note: requires `column` version 2.39 or higher, available in util-linux 2.39 or higher

    # takes the original book's path and the result of the book and logs to $outputfolder/auto-m4b.log
    # format: [date] [time] [original book relative path] [info] ["result"=success|failed] [failure-message]
    local _book_src=$(basename "$1")
    # pad the relative path with spaces to 70 characters and truncate to 70 characters
    _book_src=$(printf '%-70s' "$(echo "$_book_src" | cut -c1-70)")

    #sanitize _book_src to remove multiple spaces and replace | with _
    _book_src=$(echo "$_book_src" | sed 's/  */ /g;s/|/_/g')
    
    local _result="$2"
    # pad result with spaces to 9 characters
    _result=$(printf '%-10s' "$_result")
    
    # strip all chars from _elapsed that are not number or :
    local _elapsed=$(echo "$3" | sed 's/[^0-9:]//g')

    # get current date and time
    local _datetime=$(date +"%Y-%m-%d %H:%M:%S%z")

    local _column_args=(
        "-t" 
        "-s" 
        $'\t'
        "-C" 
        "name=Date" 
        "-C" 
        "name=Result" 
        "-C" 
        "name=Original Folder,width=70" 
        "-C" 
        "name=Bitrate,right" 
        "-C" 
        "name=Sample Rate,right" 
        "-C" 
        "name=Type" 
        "-C" 
        "name=Files,right" 
        "-C" 
        "name=Size,right" 
        "-C" 
        "name=Duration,right" 
        "-C" 
        "name=Time,right"
        "-o"
        $'   '
    )

    # Read the current auto-m4b.log file and replace all double spaces with |
    local _log=$(cat "$outputfolder/auto-m4b.log" | sed 's/  \+ /\t/g')

    # Remove each line from _log if it starts with ^Date\s+
    _log=$(echo "$_log" | sed '/^Date\s/d')

    # Remove blank lines from end of log file
    _log=$(echo "$_log" | sed -e :a -e '/^\n*$/{$d;N;};/\n$/ba')

    # append the new log entry to the log var if _book_src is not empty or whitespace
    if [ -n "${_book_src// }" ]; then
        _log=$(echo "$_log" | sed '$a'"$_datetime\t$_result\t$_book_src\t$bitrate_friendly\t$samplerate_friendly\t.$file_type\t$audio_files_count files\t$audio_files_size\t$audio_files_duration\t$_elapsed")
    fi

    # pipe the log file into column to make it pretty
    # cp "$outputfolder/auto-m4b.log" "$outputfolder/auto-m4b.log.bak" # backup the log file for testing
    echo "$_log" | column "${_column_args[@]}" > "$outputfolder/auto-m4b.log"
    # cat "$outputfolder/auto-m4b.log"
    # cp "$outputfolder/auto-m4b.log.bak" "$outputfolder/auto-m4b.log" # restore the log file for testing
}

get_log_entry() {
    # looks in the log file to see if this book has been converted before and returns the log entry or ""
    local _book_src=$(basename "$1")
    local _log_entry=$(grep "$_book_src" "$outputfolder/auto-m4b.log")
    echo "$_log_entry"
}

strip_leading_newlines() {
    # takes a string and strips leading newlines
    local _string="$1"
    perl -pe 's/^\n*//' <<< "$_string"
}

strip_training_newlines() {
    # takes a string and strips trailing newlines
    local _string="$1"
    perl -pe 's/\n*$//' <<< "$_string"
}

trim_newlines() {
    # takes a string and strips leading and trailing newlines
    local _string="$1"
    perl -pe 's/^\n*//' <<< "$_string" | perl -pe 's/\n*$//'
}

strip_part_number() {
    # takes a string and strips the part number from it
    # e.g. "The Name of the Wind, Part 1)" becomes "The Name of the Wind"
    #      "The Name of the Wind Part 002" becomes "The Name of the Wind"
    #      "The Name of the Wind - 012" becomes "The Name of the Wind"
    local _string="$1"
    local _part_number_pattern=",?[-_–—.\s]*?(?:part|ch(?:\.|apter))?[-_–—.\s]*?(?<part1>\d+)(?:$|[-_–—.\s]*?(?:of|-)[-_–—.\s]*?(?<part2>\d+)$)"
    local _ignore_if_pattern="(?:\bbook\b|\bvol(?:ume)?)\s*\d+$"

    local _matches_part_number=$(perl -nE "print if /$_part_number_pattern/i" <<< "$_string")
    local _matches_ignore_if=$(perl -nE "print if /$_ignore_if_pattern/i" <<< "$_string")

    # if it matches both the part number and ignore, return original string
    if [ -n "$_matches_part_number" ] && [ -z "$_matches_ignore_if" ]; then
        perl -pe "s/$_part_number_pattern//i" <<< "$_string"
    else
        echo "$_string"
    fi
}

fix_smart_quotes() {
    # takes a string and replaces smart quotes with regular quotes
    local _string="$1"
    perl -pe "s/[\x{2018}\x{2019}\x{201A}\x{201B}\x{2032}\x{2035}]/'/g" <<< "$_string" | perl -pe "s/[\x{201C}\x{201D}\x{201E}\x{201F}\x{2033}\x{2036}]/\"/g"
}

human_elapsed_time() {
    # make friendly elapsed time as HHh:MMm:SSs but don't show hours if 0
    # e.g. 00m:52s, 12m:52s, 1h:12m:52s 

    local _elapsedtime="$1"

    local _hours=$(bc <<< "scale=0; $_elapsedtime/3600")
    local _minutes=$(bc <<< "scale=0; ($_elapsedtime%3600)/60")
    local _seconds=$(bc <<< "scale=0; $_elapsedtime%60")
    printf "%02dh:%02dm:%02ds\n" $_hours $_minutes $_seconds | sed 's/^0//;s/^0*h.//;s/^0(?!m)//'
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

get_file_duration() {
    ffprobe -hide_banner -loglevel 0 -of flat -i "$1" -show_entries format=duration -of default=noprint_wrappers=1:nokey=1
}

get_duration() {
    # takes a file or directory and returns the length in seconds of all audio files
    # if no path specified, assume current directory
    # takes a "human" arg that returns the length in human readable format, rounding to the nearest minute
    local _path="${1:-"."}"
    local _format="${2:-"bytes"}"

    # check if path exists and whether is a dir or single file. If single file, return length of it, otherwise return length of all files in dir
    if [ ! -e "$_path" ]; then
        print_error "Error getting duration: Path {{$_dir}} does not exist"
        exit 1
    elif [ -f "$_path" ]; then

        # make sure it is in audio_exts otherwise throw
        if [[ ! $(find "$_path" -type f \( "${audio_exts[@]}" \)) ]]; then
            print_error "File {{$_path}} is not an audio file"
            exit 1
        fi

        local _duration
        _duration=$(get_file_duration "$_path")
        if [ "$_format" == "human" ]; then
          _duration=$(printf "%.0f" "$_duration")  # Round up to the nearest second
          _duration=$(human_elapsed_time "$_duration")
        fi
        echo "$_duration"
    elif [ -d "$_path" ]; then
        
        # make sure there are some audio files in the dir. Get a list of them all, and then the count, and if count is 0 exit. Otherwise, loop files and add up length
        
        _files=$(find "$_path" -type f \( "${audio_exts[@]}" \))
        _count=$(echo "$_files" | wc -l)
        if [ $_count -eq 0 ]; then
            print_notice "No audio files found in $(tint_path "$_path")"
            exit 1
        fi

        local _duration=0
        while read -r _file; do
            _duration=$(echo "$_duration + $(get_file_duration "$_file")" | bc)
        done <<< "$_files"

        if [ "$_format" == "human" ]; then
            # if length has a decimal value that is less than 0.1, round down to nearest second, otherwise round up to nearest second
            local _decimal=$(echo "$_duration" | sed 's/^[0-9]*\.//')
            if [ "$_decimal" -lt 1 ]; then
                _duration=$(printf "%.0f" "$_duration")  # Round down to the nearest second
            else
                _duration=$(printf "%.0f" "$_duration")  # Round up to the nearest second
            fi
            _duration=$(human_elapsed_time "$_duration")
        fi
        echo "$_duration"
    fi
    
}

round_bitrate() {
    local bitrate=$1
    local standard_bitrates=(32 40 48 56 64 80 96 112 128 160 192 224 256 320) # see https://superuser.com/a/465660/254022
    local closest_bitrate=${standard_bitrates[0]}
    local min_bitrate=${standard_bitrates[0]}

    local bitrate_k=$(echo "$bitrate / 1000" | bc)

    # get the lower and upper bitrates (inclusive) from the standard_bitrates array
    for i in "${standard_bitrates[@]}"; do
        if [ "$i" -le "$bitrate_k" ]; then
            lower_bitrate="$i"
        fi
        if [ "$i" -ge "$bitrate_k" ]; then
            upper_bitrate="$i"
            break
        fi
    done

    # should never happen, but if the upper bitrate is empty, then the bitrate is higher 
    # than the highest standard bitrate, so return the highest standard bitrate
    if [ -z "$upper_bitrate" ]; then
        closest_bitrate=${standard_bitrates[-1]}
    fi

    # get 25% of the difference between lower and upper
    local diff=$(echo "($upper_bitrate - $lower_bitrate) / 4" | bc)

    # if bitrate_k + diff is closer to bitrate_k than bitrate_k - diff, use upper bitrate
    if [ $(echo "$bitrate_k + $diff" | bc) -ge "$bitrate_k" ]; then
        closest_bitrate="$upper_bitrate"
    else
        closest_bitrate="$lower_bitrate"
    fi

    # if the closest bitrate is less than the minimum bitrate, use the minimum bitrate
    if [ "$closest_bitrate" -lt "$min_bitrate" ]; then
        closest_bitrate="$min_bitrate"
    fi

    printf "%d000" "$closest_bitrate"
}

compare_trim() {
    echo "$1" | awk '{$1=$1};1'
}

friendly_date() {
    date "+%a, %d %b %Y %I:%M:%S %Z"
}

split_path() {
    local path=$1
    local limit=${2:-120}
    local indent=${3:-0}
    indent=$(printf "%${indent}s")
    local length=0
    local output=""

    IFS='/' read -ra parts <<< "$path"

    for part in "${parts[@]}"; do
        if [[ $part == "" ]]; then
            continue
        fi
        length=$((length + ${#part} + 1))
        if [[ $length -gt $limit ]]; then
            output=${output%/}
            output="$output\n$indent/$part"
            length=$((${#part} + 1))
        else
            output="$output/$part"
        fi
    done

    echo -e "$output"
}

extract_id3_tag() {
    # takes a file and an id3 tag name and returns the value of that tag
    # e.g. extract_id3_tag "file.mp3" "title" returns the title of the file
    local _file="$1"
    local _tag="$2"
    ffprobe -hide_banner -loglevel 0 -of flat -i "$_file" -select_streams a -show_entries format_tags="$_tag" -of default=noprint_wrappers=1:nokey=1
}

count_numbers_in_string() {
    # takes a string and returns the number of numbers in it (count each digit individually)
    local _string="$1"
    echo "$_string" | grep -o '[0-9]' | wc -l | tr -d ' '
}

str_in_str() {
    # takes two strings and returns true if the first string is in the second string
    local _str1="$1"
    local _str2="$2"

    # if either string is empty, return false
    if [ -z "$_str1" ] || [ -z "$_str2" ]; then
        return 1
    fi

    if echo "$_str2" | grep -q -i "$_str1"; then
        return 0
    else
        return 1
    fi
}

extract_metadata() {

    local _folder_name="$1"

    sample_audio=$(find . -maxdepth 1 -type f \( "${audio_exts[@]}" \) | sort | head -n 1)

    # if sample_audio doesn't exist, return 1 so we can coninue
    if [ -z "$sample_audio" ]; then
        print_error "Error: No audio files found in {{$(pwd)}}, cannot extract metadata"
        return 1
    fi

    ecko "Sampling $(tint_light_grey "$(rm_leading_dot_slash "$sample_audio")") for id3 tags and quality information..."

    bitrate=$(round_bitrate "$(ffprobe -hide_banner -loglevel 0 -select_streams a:0 -show_entries stream=bit_rate -of default=noprint_wrappers=1:nokey=1 "$sample_audio")")
    samplerate=$(ffprobe -hide_banner -loglevel 0 -of flat -i "$sample_audio" -select_streams a -show_entries stream=sample_rate -of default=noprint_wrappers=1:nokey=1)

    # read id3 tags of mp3 file
    id3_title=$(extract_id3_tag "$sample_audio" "title")
    id3_artist=$(extract_id3_tag "$sample_audio" "artist")
    id3_albumartist=$(extract_id3_tag "$sample_audio" "album_artist")
    id3_album=$(extract_id3_tag "$sample_audio" "album")
    id3_sortalbum=$(extract_id3_tag "$sample_audio" "sort_album")
    id3_date=$(extract_id3_tag "$sample_audio" "date")
    id3_year=$(echo "$id3_date" | grep -Eo '[0-9]{4}')
    id3_comment=$(extract_id3_tag "$sample_audio" "comment")
    id3_composer=$(extract_id3_tag "$sample_audio" "composer")

    id3_title_numbers=$(count_numbers_in_string "$id3_title")
    id3_album_numbers=$(count_numbers_in_string "$id3_album")
    id3_sortalbum_numbers=$(count_numbers_in_string "$id3_sortalbum")

    # If title has more numbers in it than the album, it's probably a part number like Part 01 or 01 of 42
    title_is_partno=$(
        if [ "$id3_title_numbers" -gt "$id3_album_numbers" ] && [ "$id3_title_numbers" -gt "$id3_sortalbum_numbers" ]; then
            echo "true"
        else
            echo "false"
        fi
    )
    
    album_is_in_title=$(str_in_str "$id3_album" "$id3_title" && echo "true")
    sortalbum_is_in_title=$(str_in_str "$id3_sortalbum" "$id3_title" && echo "true")

    title_is_in_folder_name=$(str_in_str "$id3_title" "$_folder_name" && echo "true")
    album_is_in_folder_name=$(str_in_str "$id3_album" "$_folder_name" && echo "true")
    sortalbum_is_in_folder_name=$(str_in_str "$id3_sortalbum" "$_folder_name" && echo "true")

    id3_title_is_title="false"
    id3_album_is_title="false"
    id3_sortalbum_is_title="false"

    # Title:
    if [ -z "$id3_title" ] && [ -z "$id3_album" ] && [ -z "$id3_sortalbum" ]; then
        # If no id3_title, id3_album, or id3_sortalbum, use the extracted title
        title="$dir_title"
    else
        echo
        # If (sort)album is in title, it's likely that title is something like {book name}, ch. 6
        # So if album is in title, prefer album
        if [ "$album_is_in_title" = "true" ]; then
            title="$id3_album"
            id3_album_is_title="true"
        elif [ "$sortalbum_is_in_title" = "true" ]; then
            title="$id3_sortalbum"
            id3_sortalbum_is_title="true"
        # If id3_title is in $_folder_name, prefer id3_title
        elif [ "$title_is_in_folder_name" = "true" ]; then
            title="$id3_title"
            id3_title_is_title="true"
        # If title is a part no., we should use album or sortalbum
        elif [ "$title_is_partno" = "true" ]; then
            # If album is in $_folder_name or if sortalbum doens't exist, prefer album
            if [ "$album_is_in_folder_name" = "true" ] || [ -z "$id3_sortalbum" ]; then
                title="$id3_album"
                id3_album_is_title="true"
            elif [ "$sortalbum_is_in_folder_name" = "true" ] || [ -z "$id3_album" ]; then
                title="$id3_sortalbum"
                id3_sortalbum_is_title="true"
            fi
        fi
        if [ -z "$title" ]; then
            title="$id3_title"
            id3_title_is_title="true"
        fi
    fi

    title=$(strip_part_number "$title")
    title=$(fix_smart_quotes "$title")

    print_list "- Title: $title"


    # Album:
    if [ -n "$id3_album" ]; then
        album="$id3_album"
    elif [ -n "$id3_sortalbum" ]; then
        album="$id3_sortalbum"
    else
        album="$dir_title"
    fi
    print_list "- Album: $album"

    if [ -n "$id3_sortalbum" ]; then
        sortalbum="$id3_sortalbum"
    elif [ -n "$id3_album" ]; then
        sortalbum="$id3_album"
    else
        sortalbum="$dir_title"
    fi
    # ecko "  Sort album: $sortalbum"

    artist_is_in_folder_name=$(str_in_str "$id3_artist" "$_folder_name" && echo "true")
    albumartist_is_in_folder_name=$(str_in_str "$id3_albumartist" "$_folder_name" && echo "true")

    id3_artist_is_author="false"
    id3_albumartist_is_author="false"
    id3_albumartist_is_narrator="false"
    
    id3_artist_has_narrator=$(echo "$id3_artist" | grep -qEi "(narrat|read by)" && echo "true" || echo "false")
    id3_albumartist_has_narrator=$(echo "$id3_albumartist" | grep -qEi "(narrat|read by)" && echo "true" || echo "false")
    id3_comment_has_narrator=$(echo "$id3_comment" | grep -qEi "(narrat|read by)" && echo "true" || echo "false")
    id3_composer_has_narrator=$(echo "$id3_composer" | grep -qEi "(narrat|read by)" && echo "true" || echo "false")

    # Artist:
    if [ -n "$id3_albumartist" ] && [ -n "$id3_artist" ] && [ "$id3_albumartist" != "$id3_artist" ]; then
        # Artist and Album Artist are different
        if [ "$artist_is_in_folder_name" = "$albumartist_is_in_folder_name" ]; then
            # if both or neither are in the folder name, use artist for author and album artist for narrator
            artist="$id3_artist"
            albumartist="$id3_albumartist"
        elif [ "$artist_is_in_folder_name" = "true" ]; then
            # if only artist is in the folder name, use it for both
            artist="$id3_artist"
            albumartist="$id3_artist"
        elif [ "$albumartist_is_in_folder_name" = "true" ]; then
            # if only albumartist is in the folder name, use it for both
            artist="$id3_albumartist"
            albumartist="$id3_albumartist"
        fi
        
        artist="$id3_artist"
        albumartist="$id3_artist"
        narrator="$id3_albumartist"

        id3_artist_is_author="true"
        id3_albumartist_is_narrator="true"

    elif [ -n "$id3_albumartist" ] && [ -z "$id3_artist" ]; then
        # Only Album Artist is set, using it for both
        artist="$id3_albumartist"
        albumartist="$id3_albumartist"
        id3_albumartist_is_author="true"
    elif [ -n "$id3_artist" ]; then
        # Artist is set, prefer it
        artist="$id3_artist"
        albumartist="$id3_artist"
        id3_artist_is_author="true"
    else
        # Neither Artist nor Album Artist is set, use folder Author for both
        artist="$dir_author"
        albumartist="$dir_author"
    fi

    # Narrator
    # If id3_comment or (album)artist contains "Narrated by" or "Narrator", use that
    if [ "$id3_comment_has_narrator" = "true" ]; then
        narrator=$(echo "$id3_comment" | perl -n -e "/$narrator_pattern/i && print $+{narrator}")
    elif [ "$id3_artist_has_narrator" = "true" ]; then
        narrator=$(echo "$id3_artist" | perl -n -e "/$narrator_pattern/i && print $+{narrator}")
        artist=""
    elif [ "$id3_albumartist_has_narrator" = "true" ]; then
        narrator=$(echo "$id3_albumartist" | perl -n -e "/$narrator_pattern/i && print $+{narrator}")
        albumartist=""
    elif [ "$id3_albumartist_is_narrator" = "true" ]; then
        narrator="$id3_albumartist"
        albumartist=""
    elif [ "$id3_composer_has_narrator" = "true" ]; then
        narrator=$(echo "$id3_composer" | perl -n -e "/$narrator_pattern/i && print $+{narrator}")
        composer=""
    else
        narrator="$dir_narrator"
    fi

    # Swap first and last names if a comma is present
    artist=$(swap_first_last "$artist")
    author=$artist
    albumartist=$(swap_first_last "$albumartist")
    narrator=$(swap_first_last "$narrator")

    # If comment does not have narrator, but narrator is not empty, 
    # pre-pend narrator to comment as "Narrated by <narrator>. <existing comment>"
    if [ -n "$narrator" ]; then
        if [ -z "$id3_comment" ]; then
            id3_comment="Read by $narrator"
        elif [ "$id3_comment_has_narrator" = "false" ]; then
            id3_comment="Read by $narrator // $id3_comment"
        fi
    fi

    print_list "- Author: $artist"
    print_list "- Narrator: $narrator"

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
    print_list "- Date: $date"
    # extract 4 digits from date
    year=$(echo "$date" | grep -Eo '[0-9]{4}')
    
    # convert bitrate and sample rate to friendly to kbit/s, rounding to nearest tenths, e.g. 44.1 kHz
    bitrate_friendly="$(echo "$bitrate" | awk '{printf "%.0f", int($1/1000)}') kb/s"
    bitrate="$(echo "$bitrate" | awk '{printf "%.0f", int($1/1000)}')k"
    samplerate_friendly="$(echo "$samplerate" | awk '{printf "%.1f", $1/1000}') kHz"
    print_list "- Quality: $bitrate_friendly @ $samplerate_friendly"
    
    # Description:
    #      - Write all extracted properties, and "Original folder name: <folder name>" to this field, e.g.
    #        Book title: <book title>
    #        Author: <author>
    #        Date: <date>
    #        Narrator: <narrator>
    #        Quality: <bitrate_friendly> @ <samplerate_friendly>
    #        Original folder name: <folder name>
    #      - this needs to be newline-separated (\n does not work, use $'\n' instead)

    # if $mergefolder$book doesn't exist, throw error
    if [ ! -d "$mergefolder$book" ]; then
        print_error "Error: Working dir for book {{$mergefolder$book}} does not exist"
        exit 1
    fi
    
    # Save description to description.txt alongside the m4b file
    description_file="$mergefolder$book/description.txt"

    # Write the description to the file with newlines, ensure utf-8 encoding
    ecko "Book title: $title\n\
Author: $author\n\
Date: $date\n\
Narrator: $narrator\n\
Quality: $bitrate_friendly @ $samplerate_friendly\n\
Original folder: $book\n\
Original file type: .$file_type\n\
Original size: $audio_files_size\n\
Original duration: $audio_files_duration" > "$description_file"

    # check to make sure the file was created
    if [ ! -f "$description_file" ]; then
        print_error "Error: Failed to create {{$description_file}}"
        exit 1
    fi

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
        id3tags=" --title=\"$title\" --sorttitle=\"$title\""
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

write_id3_tags() {
    # takes a file and writes the specified id3 tags to it, in the format --tag="value"
    local _file="$1"
    local _exiftool_args=("${@:2}")
    local _api_opts=("-api" "filter=\"s/ \(approx\)//\"") # remove (approx) from output

    # if file doesn't exist, throw error
    if [ ! -f "$_file" ]; then
        echo -e "Error: Cannot write id3 tags, {{$_file}} does not exist"
        exit 1
    fi

    # make sure the exiftool command exists
    if ! command -v exiftool >/dev/null 2>&1; then
        echo -e "Error: exiftool is not available, please install it with {{(apt-get install exiftool)}} and try again"
        exit 1
    fi
    
    # write tag to file, using eval so that quotes are not escaped
    exiftool -overwrite_original "${_exiftool_args[@]}" "${_api_opts[@]}" "$_file" &>/dev/null
}

verify_id3_tags() {
    # takes a file and verifies that the id3 tags match the extracted metadata
    # if they do not match, it will print a notice and update the id3 tags

    local _file="$1"

    # if file doesn't exist, throw error
    if [ ! -f "$_file" ]; then
        print_error "Error: Cannot verify id3 tags, {{$_file}} does not exist"
        exit 1
    fi

    local _exiftool_args=()

    # enumerate all id3 tags and compare to extracted metadata
    local _id3_title=$(extract_id3_tag "$_file" "title")
    local _id3_artist=$(extract_id3_tag "$_file" "artist")
    local _id3_album=$(extract_id3_tag "$_file" "album")
    local _id3_sortalbum=$(extract_id3_tag "$_file" "sort_album")
    local _id3_albumartist=$(extract_id3_tag "$_file" "album_artist")
    local _id3_date=$(extract_id3_tag "$_file" "date")
    local _id3_comment=$(extract_id3_tag "$_file" "comment")

    local _update_title=false
    local _update_author=false
    local _update_date=false
    local _update_comment=false

    if [ -n "$title" ] && [ "$_id3_title" != "$title" ]; then
        _update_title=true
        print_list "- Title needs updating: $(tint_light_grey "${_id3_title:-(Missing)}") $(tint_amber ») $(tint_light_grey "$title")"
    fi

    if [ -n "$author" ] && [ "$_id3_artist" != "$author" ]; then
        _update_author=true
        print_list "- Artist (author) needs updating: $(tint_light_grey "${_id3_artist:-(Missing)}") $(tint_amber ») $(tint_light_grey "$author")"
    fi

    if [ -n "$title" ] && [ "$_id3_album" != "$title" ]; then
        _update_title=true
        print_list "- Album (title) needs updating: $(tint_light_grey "${_id3_album:-(Missing)}") $(tint_amber ») $(tint_light_grey "$title")"
    fi

    if [ -n "$title" ] && [ "$_id3_sortalbum" != "$title" ]; then
        _update_title=true
        print_list "- Sort album (title) needs updating: $(tint_light_grey "${_id3_sortalbum:-(Missing)}") $(tint_amber ») $(tint_light_grey "$title")"
    fi

    if [ -n "$author" ] && [ "$_id3_albumartist" != "$author" ]; then
        _update_author=true
        print_list "- Album artist (author) needs updating: $(tint_light_grey "${_id3_albumartist:-(Missing)}") $(tint_amber ») $(tint_light_grey "$author")"
    fi

    if [ -n "$date" ] && [ "$_id3_date" != "$date" ]; then
        id3tags="$id3tags -Date=$date"
        print_list "- Date needs updating: $(tint_light_grey "${_id3_date:-(Missing)}") $(tint_amber ») $(tint_light_grey "$date")"
    fi

    if [ -n "$comment" ] && [ "$(compare_trim "$_id3_comment")" != "$(compare_trim "$comment")" ]; then
        id3tags="$id3tags -Comment=$comment"
        print_list "- Comment needs updating: $(tint_light_grey "${_id3_comment:-(Missing)}") $(tint_amber ») $(tint_light_grey "$comment")"
    fi

    # for each of the id3 tags that need updating, write the id3 tags
    if [ "$_update_title" = true ]; then
        _exiftool_args+=("-Title=$title")
        _exiftool_args+=("-Album=$title")
        _exiftool_args+=("-SortAlbum=$title")
    fi

    if [ "$_update_author" = true ]; then
        _exiftool_args+=("-Artist=$author")
        _exiftool_args+=("-SortArtist=$author")
    fi

    if [ "$_update_date" = true ]; then
        _exiftool_args+=("-Date=$date")
    fi

    if [ "$_update_comment" = true ]; then
        _exiftool_args+=("-Comment=$comment")
    fi

    # set track_number and other statics
    _exiftool_args+=("-TrackNumber=1/$m4b_num_parts")
    _exiftool_args+=("-EncodedBy=auto-m4b")
    _exiftool_args+=("-Genre=Audiobook")
    _exiftool_args+=("-Copyright=")

    # write with exiftool
    if [ ${#_exiftool_args[@]} -gt 0 ]; then
        write_id3_tags "$_file" "${_exiftool_args[@]}"
    fi
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

# glasses 1: ⌐◒-◒
# glasses 2: ᒡ◯ᴖ◯ᒢ

# continue until $m  5
while [ $m -ge 0 ]; do

    # -----------------------------------------------------------------------
    # Ready to start
    # -----------------------------------------------------------------------
    
    cd_inbox_folder

    # Check if there are audio files in the inbox folder. If none, sleep and exit
    if [ -z "$(find . -type f \( "${audio_exts[@]}" \) -print0)" ]; then
        sleep $sleeptime
        exit 0
    fi

    current_local_time=$(date +"%Y-%m-%d %H:%M:%S")
    print_aqua "-------------------  ⌐◒-◒  auto-m4b • $current_local_time  ---------------------"
    print_grey "$config"

    # Remove fix folder if there are no non-hidden files in it (check recursively)
    if [ -d "$fixitfolder" ] && [ -z "$(find "$fixitfolder" -not -path '*/\.*' -type f)" ]; then
        ecko "Removing fix folder, it is empty..."
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

    ecko "Checking for new books in $(tint_light_grey "$inboxfolder") ꨄ︎"

    # Check if there are any directories modified in the last minute
    unfinished_dirs=$(find . -type d -mmin -0.1)

    # if unfinished dirs exist, sleep script until they are finished copying
    if [ -n "$unfinished_dirs" ]; then
        print_notice "The inbox folder was recently modified, waiting for a bit to make sure all files are done copying...\n"
        sleep $sleeptime
        exit 0
    fi

    handle_single_m4b

    # Find directories containing audio files, handling single quote if present
    audio_dirs=$(find_dirs_with_audio_files . 1)
    audio_dirs=$(get_uniq_root_dirs "$audio_dirs")

    books_count=$(echo "$audio_dirs" | wc -l)

    # If no books to convert, ecko, sleep, and exit
    if [ "$books_count" -eq 0 ]; then
        ecko "No books to convert, next check in $sleeptime\n"
        sleep $sleeptime
        exit 0
    fi

    ecko "Found $books_count $(pluralize "$books_count" book) to convert\n"

    echo "$audio_dirs" | while IFS= read -r book_rel_path; do

        # get real path of book
        book_full_path=$(realpath "$book_rel_path")

        # get basename of book
        book=$(basename "$book_rel_path")

        divider

        print_blue "$book"

        book_audio_dirs=$(find_dirs_with_audio_files "$book_rel_path")
        book_audio_dirs_count=$(echo "$book_audio_dirs" | wc -l)

        # check if the current dir was modified in the last 1m and skip if so
        if [ "$(find "$book_rel_path" -mmin -0.5)" ]; then
            ecko
            print_notice "Skipping this book, it was recently updated and may still be copying"
            continue
        fi

        # use count_dirs_with_audio_files to check if 0, 1, or >1
        if [ "$book_audio_dirs_count" -eq 0 ]; then
            ecko
            print_notice "No audio files found, skipping"
            continue

        elif [ "$book_audio_dirs_count" -ge 2 ]; then
            ecko ""
            print_error "Error: This book contains multiple folders with audio files"
            ecko "Maybe this is a multi-disc book, or maybe it is multiple books?"
            ecko "All files must be in a single folder, named alphabetically in the correct order\n"
            dir_to_move=$(join_paths "$inboxfolder" "$book_rel_path")
            ecko "Moving to fix folder → $(tint_path "$(join_paths "$fixitfolder" "$book")")\n"
            ensure_dir_exists_and_is_writable "$fixitfolder"
            mv_dir "$dir_to_move" "$fixitfolder"
            continue
            
        elif [ "$book_audio_dirs_count" -eq 1 ] && [ "$book_audio_dirs" != "$book" ]; then
            ecko "Audio files for this book are a subfolder: $(tint_path ./"$book_audio_dirs")"
            root_of_book=$(join_paths "$inboxfolder" "$book_rel_path")
            dir_to_move=$(join_paths "$root_of_book" "$book_audio_dirs")
            ecko "Moving them to book's root → $(tint_path "$root_of_book")"

            # move all files in dir to $inboxfolder/$book
            mv_dir "$dir_to_move" "$root_of_book"
        fi
        
        ecko "\nPreparing to convert..."

        # check if book is a set of mp3 files that need to be converted to m4b
        mp3_count=$(find "$book_rel_path" -type f -iname '*.mp3' | wc -l)
        m4a_count=$(find "$book_rel_path" -type f -iname '*.m4a' | wc -l)
        m4b_count=$(find "$book_rel_path" -type f -iname '*.m4b' | wc -l)
        wma_count=$(find "$book_rel_path" -type f -iname '*.wma' | wc -l)

        is_mp3=$( [ "$mp3_count" -gt 0 ] && echo "true" || echo "false" )
        is_m4a=$( [ "$m4a_count" -gt 0 ] && echo "true" || echo "false" )
        is_m4b=$( [ "$m4b_count" -gt 0 ] && echo "true" || echo "false" )
        is_wma=$( [ "$wma_count" -gt 0 ] && echo "true" || echo "false" )

        # get full path of book (remove leading ./ if relative path)
        # book_full_path=$inboxfolder$(ecko "$book_rel_path" | sed 's/^\.\///')
        
        if [ "$is_m4b" == "true" ]; then
            file_type="m4b"
        elif [ "$is_m4a" == "true" ]; then
            file_type="m4a"
        elif [ "$is_mp3" == "true" ]; then
            file_type="mp3"
        elif [ "$is_wma" == "true" ]; then
            file_type="wma"
        else
            print_error "Error: {{$book_full_path}} does not contain any known audio files, skipping"
            continue
        fi

        # Count the number of audio files in the book folder and get a human readable filesize
        audio_files_count=$(find "$book_full_path" -type f \( "${audio_exts[@]}" \) | wc -l)
        audio_files_size=$(get_size "$book_full_path" "human")
        audio_files_duration=$(get_duration "$book_full_path" "human")

        print_list "- Output path: $(tint_light_grey "$book_full_path")"
        print_list "- File type: $(tinted_file ."$file_type")"
        print_list "- Audio files: $audio_files_count"
        print_list "- Total size: $audio_files_size"
        print_list "- Duration: $audio_files_duration"
        ecko ""

        # Check if a copy of this book is in fixitfolder and bail
        if [ -d "$fixitfolder$book" ]; then
            print_error "Error: A copy of this book is in the fix folder, please fix it and try again."
            continue
        fi
        
        # Copy files to backup destination        
        if [ "$MAKE_BACKUP" == "N" ]; then
            ecko "Skipping making a backup"
        elif [ -z "$(ls -A "$book_full_path")" ]; then
            ecko "Skipping making a backup (folder is empty)"
        else
            ecko "Making a backup copy → $(tint_path "$backupfolder$book")"
            cp_dir "$book_full_path" "$backupfolder"

            # Check that files count and folder size match
            orig_files_count=$(find "$book_full_path" -type f \( "${audio_exts[@]}" \) | wc -l)
            orig_files_size=$(get_size "$book_full_path" "human")
            orig_bytes=$(get_size "$book_full_path" "bytes")
            orig_plural=$(pluralize $orig_files_count file)

            backup_files_count=$(find "$backupfolder$book" -type f \( "${audio_exts[@]}" \) | wc -l)
            backup_files_size=$(get_size "$backupfolder$book" "human")
            backup_bytes=$(get_size "$backupfolder$book" "bytes")
            backup_plural=$(pluralize $backup_files_count file)

            if [ "$orig_files_count" == "$backup_files_count" ] && [ "$orig_files_size" == "$backup_files_size" ]; then
                ecko "Backup successful - $backup_files_count $orig_plural ($backup_files_size)"
            elif [ "$orig_files_count" -le "$backup_files_count" ] && [ "$orig_bytes" -le "$backup_bytes" ]; then
                print_light_grey "Backup successful - but expected $orig_plural ($orig_files_size), found $backup_files_count $backup_plural ($backup_files_size)"
                print_light_grey "Assuming this is a previous backup and continuing"
            else
                print_error "Backup failed - expected $orig_files_count $orig_plural ($orig_files_size), found $backup_files_count $backup_plural ($backup_files_size)"
                ecko "Skipping this book"
                continue
            fi
        fi
        
        extract_folder_info "$book"

        # Set up destination paths
        build_m4bfile="$buildfolder$book/$book.m4b"
        final_m4bfile="$outputfolder$book/$book.m4b"
        logfile="./m4b-tool.log"

        cd_inbox_folder "$book"

        # Move from inbox to merge folder
        ecko "\nCopying files to build folder...\n"
        cp_dir "$book_full_path" "$mergefolder"

        cd_merge_folder "$book"

        extract_metadata "$book"

        # if output file already exists, check if OVERWRITE_EXISTING is set to Y; if so, overwrite, if not, exit with error
        if [ -f "$final_m4bfile" ]; then
            if [ "$OVERWRITE_EXISTING" == "N" ]; then
                # Check if a copy of this book is in the done folder and bail
                if [ -d "$donefolder$book" ]; then
                    ecko "Found a copy of this book in $(tint_path "$donefolder"), it has probably already been converted"
                    ecko "Skipping this book because OVERWRITE_EXISTING is not \"Y\""
                    continue
                elif [ -s "$final_m4bfile" ]; then
                    print_error "Error: Output file already exists and OVERWRITE_EXISTING is not \"Y\", skipping this book"
                    continue
                fi
            else
                print_warning "Warning: Output file already exists, it and any other {{.m4b}} files will be overwritten"
                # delete all m4b files in output folder that have $book as a substring, and print_error "Deleted {file}"
                find "$outputfolder" -maxdepth 1 -type f -name "*$book*.m4b" -print0 | while IFS= read -r -d $'\0' m4b_file; do
                    print_error "Deleted $(tint_path "$m4b_file")"
                    rm "$m4b_file"
                done
                sleep 1
            fi
            ecko
        fi

        # Pre-create tempdir for m4b-tool in "$buildfolder$book-tmpfiles" and ensure writable
        clean_workdir "$buildfolder$book"
        clean_workdir "$buildfolder$book/$book-tmpfiles"       

        # Remove any existing log file
        rm -f "$logfile"
        
        starttime=$(date +%s)
        starttime_friendly=$(friendly_date)

        ecko

        if [ "$is_mp3" = "true" ] || [ "$is_wma" = "true" ]; then

            ecko "Starting $(tinted_file $file_type) ➜ $(tinted_m4b) conversion at $(tint_light_grey "$starttime_friendly")..."

            $m4btool merge . -n $debug_switch --audio-bitrate="$bitrate" --audio-samplerate="$samplerate"$skipcoverimage --use-filenames-as-chapters --no-chapter-reindexing --max-chapter-length="$maxchapterlength" --audio-codec=libfdk_aac --jobs="$CPUcores" --output-file="$build_m4bfile" --logfile="$logfile" "$id3tags" >$logfile 2>&1
            
        elif [ "$is_m4a" = "true" ] || [ "$is_m4b" = "true" ]; then

            ecko "Starting merge/passthrough ➜ $(tinted_m4b) at $(tint_light_grey "$starttime_friendly")..."

            # Merge the files directly as chapters (use chapters.txt if it exists) instead of converting
            # Get existing chapters from file    
            chapters=$(ls ./*chapters.txt 2> /dev/null | wc -l)
            chaptersfile=$(ls ./*chapters.txt 2> /dev/null | head -n 1)
            chaptersopt=$([ "$chapters" != "0" ] && ecko "--chapters-file=\"$chaptersfile\"" || echo ""])
            chapters_switch=$([ "$chapters" == "0" ] && echo "--use-filenames-as-chapters --no-chapter-reindexing" || echo ""])

            if [ "$chapters" != "0" ]; then
                ecko Setting chapters from chapters.txt file...
            fi
            $m4btool merge . -n $debug_switch $chapters_switch --audio-codec=copy --jobs="$CPUcores" --output-file="$build_m4bfile" --logfile="$logfile" "$chaptersopt" "$id3tags" >$logfile 2>&1
        fi

        # print_error "Error: [TEST] m4b-tool failed to convert \"$book\""
        # ecko "     Moving \"$book\" to fix folder..."
        # mv_dir "$mergefolder$book" "$fixitfolder"
        # cp "$logfile" "$fixitfolder$book/m4b-tool.$book.log"
        # log_results "$book_full_path" "FAILED" ""
        # break

        endtime_friendly=$(friendly_date)
        elapsedtime=$(($(date +%s) - "$starttime"))
        elapsedtime_friendly=$(human_elapsed_time "$elapsedtime")

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
                found_ignorable_error=$(grep -i -Pzo "an error occured[\s\S]*?${ignorable_error}[\s\S]*?\)" "$logfile")
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
                print_error "Error: m4b-tool found an error in the log file"
                print_red "     Message: $error_line"
                ecko "\nMoving to fix folder → $(tint_path "$fixitfolder$book")"
                
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

                    # remove book folder from inbox if it is empty
                    if ! rmdir "$inboxfolder$book" 2>/dev/null; then
                        print_warning "Warning: Some files in {{$inboxfolder$book}} couldn't be moved"
                    fi

                    cp "$logfile" "$fixitfolder$book/$book.m4b-tool.log"
                    log_results "$book_full_path" "FAILED" ""
                    continue
                fi
                ecko "     See log file in $(tint_light_grey "$fixitfolder$book") for details"
            fi
        else
            # write "{date} :: Converted {book} in {elapsedtime_friendly}" to log file

            echo "$endtime_friendly :: $book :: Converted in $elapsedtime_friendly" >> "$logfile"
        fi

        # Make sure the m4b file was created
        if [ ! -f "$build_m4bfile" ]; then
            print_error "Error: m4b-tool failed to convert {{$book}}, no output file was found"
            ecko "Moving to fix folder → $(tint_path "$fixitfolder$book")"
            if [ "$(ensure_dir_exists_and_is_writable "$fixitfolder" "false")" != "1" ]; then
                mv_dir "$mergefolder$book" "$fixitfolder"
                cp "$logfile" "$fixitfolder$book/m4b-tool.$book.log"
                log_results "$book_full_path" "FAILED" ""
            fi
            continue
        fi

        # create outputfolder
        mkdir -p "$outputfolder$book" 2>/dev/null

        # Remove reserved filesystem chars from "$bitrate_friendly @ $samplerate_friendly" (replace kb/s with kbps)
        desc_quality=$(echo "$bitrate_friendly @ $samplerate_friendly" | sed 's/kb\/s/kbps/g')

        # Get size of new m4b file and append to description.txt file
        m4b_file_size=$(get_size "$build_m4bfile" "human")
        ecko "Converted size: $m4b_file_size" >> "$description_file"

        m4b_audio_duration=$(get_duration "$build_m4bfile" "human")
        ecko "Converted duration: $m4b_audio_duration" >> "$description_file"

        m4b_num_parts=1 # hardcode for now, until we know if we need to split parts

        # for ., $buildfolder$book, and $mergefolder$book, do:
            # found_desc=$(find {thedir} -type f -name "$book \[*kHz*\].txt" | head -n 1)
            # if [ -n "$found_desc" ]; then
            #     found_desc=$(basename "$found_desc")
            #     print_notice "Removing old description file - $found_desc"
            #     rm "{thedir}/$book \[*kHz*\].txt"
            # fi
        # end loop

        # Remove old description files from current dir, $buildfolder$book and $mergefolder$book
        did_remove_old_desc=false
        for dir in . "$buildfolder$book" "$mergefolder$book"; do
            find "$dir" -type f -name "$book \[*kHz*\].txt" | while read found_desc; do
                rm "$found_desc"
                did_remove_old_desc=true
            done
        done

        if [ "$did_remove_old_desc" = "true" ]; then
            print_notice "Removed old description file(s)"
        fi

        # Rename description.txt to $book-[$desc_quality].txt
        mv "$description_file" "$book [$desc_quality].txt"
        ecko "Finished in $elapsedtime_friendly"
        log_results "$book_full_path" "SUCCESS" "$elapsedtime_friendly"

        # Copy log file to output folder as $buildfolder$book/m4b-tool.$book.log
        mv "$logfile" "$book.m4b-tool.log"

        ecko "Moving to converted books folder → $(tint_path "$(split_path "$final_m4bfile" "" 35)")"

        ecko "Verifing id3 tags..."
        verify_id3_tags "$build_m4bfile"
        ecko

        # Move all built audio files to output folder
        find "$buildfolder$book" -maxdepth 1 -type f \( "${audio_exts[@]}" -o "${other_exts[@]}" \) -exec mv {} "$outputfolder$book/" \;
        # Copy other jpg, png, and txt files from mergefolder to output folder
        find "$mergefolder$book" -maxdepth 1 -type f \( "${other_exts[@]}" \) -exec mv {} "$outputfolder$book/" \;

        # Remove description.txt from output folder if "$book [$desc_quality].txt" exists
        if [ -f "$outputfolder$book/$book [$desc_quality].txt" ]; then
            rm "$outputfolder$book/description.txt"
        else # otherwise, warn that the description.txt file is missing
            print_notice "The description.txt is missing (reason unknown)"
        fi

        # Remove temp copy in merge
        rm -rf "$mergefolder$book" 2>/dev/null
        
        if [ "$on_complete" = "move" ]; then
            ecko "Archiving original from inbox..."

            mkdir -p "$donefolder$book" 2>/dev/null
            mv_dir "$inboxfolder$book" "$donefolder$book" "overwrite-silent"
            
            # delete all files in $inboxfolder$book that also exist in $outputfolder$book
            # delete all files in $inboxfolder$book that exist in $backupfolder$book
            # delete all files in $inboxfolder$book that are not in other_exts
            find "$inboxfolder$book" -maxdepth 1 -type f -type f \( "${audio_exts[@]}" -o "${other_exts[@]}" \) -exec basename {} \; | while IFS= read -r file; do
                if [ -f "$outputfolder$book/$file" ] || [ -f "$backupfolder$book/$file" ] || [ -f "$donefolder$book/$file" ]; then
                    rm "$inboxfolder$book/$file"
                fi
            done

        elif [ "$on_complete" = "delete" ]; then
            ecko "Deleting original from inbox..."
        fi

        if [ "$(ok_to_del "$inboxfolder$book")" = "true" ]; then
            rm -rf "$inboxfolder$book" 2>/dev/null
        fi

        # Check if for some reason this is still in the inbox and warn
        if [ -d "$inboxfolder$book" ]; then
            print_warning "Warning: $(tint_warning "$book") is still in the inbox folder, it should have been archived or deleted"
            print_orange "     To prevent this book from being converted again, move it out of the inbox folder"
        fi
        
        ecko "\nDone processing 🐾✨🥞\n"

        # cd back to inbox folder
        cd_inbox_folder
    done
        
    # clear the folders
    divider
    rm -r "$binfolder"* 2>/dev/null
    rm -r "$mergefolder"* 2>/dev/null
    rm -r "$buildfolder"* 2>/dev/null
    # Delete all *-tmpfiles dirs inside $outputfolder
    find "$buildfolder" -maxdepth 2 -type d -name "*-tmpfiles" -exec rm -rf {} \; 2>/dev/null

    if [[ "$books_count" -ge 1 ]]; then
        ecko "Finished converting all available books, next check in $sleeptime"
    else
        ecko "Next check in $sleeptime"
    fi
	divider
    ecko

    sleep $sleeptime
    exit 0 # uncomment this exit to have script restart after each run
done
