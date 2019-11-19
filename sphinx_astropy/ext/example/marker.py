# Licensed under a 3-clause BSD style license - see LICENSE.rst
"""The ``example`` directive that marks examples in the main documentation
text.
"""

__all__ = ('ExampleMarkerNode', 'visit_example_marker_html',
           'depart_example_marker_html', 'ExampleMarkerDirective',
           'format_title_to_example_id', 'format_title_to_source_ref_id',
           'format_example_id_to_source_ref_id')

from docutils import nodes
from docutils.parsers.rst import Directive, directives
from sphinx.util.logging import getLogger
from sphinx.util.nodes import nested_parse_with_titles


class ExampleMarkerNode(nodes.container):
    """Docutils node that encapsulates an example in the source content.

    This node is inserted by the `ExampleMarkerDirective`.
    """


def visit_example_marker_html(self, node):
    """HTML visitor for the `ExampleMarkerNode`.

    In HTML, marked up examples are wrapped in a ``<div>`` tag with a class
    of ``astropy-example-source``.
    """
    # The class is used by the HTML postprocessor to capture the HTML of
    # examples. The content of the div gets re-posted onto the stand-alone
    # example pages.
    self.body.append(
        self.starttag(node, 'div', CLASS='astropy-example-source'))


def depart_example_marker_html(self, node):
    """HTML departure handler for the `ExampleMarkerNode`.
    """
    self.body.append('</div>')


class ExampleMarkerDirective(Directive):
    """Directive for marking an example snippet in the body of documentation.

    This directive passes content through into the original
    documentation, but wraps it in a `ExampleMarkerNode` so that the HTML
    post-processing step can find the example's content and add it to the
    gallery.

    Usage example:

    .. code-block:: rst

       .. example:: Title of Example
          :tags: tag-1, tag-2

          Example content.

          The example content can contain multiple paragraphs, lists, images,
          code blocks, equations, and so on.

    Tags are optional and comma-separated.
    """

    _logger = getLogger(__name__)

    has_content = True

    required_arguments = 1  # The title is required
    final_argument_whitespace = True

    option_spec = {
        'tags': directives.unchanged
    }

    def run(self):
        self.assert_has_content()

        env = self.state.document.settings.env

        self.title = self.arguments[0].strip()

        # ID for example within the build environment
        self.example_id = format_title_to_example_id(self.title)
        # ID for the reference node. The example-src- prefix distinguishes
        # this ID as the source of the example, rather than a reference to
        # the standalone example page.
        self.ref_id = format_title_to_source_ref_id(self.title)

        self._logger.debug(
            '[sphinx_astropy] example title: %s',
            self.title, location=(env.docname, self.lineno))

        # The example content is parsed into the ExampleMarkerNode. This
        # node serves as both a container and a node that gets turned into a
        # <div> that the HTML-postprocessor uses to identify and copy
        # example content in the standalone example pages.
        rawsource = '\n'.join(self.content)
        example_node = ExampleMarkerNode(rawsource=rawsource)
        # For docname/lineno metadata
        example_node.document = self.state.document
        nested_parse_with_titles(self.state, self.content, example_node)

        # The target node is for backlinks from an example page to the
        # source of the example in the "main" docs.
        # In HTML, this becomes the id attribute of the container div.
        target_node = nodes.target('', '', ids=[self.ref_id])
        self.state.document.note_explicit_target(target_node)

        return [target_node, example_node]


def format_title_to_example_id(title):
    """Convert an example's title into an ID for the title.

    IDs are slugified versions of the title.

    Parameters
    ----------
    title : str
        The title of the example (such as set are the argument to the
        ``example`` directive.

    Returns
    -------
    example_id : str
        The ID for the example. This ID is used internally to identify an
        example within the build environment.
    """
    return nodes.make_id(title)


def format_title_to_source_ref_id(title):
    """Convert an example's title into the ref ID for the example's source
    location.

    The target node itself is generated by the ``example`` directive.

    Parameters
    ----------
    title : str
        The title of the example (such as set are the argument to the
        ``example`` directive.

    Returns
    -------
    ref_id : str
        The ref ID for the node marking the example's *source* location.
    """
    example_id = format_title_to_example_id(title)
    return format_example_id_to_source_ref_id(example_id)


def format_example_id_to_source_ref_id(example_id):
    """Convert an example's ID into the ref ID for the example's source
    location.

    The target node itself is generated by the ``example`` directive.

    Parameters
    ----------
    example_id : str
        The ID for the example. This ID is used internally to identify an
        example within the build environment.

    Returns
    -------
    ref_id : str
        The ref ID for the node marking the example's *source* location.
    """
    return 'example-src-{}'.format(example_id)
