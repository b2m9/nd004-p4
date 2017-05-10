#!/usr/bin/env python
import json
import sys
from sqlalchemy.orm import sessionmaker
from datetime import date
from helper import get_slug
from db_bookshelf import (
    Topic, Book, Author, BookTopic, BookAuthor, User, engine
)


def prepopulate_db():
    """Prepopulates database connected to `bookshelf_db.engine`.

    Parse `json_file` and load content into `engine`.
    Create references in the junction tables `book_author` and `book_topic` if
    necessary.
    """
    json_file = sys.path[0] + "/data/books.json"
    session = sessionmaker(bind=engine)()

    session.add(User(github_id=1))
    session.commit()
    user_id = session.query(User).first().id

    with open(json_file, "r") as data_file:
        parsed_entries = json.load(data_file)

        for entry in parsed_entries:

            """ Create new instance of `Book` if necessary and add to table
            `book`.

            Get id/key of recent book to reference it in table `book_topic` and
            table `book_author`.
            """

            # Books can have similar titles and therefore the same slug
            # SQLAlchemy's `contains` function doesn't cut it
            book_slug = get_slug(
                [b.slug for b in session.query(Book).all()],
                entry["title"]
            )

            # Split input format to create `date` object
            pub_date = entry["publication_date"].split("-")

            session.add(Book(title=entry["title"],
                             isbn=entry["isbn"],
                             description=entry["description"],
                             slug=book_slug,
                             owner_id=user_id,
                             pub_date=date(int(pub_date[1]),
                                           int(pub_date[0]),
                                           1)))

            # Book id is needed to reference authors and topics
            book_id = (
                session.query(Book.id)
                .filter_by(isbn=entry["isbn"])
                .one()[0]
            )

            """ Create new instance of `Topic` if necessary and add to table
            `topic`.

            Get id/key of recent topic to create new instance of `BookTopic`
            and add it to table `book_topic`.
            """
            topics = entry["topics"]

            for topic in topics:
                # Whether topic is present in table `topic`
                topic_exists = len(
                    session
                    .query(Topic.name)
                    .filter_by(name=topic)
                    .all()
                ) > 0

                if not topic_exists:
                    session.add(Topic(
                        name=topic,
                        owner_id=user_id,
                        slug=get_slug(
                            [t.slug for t in (session.query(Topic).all())],
                            topic))
                    )

                # Create entry in `book_topic` table
                topic_id = (
                    session.query(Topic.id)
                    .filter_by(name=topic)
                    .one()[0]
                )
                session.add(BookTopic(book_id=book_id, topic_id=topic_id))

            """ Create new instance of `Author` if necessary and add to table
            `author`.

            Get id/key of recent topic to create new instance of `BookAuthor`
            and add it to table `book_author`.
            """
            authors = entry["authors"]

            for author in authors:
                # Whether author is present in table `author`
                author_exists = len(
                    session
                    .query(Author)
                    .filter_by(name=author)
                    .all()
                ) > 0

                if not author_exists:
                    session.add(Author(name=author))

                # Create entry in `book_author` table
                author_id = (
                    session.query(Author.id)
                    .filter_by(name=author)
                    .one()[0]
                )
                session.add(BookAuthor(book_id=book_id, author_id=author_id))

    # Commit changes to database and close connection
    session.commit()
    session.close()


if __name__ == "__main__":
    prepopulate_db()
