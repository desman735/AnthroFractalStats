import sys
from pytumblr import TumblrRestClient

key = sys.argv[1]
post = sys.argv[2]
post = post.removeprefix("https://")
blog, post = post.split('/', 1)
post = post.removeprefix("post/")
post_id = post.split('/')[0]

client = TumblrRestClient(key)
notes = client.notes(blogname=blog, id=post_id)
total_notes = notes['total_notes']
handled_notes = 0

replies = dict()
replies_authors = set()
ignored_authors = set()


def format_reply(line: str) -> str:
    line = line.replace("\n", " ⮒ ")
    return f'"{line}"'


while handled_notes < total_notes:
    for note in notes['notes']:
        last_handled_timestamp = note['timestamp']
        if note['type'] != 'reply':
            continue

        reply_author = note['blog_name']
        reply_text = note['reply_text']

        if reply_text not in replies:
            replies[reply_text] = set()
        replies[reply_text].add(reply_author)

        if reply_author in replies_authors:
            ignored_authors.add(reply_author)

        replies_authors.add(reply_author)

    handled_notes += len(notes['notes'])
    if handled_notes < total_notes:
        notes = client.notes(blogname=blog, id=post_id, before_timestamp=last_handled_timestamp)

ignored_replies = {}

# remove people, who answered few times, from the replies
for reply, authors in replies.items():
    authors: list

    for author in ignored_authors:
        if author in authors:
            authors.remove(author)

            if author not in ignored_replies:
                ignored_replies[author] = set()
            ignored_replies[author].add(reply)

print("Results:")
for reply, authors in sorted(replies.items(), key=lambda reply_data: len(reply_data[1]), reverse=True):
    if authors:
        print(f'{len(authors)} - {format_reply(reply)}')

print("\nIgnored authors:")
for author, replies in ignored_replies.items():
    replies = '\n'.join(map(format_reply, replies))
    print(f"{author}:\n{replies}\n")
