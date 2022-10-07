import json
import os

from sqlalchemy.orm import Session

from database.models import Page, VoteOption, VoteAlias, TumblrPost
from database.helper import VotesDatabase

db = VotesDatabase(echo=True)

for file_name in os.listdir("data"):
    if not file_name.endswith(".json"):
        continue
    with open(f"data/{file_name}", "r", encoding="utf8") as options_file:
        options = json.load(options_file)
        post_id = int(file_name.split(".")[0])
        page = Page()
        post = TumblrPost(post_id=post_id, page=page)
        for vote_index, vote_options in options.items():
            vote_index = int(vote_index)
            vote_text: str
            if vote_index == 0:
                vote_text = "Not a vote"
            else:
                vote_text = vote_options[1][0]
                vote_text = vote_text.replace('\n', '')
                vote_text = vote_text.replace('“', '')
                vote_text = vote_text.replace('”', '')
            vote_option = VoteOption(vote_index=vote_index, full_text=vote_text, page=page)
            for option_text in vote_options:
                # skip trivial aliases
                if option_text[1] in ['1', '2', '3', '4']:
                    continue
                alias = VoteAlias(vote_text=option_text[0], compare_text=option_text[1], vote=vote_option)
        with db.create_session() as session:
            session.add(page)
            session.commit()
