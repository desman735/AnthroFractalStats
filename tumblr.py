import json
import re
from html.parser import HTMLParser

from pytumblr import TumblrRestClient

from utils import format_reply, PostVotes


class PostCaptionParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.options = list()
        self.current_option = 0
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
            self.current_option += 1

    def handle_data(self, data):
        if self.inside_list_option:
            try:
                self.options[self.current_option] += data
            except IndexError:
                self.options.append(data)
        elif self.option_regex.match(data):
            self.options.append(data[3:])


class PostOptions:

    def __init__(self, post) -> None:
        self.__post_id = post['id']
        self.__extract_text_regex = re.compile(r"\W*")
        try:
            self.__load_saved_options()
        except FileNotFoundError:
            post_html = post['caption']
            parser = PostCaptionParser()
            parser.feed(post_html)
            assert(len(parser.options) >= 2)

            self.__options = dict()
            self.__options["0"] = list()

            for index, option_text in enumerate(parser.options):
                option_number = str(index + 1)
                clean_option = self.__extract_text_regex.sub("", option_text).casefold()
                self.__options[option_number] = [
                    (option_number, option_number),
                    (option_text, clean_option),
                    (f"{option_number}. {option_text}", option_number + clean_option),
                ]

            self.__save_current_options()

    def __load_saved_options(self):
        with open(f"data/{self.__post_id}.json", "r", encoding="utf8") as options_file:
            self.__options = json.load(options_file)

    def __save_current_options(self):
        # Default "0" and at least two choices
        assert len(self.__options) >= 3
        with open(f"data/{self.__post_id}.json", "w", encoding="utf8") as options_file:
            json.dump(fp=options_file, obj=self.__options, indent="\t", ensure_ascii=False)

    def print_current_options(self):
        for option_number, option_variants in self.__options.items():
            if option_number == "0":
                continue
            print(f"Option {option_number}:")
            for variant in option_variants:
                print(f"\t{format_reply(variant[0])}")

    @property
    def options(self):
        return self.__options.keys()

    def get_option_for_reply(self, reply):
        clean_reply = self.__extract_text_regex.sub("", reply).casefold()
        for number, option_variants in self.__options.items():
            for variant in option_variants:
                if clean_reply == variant[1]:
                    return number
        else:
            reply_option = None
            while not reply_option:
                reply_option = input(f"What's the option for '{format_reply(reply)}'?")
                if reply_option in self.__options:
                    self.__options[reply_option].append((reply, clean_reply))
                    self.__save_current_options()
                    return reply_option
                else:
                    print(f"Option {reply_option} is not in options")
                    reply_option = None


class PostNotes:

    def __init__(self, tumblr_client: TumblrRestClient, post: dict, mode: str = "conversation") -> None:
        self.client = tumblr_client
        self.notes_request_mode = mode
        self.post = post

        self.cached_notes = list()
        self.__cache_post_notes()
        assert len(self.cached_notes) > 0

    def __cache_post_notes(self):
        post_blog = self.post['blog_name']
        post_id = self.post['id_string']
        notes = self.client.notes(
            blogname=post_blog,
            id=post_id,
            mode=self.notes_request_mode,
        )
        for note in notes['notes']:
            self.cached_notes.append(note)

        while '_links' in notes:
            assert 'next' in notes['_links']
            next_link = notes['_links']['next']
            notes = self.client.notes(
                blogname=post_blog,
                **next_link['query_params']
            )
            for note in notes['notes']:
                self.cached_notes.append(note)

    def filter_notes(self, filter_type):
        assert len(self.cached_notes) > 0
        for note in self.cached_notes:
            if not filter_type or note['type'] == filter_type:
                yield note


class TumblrPost:
    @property
    def post_link(self):
        return self.post['post_url']

    def __init__(self, client: TumblrRestClient, post: dict):
        self.post = post
        self.votes = None
        self.__client = client

        print("Getting initial choices...")
        self.options = PostOptions(post)
        self.options.print_current_options()

    def count_votes(self, reset_cache: bool = False):
        if self.votes and not reset_cache:
            return self.votes

        notes = PostNotes(self.__client, self.post)
        print(f"Cached {len(notes.cached_notes)} notes for post {self.post_link} "
              f"({notes.notes_request_mode} mode)")

        self.votes = PostVotes(self.options.options)
        replies = dict()

        print("\nCounting votes...")
        for reply in notes.filter_notes(filter_type='reply'):
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

        print("\nCalculating results...")
        for author, reply in replies.items():
            reply_option = self.options.get_option_for_reply(reply)
            self.votes.add_vote(reply_option, author, reply)

        print("\nUpdated choices:")
        self.options.print_current_options()

        return self.votes


class TumblrCounter:

    def __init__(self, config):
        self.config = config
        self.client = TumblrRestClient(config.key)

    def get_post_by_config(self) -> TumblrPost:
        print("Getting post...")
        if "post_link" in self.config and self.config.post_link:
            return self.get_post_by_link(self.config.post_link)
        else:
            return self.get_latest_post(self.config.blog)

    def get_post_by_link(self, link: str) -> TumblrPost:
        blog, post_id = self.__get_post_info_from_link(link)
        request = self.client.posts(blogname=blog, id=post_id)
        assert len(request['posts']) == 1
        post = request['posts'][0]
        return TumblrPost(self.client, post)

    def get_latest_post(self, blog: str) -> TumblrPost:
        request = self.client.posts(blogname=blog)
        assert len(request['posts']) > 0
        post = request['posts'][0]
        return TumblrPost(self.client, post)

    @staticmethod
    def __get_post_info_from_link(link: str) -> [str, str]:
        post = link.removeprefix("https://")
        blog, post = post.split('/', 1)
        post = post.removeprefix("post/")
        return blog, post.split('/')[0]
