function is_code(title) {
    return length(title) >= 16 && title !~ /[^0-9A-Fa-f]/
}

function usable(title, id) {
    return title != "" && title != "unknown" && title != id && !is_code(title)
}

NR > 1 {
    date = $1
    id = $2
    seconds = $3 + 0
    raw_title = $4
    key = (id == "" || id == "unknown") ? id SUBSEP raw_title : id
    if (!(key in book_index)) {
        book_index[key] = ++book_count
        book_id[book_count] = id
    }
    book_no = book_index[key]
    if (!(book_no in title) || (!usable(title[book_no], id) && usable(raw_title, id))) {
        title[book_no] = raw_title
    }
    book_seconds[book_no] += seconds
    day_seconds[date] += seconds
    month_seconds[substr(date, 1, 7)] += seconds
    day_book_seconds[date SUBSEP book_no] += seconds
    total += seconds
    if (seconds > 0) read_date[date] = 1
}

END {
    for (date in read_date) read_days++
    print total + 0 "\t" read_days + 0 > summary
    for (month in month_seconds) print month "\t" month_seconds[month] + 0 > months
    for (date in day_seconds) print date "\t" day_seconds[date] + 0 > days
    for (book_no = 1; book_no <= book_count; book_no++) {
        name = title[book_no]
        id = book_id[book_no]
        if (!usable(name, id)) name = id
        print book_seconds[book_no] + 0 "\t" name "\t" id "\t" book_no > books
    }
    for (entry in day_book_seconds) {
        split(entry, part, SUBSEP)
        date = part[1]
        book_no = part[2]
        name = title[book_no]
        id = book_id[book_no]
        if (!usable(name, id)) name = id
        print date "\t" day_book_seconds[entry] + 0 "\t" name > daybooks
    }
}
