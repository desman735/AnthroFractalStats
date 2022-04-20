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
        self.option_regex = re.compile(r"\d\) ")

    def handle_starttag(self, tag, attrs):
        if tag == 'ol':
            assert not self.handled_list
            self.handled_list = True
        elif tag == 'li':
            self.inside_list_option = True

    def handle_endtag(self, tag):
        if tag == 'li':
            self.inside_list_option = False
        elif tag == "p":
            assert len(self.options) >= 2

    def handle_data(self, data):
        if self.inside_list_option:
            self.options.append(data)
        elif self.option_regex.match(data):
            self.options.append(data[3:])


class PostOptions:

    def __init__(self, post) -> None:
        self.post_id = post['id']
        self.extract_text_regex = re.compile(r"\W*")
        try:
            self.load_saved_options()
        except FileNotFoundError:
            post_html = post['caption']
            parser = PostCaptionParser()
            parser.feed(post_html)

            self.options = dict()
            self.options["0"] = list()

            for index, option_text in enumerate(parser.options):
                option_number = str(index + 1)
                clean_option = self.extract_text_regex.sub("", option_text).casefold()
                self.options[option_number] = [
                    (option_number, option_number),
                    (option_text, clean_option),
                    (f"{option_number}. {option_text}", option_number + clean_option),
                ]

            self.save_current_options()

    def load_saved_options(self):
        with open(f"options/{self.post_id}.json", "r", encoding="utf8") as options_file:
            self.options = json.load(options_file)

    def save_current_options(self):
        # Default "0" and at least two choices
        assert len(self.options) >= 3
        with open(f"options/{self.post_id}.json", "w", encoding="utf8") as options_file:
            json.dump(fp=options_file, obj=self.options, indent="\t", ensure_ascii=False)

    def print_current_options(self):
        for option_number, option_variants in self.options.items():
            if option_number == "0":
                continue
            print(f"Option {option_number}:")
            for variant in option_variants:
                print(f"\t{format_reply(variant[0])}")

    def get_options(self):
        return self.options.keys()

    def get_option_for_reply(self, reply):
        clean_reply = self.extract_text_regex.sub("", reply).casefold()
        for number, option_variants in self.options.items():
            for variant in option_variants:
                if clean_reply == variant[1]:
                    return number
        else:
            reply_option = None
            while not reply_option:
                reply_option = input(f"What's the option for '{format_reply(reply)}'?")
                if reply_option in self.options:
                    self.options[reply_option].append((reply, clean_reply))
                    self.save_current_options()
                    return reply_option
                else:
                    print(f"Option {reply_option} is not in options")
                    reply_option = None


class PostNotes:

    def __init__(self, tumblr_client, post_link, mode="conversation") -> None:
        self.client = tumblr_client
        self.notes_request_mode = mode

        post = post_link.removeprefix("https://")
        self.blog, post = post.split('/', 1)

        post = post.removeprefix("post/")
        self.post_id = post.split('/')[0]

        self.initial_post = None
        self.cache_initial_post()
        assert self.initial_post

        self.cached_notes = list()
        self.cache_post_notes()
        assert len(self.cached_notes) > 0

    def cache_post_notes(self):
        notes = self.client.notes(
            blogname=self.blog,
            id=self.post_id,
            mode=self.notes_request_mode,
        )
        for note in notes['notes']:
            self.cached_notes.append(note)

        while '_links' in notes:
            assert 'next' in notes['_links']
            next_link = notes['_links']['next']
            notes = self.client.notes(
                blogname=self.blog,
                **next_link['query_params']
            )
            for note in notes['notes']:
                self.cached_notes.append(note)

    def cache_initial_post(self):
        request = self.client.posts(blogname=self.blog, id=self.post_id)
        assert len(request['posts']) == 1
        self.initial_post = request['posts'][0]

    def filter_notes(self, filter_type):
        assert len(self.cached_notes) > 0
        for note in self.cached_notes:
            if not filter_type or note['type'] == filter_type:
                yield note


def format_reply(line: str) -> str:
    line = line.replace("\n", " ⮒ ")
    return f'- {line}'


CONFIG = Dynaconf(
    settings_files=[
        "config.toml"
    ]
)

CLIENT = TumblrRestClient(CONFIG.tumblr_key)

print("Getting post notes...")
NOTES = PostNotes(CLIENT, CONFIG.tumblr_post_link)
print(f"Cached {len(NOTES.cached_notes)} notes ({NOTES.notes_request_mode} mode)")

print("Getting initial choices...")
OPTIONS = PostOptions(NOTES.initial_post)
OPTIONS.print_current_options()

REPLIES = dict()
print("\nCounting replies...")
for REPLY in NOTES.filter_notes(filter_type='reply'):
    REPLY_AUTHOR = REPLY['blog_name']
    REPLY_TEXT = REPLY['reply_text']

    if REPLY_AUTHOR in REPLIES:
        if REPLIES[REPLY_AUTHOR] == REPLY_TEXT:
            continue
        REPLIES[REPLY_AUTHOR] += "\n"
        REPLIES[REPLY_AUTHOR] += REPLY_TEXT
    else:
        REPLIES[REPLY_AUTHOR] = REPLY_TEXT
print(f"{len(REPLIES)} replies to handle")

if CONFIG.count_reblogs:
    print("\nCounting reblogs...")
    for REBLOG_NOTE in NOTES.filter_notes(filter_type='reblog'):
        REBLOG_AUTHOR = REBLOG_NOTE['blog_name']
        REBLOG_POST_ID = REBLOG_NOTE['post_id']
        POSTS = CLIENT.posts(blogname=f"{REBLOG_AUTHOR}.tumblr.com", id=REBLOG_POST_ID)
        if 'posts' not in POSTS:
            assert POSTS['meta']['status'] == 404
            print(f'Failed to get reblog text from {REBLOG_AUTHOR}')
            continue
        REBLOGS = POSTS['posts']
        assert len(REBLOGS) == 1
        REBLOG_POST = REBLOGS[0]
        REBLOG_COMMENT = REBLOG_POST['reblog']['comment']
        if not REBLOG_COMMENT:
            continue
        REBLOG_COMMENT: str
        assert REBLOG_COMMENT.startswith("<p>")
        assert REBLOG_COMMENT.endswith("</p>")
        REBLOG_COMMENT = REBLOG_COMMENT[3:-4]
        if REBLOG_AUTHOR in REPLIES:
            if REPLIES[REBLOG_AUTHOR] == REBLOG_COMMENT:
                continue
            REPLIES[REBLOG_AUTHOR] += "\n"
            REPLIES[REBLOG_AUTHOR] += REBLOG_COMMENT
        else:
            REPLIES[REBLOG_AUTHOR] = REBLOG_COMMENT
    print(f"{len(REPLIES)} replies to handle")

print("\nCalculating results...")
DEFINED_REPLIES = dict()

for OPTION in OPTIONS.get_options():
    DEFINED_REPLIES[OPTION] = list()

for AUTHOR, REPLY in REPLIES.items():
    REPLY_OPTION = OPTIONS.get_option_for_reply(REPLY)
    DEFINED_REPLIES[REPLY_OPTION].append((REPLY, AUTHOR))

print("\nUpdated choices:")
OPTIONS.print_current_options()

print("\nTumblr: " + ", ".join(
    [
        f'{OPTION} - {len(REPLIES)}'
        for OPTION, REPLIES in DEFINED_REPLIES.items()
        if REPLIES and OPTION != "0"
    ]
))
