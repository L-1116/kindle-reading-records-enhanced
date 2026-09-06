function is_code(title) {
    return length(title) >= 16 && title !~ /[^0-9A-Fa-f]/
}

function usable(title, id) {
    return title != "" && title != "unknown" && title != id && !is_code(title)
}

# Gregorian date -> Julian day number.  Keeping this in the one-pass cache
# builder avoids depending on GNU date features that are not guaranteed on
# Kindle's BusyBox userspace.
function day_number(date,    y, m, d, a, yy, mm) {
    if (date !~ /^[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]$/) return -1
    y = substr(date, 1, 4) + 0
    m = substr(date, 6, 2) + 0
    d = substr(date, 9, 2) + 0
    if (m < 1 || m > 12 || d < 1 || d > 31) return -1
    a = int((14 - m) / 12)
    yy = y + 4800 - a
    mm = m + 12 * a - 3
    return d + int((153 * mm + 2) / 5) + 365 * yy + int(yy / 4) - int(yy / 100) + int(yy / 400) - 32045
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
    today_day = day_number(today)
    today_weekday = today_day % 7 # Monday=0
    print today_day > calendar
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
        seconds = day_book_seconds[entry] + 0
        name = title[book_no]
        id = book_id[book_no]
        if (!usable(name, id)) name = id
        print date "\t" seconds "\t" name > daybooks

        date_day = day_number(date)
        age = today_day - date_day
        if (today_day >= 0 && date_day >= 0 && age >= 0) {
            if (age <= 6) range_7d[book_no] += seconds
            if (age <= today_weekday) range_week[book_no] += seconds
            if (substr(date, 1, 7) == substr(today, 1, 7)) range_month[book_no] += seconds
            if (substr(date, 1, 4) == substr(today, 1, 4)) range_year[book_no] += seconds
        }
    }
    for (book_no = 1; book_no <= book_count; book_no++) {
        name = title[book_no]
        id = book_id[book_no]
        if (!usable(name, id)) name = id
        if (book_no in range_7d) print range_7d[book_no] + 0 "\t" name "\t" id "\t" book_no > books7
        if (book_no in range_week) print range_week[book_no] + 0 "\t" name "\t" id "\t" book_no > booksweek
        if (book_no in range_month) print range_month[book_no] + 0 "\t" name "\t" id "\t" book_no > booksmonth
        if (book_no in range_year) print range_year[book_no] + 0 "\t" name "\t" id "\t" book_no > booksyear
    }
    for (date in day_seconds) {
        date_day = day_number(date)
        if (date_day >= 0) {
            monday = date_day - (date_day % 7)
            week_seconds[monday] += day_seconds[date]
        }
    }
    for (monday in week_seconds) print monday "\t" week_seconds[monday] + 0 > weeks
}
