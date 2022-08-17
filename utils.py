
class PostVotes:
    def __init__(self, options: [str]):
        self.votes = dict()
        for option in options:
            self.votes[option] = list()

    def add_vote(self, option: str, vote_author: str, vote: str):
        assert option in self.votes
        self.votes[option].append((vote, vote_author))


def format_reply(line: str, prefix: str = "- ") -> str:
    line = line.replace("\n", " ⮒ ")
    return f"{prefix}{line}"
