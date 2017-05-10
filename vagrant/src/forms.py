from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, TextAreaField, validators


class UpdateTopicForm(FlaskForm):
    """Form for route "<topic_slug>/edit". """
    name = StringField(
        "Topic Name:",
        [validators.Length(min=1, max=80)]
    )
    submit = SubmitField("Submit")


class DeleteForm(FlaskForm):
    """Form for routes "/<topic_slug>/delete" and
    "/<topic_slug>/<book_slug>/delete".
    """
    submit = SubmitField("Delete")


class UpdateBookForm(FlaskForm):
    """Form for route "/<topic_slug>/<book_slug/edit". """
    title = StringField(
        "Book Title:",
        [validators.Length(min=1, max=80,
                           message="Book title must be between 1 and 80 "
                                   "characters long.")]
    )
    isbn = StringField(
        "ISBN:",
        [validators.Length(min=13, max=13,
                           message="Valid ISBNs are 13 characters long."),
         validators.Regexp("^(\d*)$", message="Only numbers are allowed.")]
    )
    authors = StringField(
        "Author(s):",
        [validators.Length(min=3, max=250,
                           message="List authors, separated by comma.")]
    )
    pub_date = StringField(
        "Publication Date:",
        [validators.Length(min=7, max=7,
                           message="Must be 7 characters long."),
         validators.Regexp("^\d\d-\d\d\d\d$",
                           message="Publication date must be in format "
                                   "MM-YYYY, like 06-2010 for June 2010.")]
    )
    description = TextAreaField("Description:", [validators.Optional()])
    submit = SubmitField("Submit")


class AddBookForm(FlaskForm):
    """Form for route "/add". """
    title = StringField(
        "Book Title:",
        [validators.Length(min=1, max=80,
                           message="Book title must be between 1 and 80 "
                                   "characters long.")]
    )
    authors = StringField(
        "Author(s):",
        [validators.Length(min=3, max=250,
                           message="List authors, separated by comma.")]
    )
    topics = StringField(
        "Topic(s):",
        [validators.Length(min=3, max=250,
                           message="List topics, separated by comma.")]
    )
    isbn = StringField(
        "ISBN:",
        [validators.Length(min=13, max=13,
                           message="Valid ISBNs are 13 characters long."),
         validators.Regexp("^(\d*)$", message="Only numbers are allowed.")]
    )
    pub_date = StringField(
        "Publication Date:",
        [validators.Length(min=7, max=7,
                           message="Must be 7 characters long."),
         validators.Regexp("^\d\d-\d\d\d\d$",
                           message="Publication date must be in format "
                                   "MM-YYYY, like 06-2010 for June 2010.")]
    )
    description = TextAreaField("Description:", [validators.Optional()])
    submit = SubmitField("Submit")
