import re
from html.parser import HTMLParser

from dynaconf import Dynaconf
from pytumblr import TumblrRestClient


class PostCaptionParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.options = list()
        self.handled_list = False
        self.inside_list_option = False

    def handle_starttag(self, tag, attrs):
        if tag == 'ol':
            assert not self.handled_list
            self.handled_list = True
        if tag == 'li':
            self.inside_list_option = True

    def handle_endtag(self, tag):
        if tag == 'li':
            self.inside_list_option = False

    def handle_data(self, data):
        if self.inside_list_option:
            self.options.append(data)


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


def get_post_options(tumblr_client, blogname, post_id):
    request = tumblr_client.posts(blogname=blogname, id=post_id)
    assert len(request['posts']) == 1
    post_html = request['posts'][0]['caption']
    parser = PostCaptionParser()
    parser.feed(post_html)
    result = dict()
    for index, option in enumerate(parser.options):
        result[str(index + 1)] = option
    return result


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


print("Getting choices...")
options = get_post_options(client, blog, post_id)
for option_number, option_text in options.items():
    print(f"Choice {option_number}: {option_text}")

print("\nCounting replies...")
for reply in notes_iter(client, blog, post_id, 'reply'):
    reply_author = reply['blog_name']
    reply_text = reply['reply_text']

    if reply_author in replies:
        if replies[reply_author] == reply_text:
            continue
        replies[reply_author] += "\n"
        replies[reply_author] += reply_text
    else:
        replies[reply_author] = reply_text
print(f"{len(replies)} replies to handle")

print("\nCounting reblogs...")
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
    if not reblog_comment:
        continue
    reblog_comment: str
    assert reblog_comment.startswith("<p>")
    assert reblog_comment.endswith("</p>")
    reblog_comment = reblog_comment[3:-4]
    if reblog_author in replies:
        if replies[reply_author] == reply_text:
            continue
        replies[reblog_author] += "\n"
        replies[reblog_author] += reblog_comment
    else:
        replies[reblog_author] = reblog_comment
print(f"{len(replies)} replies to handle")

print("\nCalculating results...")
regexes = dict()
defined_replies = dict()
undefined_replies = []

for number, option_text in options.items():
    defined_replies[number] = list()
    assert number not in regexes
    regexes[number] = re.compile(rf"\W*{number}\W*", re.IGNORECASE)
    assert option_text not in regexes
    regexes[option_text] = re.compile(rf"\W*{option_text}\W*", re.IGNORECASE)

for author, reply in replies.items():
    reply_options = list()
    for number, option_text in options.items():
        if regexes[number].fullmatch(reply):
            defined_replies[number].append((reply, author))
            break
        if regexes[option_text].fullmatch(reply):
            defined_replies[number].append((reply, author))
            break
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
