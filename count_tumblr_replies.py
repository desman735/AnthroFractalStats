import json
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


def load_options(post_id):
    with open(f"options/{post_id}.json", "r", encoding="utf8") as options_file:
        return json.load(options_file)


def save_options(post_id, options):
    with open(f"options/{post_id}.json", "w", encoding="utf8") as options_file:
        json.dump(fp=options_file, obj=options, indent="\t", ensure_ascii=False)


def print_options(options):
    for option_number, option_variants in options.items():
        print(f"Option {option_number}:")
        for variant in option_variants:
            print(f"\t{format_reply(variant[0])}")


def get_post_options(tumblr_client, blogname, post_id):
    try:
        return load_options(post_id)
    except FileNotFoundError:
        request = tumblr_client.posts(blogname=blogname, id=post_id)
        assert len(request['posts']) == 1
        post_html = request['posts'][0]['caption']
        parser = PostCaptionParser()
        parser.feed(post_html)
        result = dict()
        extract_text_regex = re.compile(r"\W*")
        for index, option in enumerate(parser.options):
            option_number = str(index + 1)
            clean_option = extract_text_regex.sub("", option).casefold()
            result[option_number] = [
                (option_number, option_number),
                (option, clean_option),
                (f"{option_number}. {option}", option_number + clean_option),
            ]
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


print("Getting initial choices...")
options = get_post_options(client, blog, post_id)
print_options(options)
save_options(post_id, options)

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

if config.count_reblogs:
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
            if replies[reblog_author] == reblog_comment:
                continue
            replies[reblog_author] += "\n"
            replies[reblog_author] += reblog_comment
        else:
            replies[reblog_author] = reblog_comment
    print(f"{len(replies)} replies to handle")

print("\nCalculating results...")
extract_text_regex = re.compile(r"\W*")
defined_replies = dict()

for option_number, option_variants in options.items():
    defined_replies[option_number] = list()

for author, reply in replies.items():
    clean_reply = extract_text_regex.sub("", reply).casefold()
    for number, option_variants in options.items():
        defined_reply = False
        for variant in option_variants:
            if clean_reply == variant[1]:
                defined_replies[number].append((reply, author))
                defined_reply = True
                break
        if defined_reply:
            break
    else:
        reply_option = None
        while not reply_option:
            reply_option = input(f"What's the option for '{format_reply(reply)}'?")
            if reply_option in options:
                defined_replies[reply_option].append((reply, author))
                options[reply_option].append((reply, clean_reply))
            else:
                if reply_option != "0":
                    print(f"Option {reply_option} is not in options")
                    reply_option = None

print("\nUpdated choices:")
print_options(options)
save_options(post_id, options)

print("\nResults:")
for choice, replies in defined_replies.items():
    if replies:
        print(f'{choice}: {len(replies)}')
