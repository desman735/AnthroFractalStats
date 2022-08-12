from dynaconf import Dynaconf
from tumblr import TumblrCounter

CONFIG = Dynaconf(
    settings_files=[
        "config.toml"
    ]
)

TUMBLR_COUNTER = TumblrCounter(config=CONFIG.tumblr)
TUMBLR_POST = TUMBLR_COUNTER.get_post_by_config()
VOTES = TUMBLR_POST.count_votes()

print("\nTumblr: " + ", ".join(
    [
        f'{OPTION} - {len(OPTION_VOTES)}'
        for OPTION, OPTION_VOTES in VOTES.votes.items()
        if OPTION_VOTES and OPTION != "0"
    ]
))
