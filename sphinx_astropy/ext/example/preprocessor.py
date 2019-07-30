# Licensed under a 3-clause BSD style license - see LICENSE.rst

__all__ = ('preprocess_example_pages', 'detect_examples')

import os
import re

from sphinx.util.logging import getLogger

from .marker import format_title_to_example_id
from .examplepages import generate_example_page
from .indexpages import generate_landing_page, generate_tag_page


EXAMPLE_PATTERN = re.compile(
    # Match the example directive and title argument
    r'^\.\. example:: (?P<title>.+)\n'
    # Optionally match the tags option that follows
    # Note: this only works because there aren't other options.
    r'( +:tags: +(?P<tags>.+))?$',
    flags=re.MULTILINE)


def preprocess_example_pages(app):
    """Generate the example gallery landing pages and stubs for individual
    standalone example pages by detecting example directives in the
    reStructuredText source.

    This fun is run as part of the ``builder-inited`` event.

    Parameters
    ----------
    app : `sphinx.application.Sphinx`
        The application instance.
    """
    logger = getLogger(__name__)
    logger.debug('in generate_gallery_pages')
    env = app.env
    logger.debug('Found docs %s', str(env.found_docs))

    # Create directory for example pages inside the documentation source dir
    examples_dir = os.path.join(app.srcdir, app.config.astropy_examples_dir)
    os.makedirs(examples_dir, exist_ok=True)

    tags_dir = os.path.join(app.config.astropy_examples_dir, 'tags')
    abs_tagsdir = os.path.join(app.srcdir, tags_dir)
    os.makedirs(abs_tagsdir, exist_ok=True)

    # Add extensions to the docnames to generate relative paths
    found_files = []
    for docname in env.found_docs:
        filepath = env.doc2path(docname)
        if os.path.isfile(filepath):
            found_files.append(filepath)

    found_examples = []
    for filepath in found_files:
        logger.debug('[sphinx_astropy] Checking for examples in %s', filepath)
        found_examples.extend(detect_examples(filepath, env))

    # Compute docnames and file paths for each example page
    for example in found_examples:
        example_id = format_title_to_example_id(example['title'])
        example['example_id'] = example_id
        example['docname'] = example_id
        example['abs_docname'] = '/' \
            + os.path.join(app.config.astropy_examples_dir, example_id)
        example['filepath'] = os.path.join(
            app.srcdir, app.config.astropy_examples_dir,
            example['docname'] + '.rst')

    # Alphabetically sort examples
    found_examples.sort(key=lambda x: x['title'])

    # Pre compute information about tags
    all_tags = set()
    for example in found_examples:
        all_tags.update(example['tags'])
    tags = {}
    for tagname in all_tags:
        filepath = os.path.join(abs_tagsdir, tagname + '.rst')
        abs_docname = '/' + os.path.join(tags_dir, tagname)
        tags[tagname] = {
            'tag': tagname,
            'filepath': filepath,
            'docname': tagname,
            'abs_docname': abs_docname
        }

    for example in found_examples:
        logger.debug('[sphinx_astropy] Creating a page for example "%s"',
                     example['title'])
        generate_example_page(title=example['title'],
                              tags=example['tags'],
                              example_id=example['example_id'],
                              filepath=example['filepath'],
                              h1header=app.config.astropy_examples_h1,
                              taginfo=tags)

    # Generate a page for each tag
    for tagname, info in tags.items():
        print(tagname, info)
        generate_tag_page(
            tagname=tagname,
            filepath=info['filepath'],
            examples=found_examples,
            h1header=app.config.astropy_examples_h1,
            taginfo=tags)

    logger.debug('[sphinx_astropy] Creating examples landing page')
    generate_landing_page(
        examples=found_examples,
        dirname=examples_dir,
        h1header=app.config.astropy_examples_h1,
        taginfo=tags)


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
