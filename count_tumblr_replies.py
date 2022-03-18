from dynaconf import Dynaconf
from pytumblr import TumblrRestClient


def reply_iter(notes):
    total_notes = notes['total_notes']
    handled_notes = 0
    while handled_notes < total_notes:
        for note in notes['notes']:
            last_handled_timestamp = note['timestamp']
            if note['type'] != 'reply':
                continue
            yield note

        handled_notes += len(notes['notes'])
        if handled_notes < total_notes:
            notes = client.notes(blogname=blog, id=post_id, before_timestamp=last_handled_timestamp)


def format_reply(line: str) -> str:
    line = line.replace("\n", " ⮒ ")
    return f'"{line}"'


config = Dynaconf(
    settings_files=[
        "config.toml"
    ]
)

key = config.tumblr_key
post = config.tumblr_post_link

post = post.removeprefix("https://")
blog, post = post.split('/', 1)
post = post.removeprefix("post/")
post_id = post.split('/')[0]

client = TumblrRestClient(key)
post_notes = client.notes(blogname=blog, id=post_id)

replies = dict()
replies_authors = set()
ignored_authors = set()

for reply in reply_iter(post_notes):
    reply_author = reply['blog_name']
    reply_text = reply['reply_text']

    if reply_text not in replies:
        replies[reply_text] = set()
    replies[reply_text].add(reply_author)

    if reply_author in replies_authors:
        ignored_authors.add(reply_author)

    replies_authors.add(reply_author)

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
