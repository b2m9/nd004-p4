import re

# Those characters are used to delimit titles of books and topics
regex_delimit = re.compile(r"[\t !\"#$%&()*\-/<=>?@\[\\\]^_`{|}:,.]+")


def create_slug(title: str = "") -> str:
    """Create a human-friendly slug.

    Examples:
        Machine Learning -> machine-learning
        You don't know JS -> you-dont-know-js
    """
    result = []
    title = title.replace("'", "")  # "don't" become "dont" and not "don_t"

    for word in regex_delimit.split(title.lower()):
        result.append(word)

    return "-".join(result)


def get_slug(slugs: list, text: str = "") -> str:
    """Get a unique slug.

    Books and topics can have the same name and therefore the same slug. To
    prevent this, use this method to create a unique slug by providing the list
    of existing slugs in addition to the text that will be slugified.

    Example:
        Existing books are "Learning Python", and "Learning Python Data Vis".
        New book is titled "Learning Python" too. By providing the list of
        existing slugs `["learning-python", "learning-python-data-vis"]` the
        method can create `learning-python-1` as a valid, unique slug for the
        new book.

    Args:
        slugs: List of existing slugs
        text: Text that will be slugified with `create_slug`

    Returns:
        A string that is unique among the given list of `slugs`.
    """
    slug = create_slug(text)

    if slug in slugs:
        # Iterate over slugs until available variation is found
        count = 1
        is_available = False

        while is_available is not True:
            new_slug = slug + "-" + str(count)
            if new_slug in slugs:
                count = count + 1
            else:
                slug = new_slug
                is_available = True

    return slug
