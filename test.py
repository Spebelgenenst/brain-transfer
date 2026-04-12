def extract_video(url):
    start = url.find("v=") + 2
    end = url.find("&")
    print(end)
    print(end if end != -1 else None)
    return url[start:end if end != -1 else None]

print(extract_video("https://www.youtube.com/watch?v=dQw4w9WgXcQ"))