from flask import (Flask, render_template, request, redirect, url_for, flash,
                   jsonify, g, session, abort)
from flask_bootstrap import Bootstrap
from flask_github import GitHub

from sqlalchemy import and_
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError

from datetime import date

from forms import UpdateTopicForm, UpdateBookForm, DeleteForm, AddBookForm
from helper import get_slug
from db_bookshelf import Book, Topic, Author, BookAuthor, BookTopic, engine
from github_secrets import GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET

# Setup Flask app
app = Flask(__name__)
app.config["SECRET_KEY"] = "6RoG8rjAiYzHa4ijDTNtiEnC2XFxEwNsmexWb7pu"
app.config["GITHUB_CLIENT_ID"] = GITHUB_CLIENT_ID
app.config["GITHUB_CLIENT_SECRET"] = GITHUB_CLIENT_SECRET
bootstrap = Bootstrap(app)
github = GitHub(app)
db_session = sessionmaker(bind=engine)()


"""" SECTION: GITHUB AUTH LOGIC """


@app.before_request
def before_request():
    """Before each request, make auth token available in `g.user`."""
    g.user = None
    if 'auth_token' in session:
        g.user = session['auth_token']


@github.access_token_getter
def token_getter():
    """Return Github's auth token to make requests on the user's behalf."""
    user = g.user
    if user is not None:
        return user.auth_token


@app.route("/login")
@app.route("/login/")
def login():
    """Redirect to Github authorisation page or to route "/" if user is
    already logged in or Github's client secrets are not set.
    """
    # Check if Github client secrets are set
    if app.config["GITHUB_CLIENT_ID"] and app.config["GITHUB_CLIENT_SECRET"]:
        if session.get("auth_token", None) is None:
            return github.authorize()
        else:
            flash("Already logged in.", "info")
            return redirect(url_for("overview"))

    else:
        flash("Auth error. Please fill in Github's client secrets.", "danger")
        return redirect(url_for("overview"))


@app.route("/logout")
@app.route("/logout/")
def logout():
    """Remove auth token and redirect to route "/". Does not test if a user
    was actually logged in.
    """
    session.pop("auth_token", None)
    flash("Logout successful.", "success")
    return redirect(url_for("overview"))


@app.route("/github-callback")
@github.authorized_handler
def authorized(oauth_token):
    """Callback handler for Github OAuth.

    Sets auth token to `session.auth_token` and redirects to route "/".
    """
    next_url = request.args.get("next") or url_for("overview")

    if oauth_token is None:
        flash("Authorization failed.", "danger")
        return redirect(next_url)

    session["auth_token"] = oauth_token
    flash("Login successful.", "success")
    return redirect(next_url)


"""" SECTION: READ TOPICS AND BOOKS """


@app.route("/")
@app.route("/<topic_slug>")
@app.route("/<topic_slug>/")
def overview(topic_slug: str="") -> tuple:
    """Render `templates/overview.html` for "/" and "/<topic_slug>".

    Route "/":
        Display all books ordered by `pub_date` from `bookshelf_db.Book`.

    Route "/<topic_slug>":
        Display only the books associated with the given `topic_slug`.

    Args:
        topic_slug: Unique human-friendly slug to identify topic.

    Raises:
        SQLAlchemyError: Given `topic_slug` not found in `bookshelf_db.Topic`.
            Abort with error code 404.
    """
    topic_list = db_session.query(Topic.name, Topic.slug).all()

    # TODO: How to alias fields in SQLAlchemy?
    # Example: Book.slug and Topic.slug have same key in result tuple
    if len(topic_slug):
        try:
            # Return 404 in case of invalid `topic_slug`
            topic = get_topic_by_slug(topic_slug).name
            book_list = (
                db_session.query(Book.title, Book.slug, Topic.slug)
                .join(BookTopic, Topic)
                .filter(and_(Topic.slug == topic_slug))
                .all()
            )
        except SQLAlchemyError as sa_err:
            return abort(404, sa_err)
    else:
        topic = ""
        # Group by BookTopic.book_id necessary to filter out books that belong
        # multiple topics.
        #
        # Example:
        # Book "Data Vis with Python and JavaScript" belongs to topics
        # "Python" and "JavaScript".
        book_list = (
            db_session.query(Book.title, Book.slug, Topic.slug)
            .join(BookTopic, Topic)
            .group_by(BookTopic.book_id)
            .order_by(Book.pub_date.desc())
            .all()
        )

    user = None if not g.user else g.user

    return render_template("overview.html", topics=topic_list, topic=topic,
                           t_slug=topic_slug, books=book_list, user=user)


@app.route("/<topic_slug>/<book_slug>")
@app.route("/<topic_slug>/<book_slug>/")
def detail(topic_slug: str, book_slug: str) -> tuple:
    """Render `templates/detail.html` for "/<topic_slug>/<book_slug>".

    Route "/<topic_slug>/<book_slug>":
        Display all details associated with this book from `bookshelf_db.Book`.
        Query for associated authors from `bookshelf_db.Author`.

    Args:
        topic_slug: Unique human-friendly slug to identify topic.
        book_slug: Unique human-friendly slug to identify book.

    Raises:
        SQLAlchemyError: Given `topic_slug` or `book_slug` not found in
            `bookshelf_db.Topic` or `bookshelf_db.Book` respectively. Abort
            with error code 404.
    """
    try:
        # Return 404 in case of invalid `topic_slug` or `book_slug`
        get_topic_by_slug(topic_slug)
        book = get_book_by_slug(book_slug)
        authors = get_authors_by_book_id(book.id)
    except SQLAlchemyError as sa_err:
        return abort(404, sa_err)

    user = None if not g.user else g.user

    return render_template("detail.html", book=book, authors=authors,
                           t_slug=topic_slug, b_slug=book_slug, user=user)


"""" SECTION: ADD BOOKS """


@app.route("/add", methods=["GET", "POST"])
@app.route("/add/", methods=["GET", "POST"])
def add_book():
    """Render `templates/add.html` for "/add".

    Route GET "/add":
        Render instance of `forms.AddBookForm`.

    Route POST "/add":
        If form validation fails, render instance of `forms.AddBookForm`.
        If form validation successful, create new book and update all tables.
        If commit to database successful, redirect app to route "/".

    Raises:
        SQLAlchemyError: Commit new book failed. Abort with error code 500.
    """
    # User needs to be logged in to see this page
    user = None if not g.user else g.user
    if user is None:
        return abort(401)

    form = AddBookForm()

    if request.method == "POST" and form.validate_on_submit():
        # Add new `Book` and remember id
        pub_date = form.pub_date.data.split("-")
        book = Book(title=form.title.data,
                    isbn=form.isbn.data,
                    description=form.description.data,
                    slug=create_book_slug(form.title.data),
                    pub_date=date(int(pub_date[1]), int(pub_date[0]), 1))
        db_session.add(book)
        book_id = db_session.query(Book).filter_by(slug=book.slug).one().id

        # Add new `Topic` if necessary and create new reference in `BookTopic`
        for topic in form.topics.data.split(","):
            topic = topic.strip()
            topic_exists = len(get_topic_by_name(topic)) > 0

            if not topic_exists:
                db_session.add(
                    Topic(name=topic, slug=create_topic_slug(topic))
                )

            topic_id = get_topic_by_name(topic)[0].id
            db_session.add(BookTopic(book_id=book_id, topic_id=topic_id))

        # Add new `Author` if necessary and create reference in `BookAuthor`
        for name in form.authors.data.split(","):
            name = name.strip()
            author_exists = len(get_author_by_name(name)) > 0

            if not author_exists:
                db_session.add(Author(name=name))

            author_id = get_author_by_name(name)[0].id
            db_session.add(BookAuthor(book_id=book.id, author_id=author_id))

        try:
            # Return 500 in case commit fails
            db_session.commit()
        except SQLAlchemyError as sa_err:
            db_session.rollback()
            flash("Something went very wrong. Add aborted.", "danger")
            abort(500, sa_err)

        flash("Book successfully added.", "success")
        return redirect(url_for("overview"))
    else:
        return render_template("add.html", form=form, user=user)


"""" SECTION: EDIT TOPICS AND BOOKS """


@app.route("/<topic_slug>/edit", methods=["GET", "POST"])
@app.route("/<topic_slug>/edit/", methods=["GET", "POST"])
def update_topic(topic_slug: str) -> tuple:
    """Render `templates/update.html` for "/<topic_slug>/edit".

    Route GET "/<topic_slug>/edit":
        Render instance of `forms.UpdateTopicForm` with pre-filled values.

    Route POST "/<topic_slug>/edit":
        If form validation fails, render instance of `forms.UpdateTopicForm`.
        If form validation successful, update topic with new name and commit to
        database. If commit to database successful, redirect app to route "/".

    Args:
        topic_slug: Unique human-friendly slug to identify topic.

    Raises:
        SQLAlchemyError: Given `topic_slug` not found in `bookshelf_db.Topic`.
            Abort with error code 404.
        SQLAlchemyError: Commit updated topic failed. Abort with error code
            500.
    """
    try:
        # Return 404 in case of invalid `topic_slug`
        topic = get_topic_by_slug(topic_slug)
    except SQLAlchemyError as sa_err:
        return abort(404, sa_err)

    # User needs to be logged in to see this page
    user = None if not g.user else g.user
    if user is None:
        return abort(401)

    form = UpdateTopicForm()

    if request.method == "POST" and form.validate_on_submit():
        if topic.name != form.name.data:
            # Update slug if name has changed
            if topic.name != form.name.data:
                topic.name = form.name.data
                topic.slug = create_topic_slug(topic.name)

            try:
                # Return 500 in case commit fails
                db_session.add(topic)
                db_session.commit()
            except SQLAlchemyError as sa_err:
                db_session.rollback()
                flash("Something went very wrong. Edit aborted.", "danger")
                return abort(500, sa_err)

        flash("Topic successfully edited.", "success")
        return redirect(url_for("overview"))
    else:
        if request.method == "GET":
            # Pre-populate form data if it is GET request
            form.name.data = topic.name

        return render_template("update.html", form=form, name=topic.name,
                               user=user)


@app.route("/<topic_slug>/<book_slug>/edit", methods=["GET", "POST"])
@app.route("/<topic_slug>/<book_slug>/edit/", methods=["GET", "POST"])
def update_book(topic_slug: str, book_slug: str) -> tuple:
    """Render `templates/update.html` for "/<topic_slug>/<book_slug>/edit".

    Route GET "/<topic_slug>/<book_slug>/edit":
        Render instance of `forms.UpdateTopicForm` with pre-filled values.

    Route POST "/<topic_slug>/<book_slug>/edit":
        If form validation fails, render instance of `forms.UpdateTopicForm`.
        If form validation successful, update `bookshelf_db.Book`,
        `bookshelf_db.BookAuthor`, and `bookshelf_db.Author` and commit to
        database. If commit to database successful, redirect app to route "/".

    Args:
        topic_slug: Unique human-friendly slug to identify topic.
        book_slug: Unique human-friendly slug to identify book.

    Raises:
        SQLAlchemyError: Given `topic_slug` or `book_slug` not found in
            `bookshelf_db.Topic` or `bookshelf_db.Book` respectively. Abort
            with error code 404.
        SQLAlchemyError: Commit failed. Abort with error code 500.
    """
    try:
        # Return 404 in case of invalid `topic_slug` or `book_slug`
        get_topic_by_slug(topic_slug)
        book = get_book_by_slug(book_slug)
        authors = get_authors_by_book_id(book.id)
    except SQLAlchemyError as sa_err:
        return abort(404, sa_err)

    # User needs to be logged in to see this page
    user = None if not g.user else g.user
    if user is None:
        return abort(401)

    form = UpdateBookForm()

    if request.method == "POST" and form.validate_on_submit():
        try:
            # Update slug if title has changed
            if book.title != form.title.data:
                book.title = form.title.data
                book.slug = create_book_slug(book.title)

            # Update remaining `book` fields
            book.description = form.description.data
            book.isbn = form.isbn.data
            pub_date = form.pub_date.data.split("-")
            book.pub_date = date(int(pub_date[1]), int(pub_date[0]), 1)
            db_session.add(book)

            # Delete references in `BookAuthor`
            delete_bookauthor_by_book_id(book.id)

            # Create new authors if necessary
            # Create entry in `BookAuthor`
            for name in form.authors.data.split(","):
                name = name.strip()
                author_exists = len(get_author_by_name(name)) > 0

                if not author_exists:
                    db_session.add(Author(name=name))

                author_id = get_author_by_name(name)[0].id
                db_session.add(BookAuthor(book_id=book.id,
                                          author_id=author_id))

            # Delete all authors without entries in `BookAuthor`
            delete_bookless_authors()

            db_session.commit()
        except SQLAlchemyError as sa_err:
            db_session.rollback()
            flash("Something went very wrong. Edit aborted.", "danger")
            return abort(500, sa_err)

        flash("Book successfully edited.", "success")
        return redirect(url_for("overview"))
    else:
        if request.method == "GET":
            # Pre-populate form data if it is a GET request
            form.title.data = book.title
            form.isbn.data = book.isbn
            form.description.data = book.description
            form.authors.data = ", ".join(authors)
            form.pub_date.data = book.pub_date.strftime("%m-%Y")

        return render_template("update.html", form=form, name=book.title,
                               user=user)


"""" SECTION: DELETE TOPICS AND BOOKS """


@app.route("/<topic_slug>/delete", methods=["GET", "POST"])
@app.route("/<topic_slug>/delete/", methods=["GET", "POST"])
def delete_topic(topic_slug: str) -> tuple:
    """Render `templates/delete.html` for "/<topic_slug>/delete".

    Route GET "/<topic_slug>/delete":
        Render instance of `forms.DeleteForm`.

    Route POST "/<topic_slug>/delete":
        Deletes a single instance of `bookshelf_db.Topic` and deletes
        subsequently associated entries from `bookshelf_db.BookTopic`,
        `bookshelf_db.Book`, `bookshelf_db.BookAuthor`, and
        `bookshelf_db.Author`. If commit to database successful, redirect
        app to route "/".

    Args:
        topic_slug: Unique human-friendly slug to identify topic.

    Raises:
        SQLAlchemyError: Given `topic_slug` not found in `bookshelf_db.Topic`.
            Abort with error code 404.
        SQLAlchemyError: Commit failed. Abort with error code 500.
    """
    try:
        # Return 404 in case of invalid `topic_slug`
        topic = get_topic_by_slug(topic_slug)
    except SQLAlchemyError as sa_err:
        return abort(404, sa_err)

    # User needs to be logged in to see this page
    user = None if not g.user else g.user
    if user is None:
        return abort(401)

    form = DeleteForm()

    if request.method == "POST" and form.validate_on_submit():
        try:
            # Return 500 in case commit fails
            db_session.delete(topic)

            # Delete references in BookTopic and then books w/o topics
            delete_list(
                db_session.query(BookTopic)
                .filter_by(topic_id=topic.id)
                .all()
            )
            delete_topicless_books()

            # Delete references in BookAuthor and then authors w/o books
            delete_list(
                db_session.query(BookAuthor)
                .outerjoin(Book)
                .filter(and_(Book.id == None))  # `is None` does not work
                .all()
            )
            delete_bookless_authors()

            db_session.commit()
        except SQLAlchemyError as sa_err:
            db_session.rollback()
            flash("Something went very wrong. Deletion aborted.", "danger")
            return abort(500, sa_err)

        flash("Topic successfully deleted.", "success")
        return redirect(url_for("overview"))
    else:
        return render_template("delete.html", form=form, name=topic.name,
                               is_topic=True, user=user)


@app.route("/<topic_slug>/<book_slug>/delete", methods=["GET", "POST"])
@app.route("/<topic_slug>/<book_slug>/delete/", methods=["GET", "POST"])
def delete_book(topic_slug: str, book_slug: str) -> tuple:
    """Render `templates/delete.html` for "/<topic_slug>/<book_slug>/delete".

    Route GET "/<topic_slug>/<book_slug>/delete":
        Render instance of `forms.DeleteForm`.

    Route POST "/<topic_slug>/<book_slug>/delete":
        Deletes a single instance of `bookshelf_db.Book` and deletes
        subsequently associated entries from `bookshelf_db.BookTopic`,
        `bookshelf_db.Book`, `bookshelf_db.BookAuthor`, and
        `bookshelf_db.Author`. If commit to database successful, redirect
        app to route "/".

    Args:
        topic_slug: Unique human-friendly slug to identify topic.
        book_slug: Unique human-friendly slug to identify book.

    Raises:
        SQLAlchemyError: Given `topic_slug` or `book_slug` not found in
            `bookshelf_db.Topic` or `bookshelf_db.Book` respectively. Abort
            with error code 404.
        SQLAlchemyError: Commit failed. Abort with error code 500.
    """
    try:
        # Return 404 in case of invalid `topic_slug` or `book_slug`
        get_topic_by_slug(topic_slug)
        book = get_book_by_slug(book_slug)
    except SQLAlchemyError as sa_err:
        return abort(404, sa_err)

    # User needs to be logged in to see this page
    user = None if not g.user else g.user
    if user is None:
        return abort(401)

    form = DeleteForm()

    if request.method == "POST" and form.validate_on_submit():
        try:
            # Return 500 in case commit fails
            db_session.delete(book)

            # Delete references in BookAuthor and then authors w/o books
            delete_bookauthor_by_book_id(book.id)
            delete_bookless_authors()

            # Delete references in BookTopic and then topics w/o books
            delete_list(
                db_session.query(BookTopic)
                .filter_by(book_id=book.id)
                .all()
            )
            delete_bookless_topics()
            db_session.commit()
        except SQLAlchemyError as sa_err:
            db_session.rollback()
            flash("Something went very wrong. Deletion aborted.", "danger")
            return abort(500, sa_err)

        flash("Book successfully deleted.", "success")
        return redirect(url_for("overview"))
    else:
        return render_template("delete.html", form=form, name=book.title,
                               is_book=True, user=user)


"""" SECTION: JSON ENDPOINTS """


@app.route("/JSON")
@app.route("/JSON/")
@app.route("/<topic_slug>/JSON")
@app.route("/<topic_slug>/JSON/")
def handle_json(topic_slug: str=""):
    if len(topic_slug):
        try:
            # Return 404 in case of invalid `topic_slug`
            get_topic_by_slug(topic_slug)  # Necessary to throw exception
            books = (
                db_session.query(Book)
                .join(BookTopic, Topic)
                .filter(and_(Topic.slug == topic_slug))
                .all()
            )
        except SQLAlchemyError as sa_err:
            return abort(404, sa_err)
    else:
        books = db_session.query(Book).all()

    return jsonify(books=[b.serialize() for b in books])


"""" SECTION: ERROR HANDLERS """


@app.errorhandler(401)
def error_404(e: Exception) -> tuple:
    """Render `templates/401.html` if 401 error."""
    user = None if not g.user else g.user

    return render_template("401.html", exception=e, user=user), 401


@app.errorhandler(404)
def error_404(e: Exception) -> tuple:
    """Render `templates/404.html` if 404 error."""
    user = None if not g.user else g.user

    return render_template("404.html", exception=e, user=user), 404


@app.errorhandler(500)
def error_500(e: Exception) -> tuple:
    """Render `templates/500.html` if 500 error."""
    user = None if not g.user else g.user

    return render_template('500.html', exception=e, user=user), 500


"""" SECTION: HELPER FUNCTIONS TO RE-USE QUERIES """


def get_topic_by_slug(slug: str) -> Topic:
    """Return one `Topic` by given `slug`."""
    return db_session.query(Topic).filter_by(slug=slug).one()


def get_book_by_slug(slug: str) -> Book:
    """Return one `Book` by given `slug`."""
    return db_session.query(Book).filter_by(slug=slug).one()


def get_authors_by_book_id(book_id: int) -> list:
    """Return list of `Author.name` for given `book_id`."""
    return [a[0] for a in (
        db_session.query(Author.name)
        .join(BookAuthor, Book)
        .filter(and_(BookAuthor.book_id == book_id))
        .all()
    )]


def get_topic_by_name(name: str) -> list:
    """Return all `Topic` objects matching given `name`."""
    return db_session.query(Topic).filter_by(name=name).all()


def get_author_by_name(name: str) -> list:
    """Return all `Author` objects matching given `name`."""
    return db_session.query(Author).filter_by(name=name).all()


def create_book_slug(title: str) -> str:
    """Return unique slug for `Book`."""
    return get_slug([b.slug for b in db_session.query(Book).all()], title)


def create_topic_slug(name: str) -> str:
    """Return unique slug for `Topic`."""
    return get_slug([t.slug for t in (db_session.query(Topic).all())], name)


def delete_bookauthor_by_book_id(book_id: int) -> None:
    """Delete all references in `BookAuthor` matching given `book_id`."""
    delete_list(
        db_session.query(BookAuthor)
        .filter_by(book_id=book_id)
        .all()
    )


def delete_bookless_authors() -> None:
    """Delete all `Author` objects without references in `BookAuthor`."""
    delete_list(
        db_session.query(Author)
        .outerjoin(BookAuthor)
        .filter(BookAuthor.author_id == None)  # `is None` doesn't work
        .all()
    )


def delete_bookless_topics() -> None:
    """Delete all `Topic` objects without references in `BookTopic`."""
    delete_list(
        db_session.query(Topic)
        .outerjoin(BookTopic)
        .filter(BookTopic.topic_id == None)  # `is None` doesn't work
        .all()
    )


def delete_topicless_books() -> None:
    """Delete all `Book` objects without references in `BookTopic`."""
    delete_list(
        db_session.query(Book)
        .outerjoin(BookTopic)
        .filter(BookTopic.book_id == None)  # `is None` doesn't work
        .all()
    )


def delete_list(db_list: list) -> None:
    """Delete a list of SQLAlchemy objects.

    Necessary because `session.delete` can only delete single elements.
    """
    for l in db_list:
        db_session.delete(l)

if __name__ == '__main__':
    # Automatically reload changed Jinja templates
    app.jinja_env.auto_reload = True
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    app.run(host="0.0.0.0", port=5000)
