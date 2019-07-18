# Licensed under a 3-clause BSD style license - see LICENSE.rst

__all__ = ('detect_examples',)

import re

from sphinx.util.logging import getLogger


EXAMPLE_PATTERN = re.compile(
    # Match the example directive and title argument
    r'^\.\. example:: (?P<title>.+)\n'
    # Optionally match the tags option that follows
    # Note: this only works because there aren't other options.
    r'( +:tags: +(?P<tags>.+))?$',
    flags=re.MULTILINE)


def detect_examples(filepath, env):
    """Detect ``example`` directives from a source file by regular expression
    matching.

    Parameters
    ----------
    filepath : str
        A path to a source file.
    env : sphinx.environment.BuildEnvironment
        The build environment.

    Returns
    -------
    examples : list of dict
        List of found examples (or an empty list if no examples are found.
        Each example is a dict with keys:

        title
            The string containing the title argument to the example directive.
        tags
            The set of tag strings (or an empty set if no tags are given).
    """
    logger = getLogger(__name__)

    with open(filepath, encoding='utf-8') as fh:
        text = fh.read()

    # Make the docname absolute
    src_docname = '/' + env.path2doc(filepath)

    examples = []
    for m in EXAMPLE_PATTERN.finditer(text):
        title = m.group('title')
        if title is None:
            logger.warning(
                '[sphinx_astropy] Could not parse example title from %s',
                m.group(0))

        tag_option = m.group('tags')
        if tag_option:
            tags = set([t.strip() for t in tag_option.split(', ')])
        else:
            tags = set()

        examples.append({'title': title,
                         'tags': tags,
                         'src_docname': src_docname})
    return examples
