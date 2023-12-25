#!/bin/bash

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

    rows=$(echo "$table" | grep -o '<tr>.*</tr>')
    for row in $rows; do
        columns=$(echo "$row" | grep -o '<td>.*</td>')
        if [[ -n "$columns" ]]; then
            first_column=$(echo "$columns" | head -n 1)
            link=$(echo "$first_column" | grep -o '<a.*</a>')
            if [[ -n "$link" ]]; then
                link_text=$(echo "$link" | grep -o 'href=".*"' | cut -d '"' -f 2 | sed 's:/$::')
                full_url=$(echo "$link" | grep -o 'href=".*"' | cut -d '"' -f 2 | sed 's:^/::')
                result="${link_text##*/}=$full_url"
                if [[ "$full_url" == *"#"+suid* ]]; then
                    results+=("$result")
                fi
            fi
        fi
    done

    echo "${results[@]}"
}

scrape_bin_table() {
    url=$1
    full_url="$url#+suid"
    soup=$(curl -s "$full_url")
    if [[ -z "$soup" ]]; then
        return
    fi

    bin_table=$(echo "$soup" | grep -o '<table id="bin-table">.*</table>')
    if [[ -n "$bin_table" ]]; then
        results=$(get_links_from_table "$full_url" "$bin_table")
        echo "$results"
    else
        echo "Error: Table with id 'bin-table' not found on $full_url"
    fi
}

find_setuid_setgid_files() {
    files=()
    while IFS= read -r -d '' file_path; do
        if [[ -f "$file_path" && $(( $(stat -c "%a" "$file_path") & 0o6000 )) -ne 0 ]]; then
            files+=("$file_path")
        fi
    done < <(find / -type f -print0 2>/dev/null)
    echo "${files[@]}"
}

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
There is nothing here :("
            fi
        else
            echo "
---------------------------------------------
There is nothing here :("
        fi
    else
        echo "
---------------------------------------------
There is nothing here :("
    fi
}

main
