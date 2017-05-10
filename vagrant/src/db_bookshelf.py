#!/usr/bin/env python

"""Run this module to initialise the SQLite database `bookshelf.db`."""
import sys
from sqlalchemy import Column, ForeignKey, Integer, String, Date
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy import create_engine

DB_NAME = "bookshelf"
Base = declarative_base()
engine = create_engine("sqlite:///" + sys.path[0] + "/{}.db".format(DB_NAME))


"""Basic classes for bookshelf: Topic, Author, Book.

Note that those tables are not linked together, since they have a
many-to-many relationship. Examples:
    - Book "Data Vis with Python and JS" belongs to topics "Python" and
        "JavaScript" and those topics can contains many others books
    - Books can have multiple authors and those might have written multiple
        books

References between those tables are achieved via `BookTopic` and `BookAuthor`.
"""


class Topic(Base):
    __tablename__ = "topic"

    id = Column(Integer, primary_key=True)
    name = Column(String(80), nullable=False)
    slug = Column(String(80), nullable=False)


class Author(Base):
    __tablename__ = "author"

    id = Column(Integer, primary_key=True)
    name = Column(String(80), nullable=False)


class Book(Base):
    __tablename__ = "book"

    id = Column(Integer, primary_key=True)
    title = Column(String(80), nullable=False)
    pub_date = Column(Date, nullable=False)
    slug = Column(String(80), nullable=False)
    isbn = Column(String(13), nullable=False)
    description = Column(String(250))

    def serialize(self):
        return {
            "title": self.title,
            "isbn": self.isbn,
            "description": self.description,
            "publication_date": self.pub_date.strftime("%B %Y")
        }


"""Since we have a many:many relationship between topics and books as well
as authors and books, we need junction tables to handle those references.

For more information see, Wikipedia:
    - https://en.m.wikipedia.org/wiki/Many-to-many_(data_model)
"""


# m:n relationship between `Book` and `Topic`
class BookTopic(Base):
    __tablename__ = "book_topic"

    book_id = Column(Integer, ForeignKey("book.id"), primary_key=True)
    topic_id = Column(Integer, ForeignKey("topic.id"), primary_key=True)
    book = relationship(Book)
    topic = relationship(Topic)


# m:n relationship between `Book` and `Author`
class BookAuthor(Base):
    __tablename__ = "book_author"

    book_id = Column(Integer, ForeignKey("book.id"), primary_key=True)
    author_id = Column(Integer, ForeignKey("author.id"), primary_key=True)
    book = relationship(Book)
    author = relationship(Author)


def init_db():
    Base.metadata.create_all(engine)


if __name__ == "__main__":
    init_db()
