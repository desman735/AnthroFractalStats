from sqlalchemy import Column, Integer, String, ForeignKey, BigInteger
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Page(Base):
    __tablename__ = "pages"

    id = Column(Integer, primary_key=True)

    vote_options = relationship("VoteOption", back_populates="page")
    tumblr_post = relationship("TumblrPost", back_populates="page", uselist=False)

    def __repr__(self):
        return f"Page {id!r}"


class VoteOption(Base):
    __tablename__ = "vote_options"

    id = Column(Integer, primary_key=True)
    vote_index = Column(Integer)  # goes from 0 to 4, 0 - invalid option
    full_text = Column(String)  # just for readability

    page_id = Column(Integer, ForeignKey(Page.id))
    page = relationship(Page, back_populates="vote_options")

    aliases = relationship("VoteAlias", back_populates="vote")

    def __repr__(self):
        return f"Vote {self.vote_index!r}: '{self.full_text!r}'"


class VoteAlias(Base):
    __tablename__ = "vote_aliases"

    id = Column(Integer, primary_key=True)
    vote_text = Column(String)  # human-readable alias text
    compare_text = Column(String)  # alias text, optimised for comparison

    vote_id = Column(Integer, ForeignKey(VoteOption.id))
    vote = relationship(VoteOption, back_populates="aliases")

    def __repr__(self):
        return f"'{self.vote_text!r}'"


class TumblrPost(Base):
    __tablename__ = "tumblr_posts"

    post_id = Column(BigInteger, primary_key=True)

    page_id = Column(Integer, ForeignKey(Page.id))
    page = relationship(Page, back_populates="tumblr_post")

    def __repr__(self):
        return f"Post ({self.post_id!r}) for page {self.page_id!r}"
