import re

from dynaconf import Dynaconf
from pytumblr import TumblrRestClient


def notes_iter(tumblr_client, blogname, notes_post_id, filter_type):
    notes = tumblr_client.notes(blogname=blogname, id=notes_post_id)
    total_notes = notes['total_notes']
    handled_notes = 0
    while handled_notes < total_notes:
        for note in notes['notes']:
            last_handled_timestamp = note['timestamp']
            if note['type'] == filter_type:
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

replies = dict()

print("Counting replies...")
for reply in notes_iter(client, blog, post_id, 'reply'):
    reply_author = reply['blog_name']
    reply_text = reply['reply_text']

    if reply_author in replies:
        replies[reply_author] += "\n"
        replies[reply_author] += reply_text
    else:
        replies[reply_author] = reply_text

print("Counting reblogs...")
for reblog_note in notes_iter(client, blog, post_id, 'reblog'):
    reblog_author = reblog_note['blog_name']
    reblog_post_id = reblog_note['post_id']
    posts = client.posts(blogname=f"{reblog_author}.tumblr.com", id=reblog_post_id)
    if 'posts' not in posts:
        assert posts['meta']['status'] == 404
        continue
    reblogs = posts['posts']
    assert len(reblogs) == 1
    reblog_post = reblogs[0]
    reblog_comment = reblog_post['reblog']['comment']
    if reblog_comment:
        if reblog_author in replies:
            replies[reblog_author] += "\n"
            replies[reblog_author] += reblog_comment
        else:
            replies[reblog_author] = reblog_comment

print("Calculating results...")
choices = config.choices
regexes = dict()
defined_replies = dict()
undefined_replies = []

for name, keywords in choices.items():
    defined_replies[name] = list()
    for keyword in keywords:
        assert keyword not in regexes
        regexes[keyword] = re.compile(rf"\b{keyword}\b", re.IGNORECASE)

for author, reply in replies.items():
    reply_options = list()
    for name, keywords in choices.items():
        for keyword in keywords:
            if regexes[keyword].search(reply):
                reply_options.append(name)
                break

    if len(reply_options) == 1:
        defined_replies[reply_options[0]].append((reply, author))
    else:
        undefined_replies.append((reply, author))


print("Results:")
for choice, replies in defined_replies.items():
    if replies:
        print(f'{choice}: {len(replies)}')

if undefined_replies:
    print("\nUndefined replies:")
    for reply, author in undefined_replies:
        print(f"{author}:\n{format_reply(reply)}\n")
