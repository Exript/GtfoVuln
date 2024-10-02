#!/bin/bash

# ASCII header
print_header() {
    ascii_art="
       ___________              .__        __    
       \_   _____/__  __________|__|______/  |_  
        |    __)_\  \/  /\_  __ \  \____ \   __\ 
        |        \>    <  |  | \/  |  |_> >  |   
       /_______  /__/\_ \ |__|  |__|   __/|__|   
               \/      \/          |__|          
    "
    echo "$ascii_art"
}

get_links_from_table() {
    url=$1
    table=$2
    results=()

    # table row
    rows=$(echo "$table" | grep -oP '(?<=<tr>).*?(?=</tr>)')
    for row in $rows; do
        # table colmn
        columns=$(echo "$row" | grep -oP '(?<=<td>).*?(?=</td>)')
        if [[ -n "$columns" ]]; then
            first_column=$(echo "$columns" | head -n 1)
            # link
            link=$(echo "$first_column" | grep -oP '(?<=href=").*?(?=")')
            if [[ -n "$link" ]]; then
                # if suit
                if [[ "$link" == *"#suid"* ]]; then
                    bin_name=$(basename "$link")
                    results+=("$bin_name=$url$link")
                fi
            fi
        fi
    done

    echo "${results[@]}"
}

# GTFObins  SUID/SGID exploit binary
scrape_bin_table() {
    url=$1
    full_url="$url#+suid"
    soup=$(curl -s "$url")
    if [[ -z "$soup" ]]; then
        return
    fi

    bin_table=$(echo "$soup" | grep -oP '(?<=<table id="bin-table">).*?(?=</table>)')
    if [[ -n "$bin_table" ]]; then
        results=$(get_links_from_table "$url" "$bin_table")
        echo "$results"
    else
        echo "Error: Table with id 'bin-table' not found on $url"
    fi
}

#  SetUID and SetGID file controll
find_setuid_setgid_files() {
    files=()
    while IFS= read -r -d '' file_path; do
        # SUID or SGID setting file 
        if [[ -f "$file_path" && $(stat -c "%A" "$file_path") =~ [sS] ]]; then
            files+=("$file_path")
        fi
    done < <(find / -type f \( -perm -4000 -o -perm -2000 \) -print0 2>/dev/null)
    echo "${files[@]}"
}

# main func
main() {
    print_header

    url="https://gtfobins.github.io/"
    bin_links=$(scrape_bin_table "$url")

    if [[ -n "$bin_links" ]]; then
        setuid_setgid_files=$(find_setuid_setgid_files)

        if [[ -n "$setuid_setgid_files" ]]; then
            matches=()
            max_bin_length=0
            for link_info in $bin_links; do
                bin_name=$(echo "$link_info" | cut -d '=' -f 1)
                bin_url=$(echo "$link_info" | cut -d '=' -f 2)
                if [[ -n "$bin_name" && -n "$bin_url" ]]; then
                    length=${#bin_name}
                    if (( length > max_bin_length )); then
                        max_bin_length=$length
                    fi
                    for file_path in $setuid_setgid_files; do
                        if [[ "$(basename "$file_path")" == "$bin_name" ]]; then
                            matches+=("$bin_name=$bin_url")
                        fi
                    done
                fi
            done

            if [[ ${#matches[@]} -gt 0 ]]; then
                echo "
Gotchu SUID
-----------------"
                for match in "${matches[@]}"; do
                    bin_name=$(echo "$match" | cut -d '=' -f 1)
                    bin_url=$(echo "$match" | cut -d '=' -f 2)
                    printf "%-${max_bin_length}s -------> %s\n" "$bin_name" "$bin_url"
                done
                echo "
Happy Hack Day ^-^"
            else
                echo "
---------------------------------------------
No exploitable SUID binaries found :("
            fi
        else
            echo "
---------------------------------------------
No SUID/SGID files found on the system."
        fi
    else
        echo "
---------------------------------------------
Error fetching data from GTFObins."
    fi
}

main
