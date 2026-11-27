def unescape(s: str) -> str:
    metacharacters = "{}()+-.*?^$[]\\"
    result = []
    i = 0

    while i < len(s):
        char = s[i]
        if char == "\\" and i + 1 < len(s):
            following = s[i + 1]
            if following in metacharacters or following.isspace():
                result.append(following)
                i += 2
                continue
        result.append(char)
        i += 1

    return "".join(result)
