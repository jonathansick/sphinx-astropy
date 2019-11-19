# Licensed under a 3-clause BSD style license - see LICENSE.rst
"""APIs for generating standalone example pages.
"""

__all__ = ('ExamplePage', 'ExampleContentDirective')

import copy
import os
import posixpath
import re

from docutils import nodes
from docutils.parsers.rst import Directive
from sphinx.util.logging import getLogger
from sphinx.addnodes import pending_xref, download_reference

from .utils import is_directive_registered


HTTP_URI = re.compile(r'^http(s?)://')
"""Regular expression for identifying http or https URIs.
"""


class ExamplePage:
    """A class that renders and represents a standalone example page.

    Parameters
    ----------
    example_source : sphinx_astropy.ext.example.preprocessor.ExampleSource
        Object describing the source of the example.
    examples_dir : str
        The directory path where example pages are written.
    app : sphinx.application.Sphinx
        The Sphinx application instance.
    """

    def __init__(self, example_source, examples_dir, app):
        self._example_source = example_source
        self._examples_dir = examples_dir
        self._app = app
        self._srcdir = app.srcdir
        self._tag_pages = []

    @property
    def source(self):
        """Metadata about the source of the example, a
        `sphinx_astropy.ext.example.preprocessor.ExampleSource` instance.`
        """
        return self._example_source

    def __str__(self):
        return '<ExamplePage {self.abs_docname!r}>'.format(self=self)

    def __repr__(self):
        return ('ExamplePage({self.example_source!r}, {self.docname!r},'
                ' tags={self.tags!r})').format(self=self)

    def __eq__(self, other):
        return self.source == other.source

    def __ne__(self, other):
        return self.source != other.source

    def __lt__(self, other):
        return self.source < other.source

    def __le__(self, other):
        return self.source <= other.source

    def __gt__(self, other):
        return self.source > other.source

    def __ge__(self, other):
        return self.source >= other.source

    @property
    def docname(self):
        """The docname of the standalone example page.

        The Sphinx docname is similar to the page's file path relative to the
        root of the source directory but does include the ``.rst`` extension.
        """
        return os.path.splitext(
            os.path.relpath(self.filepath, start=self._srcdir))[0]

    @property
    def rel_docname(self):
        """The docname of the standalone example page relative to the
        examples directory.
        """
        return self.source.example_id

    @property
    def abs_docname(self):
        """The absolute docname of the standalone example page.
        """
        return '/' + os.path.splitext(
            os.path.relpath(self.filepath, start=self._srcdir))[0]

    @property
    def filepath(self):
        """The filesystem path where the reStructuredText file for the
        standalone example page is rendered.
        """
        return os.path.join(self._examples_dir,
                            self.rel_docname + '.rst')

    def insert_tag_page(self, tag_page):
        """Associate a tag page with the example page.

        Typically this API is called by
        `sphinx_astropy.ext.example.indexpages.generate_tag_pages`, which
        simultaneously creates tag pages and associates eample pages with
        those tag pages.

        Parameters
        ----------
        tag_page : sphinx_astropy.ext.examples.indexpages.TagPage
            A tag page.

        See also
        --------
        tag_pages
        """
        self._tag_pages.append(tag_page)
        self._tag_pages.sort()

    @property
    def tag_pages(self):
        """Sequence of tag pages
        (`sphinx_astropy.ext.examples.indexpages.TagPage`) associated with
        the example page.
        """
        return self._tag_pages

    def render(self, renderer):
        """Render the source for the standalone example page using a
        ``astropy_example/examplepage.rst`` template.

        Parameters
        ----------
        renderer : sphinx_astropy.ext.example.templates.Renderer
            The Jinja template renderer.

        Returns
        -------
        content : str
            The content of the standalone example page.
        """
        context = {
            'title': self.source.title,
            'tag_pages': self.tag_pages,
            'example': self.source,
            'has_doctestskipall': is_directive_registered('doctest-skip-all')
        }
        return renderer.render('astropy_example/examplepage.rst', context)

    def render_and_save(self, renderer):
        """Render the standalone example page and write it to `filepath`
        using the ``astropy_example/examplepage.rst`` template.

        Parameters
        ----------
        renderer : sphinx_astropy.ext.example.templates.Renderer
            The Jinja template renderer.
        """
        content = self.render(renderer)
        with open(self.filepath, 'w') as fh:
            fh.write(content)


class ExampleContentDirective(Directive):
    """A directive that inserts content from an example marked by the
    ``example`` directive into place.

    Example:

    .. code-block:: rst

       .. example-content:: example-id

    The argument is the ID of the example.
    """

    _logger = getLogger(__name__)
    has_content = False
    required_arguments = 1  # example ID

    def run(self):
        self.env = self.state.document.settings.env
        self.example_id = self.arguments[0].strip()
        try:
            self.example = self.env.sphinx_astropy_examples[self.example_id]
        except (KeyError, AttributeError):
            message = 'Example {} not found in the environment'.format(
                self.example_id)
            self._logger.warning(message)
            return [nodes.Text(message, message)]

        new_nodes = []

        # Add substitution_definition nodes that aren't already in the
        # example page.
        new_nodes.extend(self._merge_substitution_definitions(
            self.state.document,
            self.example['substitution_definitions']))

        # Adapt nodes to work from the standalone example page rather than the
        # source page.
        for node in self.example['content_node'].traverse():
            if isinstance(node, pending_xref):
                self._process_pending_xref(node)
            elif isinstance(node, nodes.image):
                self._process_pending_image(node)
            elif isinstance(node, download_reference):
                self._process_download_reference(node)
            elif isinstance(node, nodes.reference):
                self._process_reference(node)
            elif isinstance(node, nodes.footnote):
                self._process_footnote(node, self.state.document)
            elif isinstance(node, nodes.footnote_reference):
                self._process_footnote_reference(node, self.state.document)
        new_nodes.append(self.example['content_node'])

        return new_nodes

    def _merge_substitution_definitions(self, document, example_sub_defs):
        """Get and process ``substitution_definition`` nodes that are
        captured as part of the ExampleMarkerDirective directive.

        The processing steps are:

        1. Check if any substitutions of the same name are already in the
           document. This could be because they are part of the rst_epilog
           or rst_prolog present in all documents.
        2. Note new substitution definitions in the document.
        3. Return the list of new ``substitution_definition`` nodes.
        """
        # Names of substitution definitions that are part of the page already.
        existing_sub_def_names = set()
        for n in document.traverse(nodes.substitution_definition):
            for name in n['names']:
                existing_sub_def_names.add(name)

        # Process substitution definitions from the example to find the
        # ones that don't already exist in the document.
        new_sub_defs = []
        for n in example_sub_defs:
            names = set(copy.deepcopy(n['names']))
            if names.isdisjoint(existing_sub_def_names):
                new_sub_defs.append(n)
                # This is necessary because the substitution definitions
                # are added *after* the document is parsed. The
                # note_substitutions method adds important metadata about
                # the substitutions to the document and the substitution_refs
                # won't get resolved otherwise.
                for name in names:
                    document.note_substitution_def(n, name)

        return new_sub_defs

    def _process_pending_xref(self, node):
        """Adapt a ``pending_xref`` node to work from a standalone example
        page.

        Parameters
        ----------
        node : sphinx.addnodes.pending_xref
            A ``pending_xref`` node type.
        """
        # The docname of the page where the example originated.
        origin_docname = node['refdoc']
        # Switch the refdoc to be the current doc. This will ensure
        # the link resolves correctly from the standalone example page.
        node['refdoc'] = self.env.docname
        if node['refdomain'] == 'std' and node['reftype'] == 'doc':
            if not node['reftarget'].startswith('/'):
                # Replace the relative reftarget with the absolute
                # reftarget so it will resolve from the standalone
                # example page
                abs_reftarget = '/' + posixpath.normpath(
                    posixpath.join(
                        origin_docname,
                        posixpath.relpath(node['reftarget'],
                                          start=origin_docname)))
                node['reftarget'] = abs_reftarget

    def _process_pending_image(self, node):
        """Adapt an ``image`` node to work from a standalone example page.

        Parameters
        ----------
        node : docutils.nodes.image
            An ``image`` node type.
        """
        if not HTTP_URI.match(node['uri']):
            if not node['uri'].startswith('/'):
                # Replace the relative image URI with the absolute
                # project-relative path so it will resolve from the
                # standalone example page.
                abs_uri = '/' + os.path.normpath(
                    os.path.join(
                        self.example['docname'],
                        os.path.relpath(node['uri'],
                                        start=self.example['docname'])))
                node['uri'] = abs_uri

    def _process_download_reference(self, node):
        """Adapt a ``download_reference`` node, created by a ``download`` role,
        to work from a standalone example page.

        Parameters
        ----------
        node : sphinx.addnodes.download_reference
            A ``download_reference`` node.
        """
        original_reftarget = node['reftarget']
        if original_reftarget.startswith('/'):
            # Ignore absolute references; they'll work out
            return
        if HTTP_URI.match(original_reftarget):
            # Ignore external references
            return

        # The docname of the page where the example originated.
        origin_docname = node['refdoc']
        # Switch the refdoc to be the current doc. This will ensure
        # the link resolves correctly from the standalone example page.
        node['refdoc'] = self.env.docname

        # Replace the relative reftarget with an absolute reftarget
        abs_reftarget = '/' + posixpath.normpath(
            posixpath.join(
                origin_docname,
                posixpath.relpath(node['reftarget'],
                                  start=origin_docname)))
        node['reftarget'] = abs_reftarget

    def _process_reference(self, node):
        """Adapt a ``reference`` to work from a standalone example page.

        Parameters
        ----------
        node : docutils.nodes.reference
            A ``reference`` node type.

        Notes
        -----
        In most cases, external references don't need to be adapted. However,
        matplotlib.sphinxext.plot_directive is observed to use an external
        reference node when linking to the plot source files. Those URIs
        start with './/'.
        """
        if 'refuri' in node:  # look for "external" links
            if not HTTP_URI.match(node['refuri']):
                # The refuri is actually a local path. We need to make the
                # link relative to the directory of the examples.
                uri = posixpath.relpath(
                    posixpath.normpath(
                        posixpath.join(
                            self.example['docname'],
                            posixpath.relpath(
                                node['refuri'],
                                start=self.example['docname']))),
                    start=posixpath.dirname(self.env.docname))
                node['refuri'] = uri

    def _process_footnote(self, node, document):
        """Process a ``footnote`` node that appears in the example content.

        This calls the ``note_footnote`` or ``node_autofootnote`` methods
        on the document (`docutils.nodes.document`). These methods are normally
        called when the reStructuredText is parsed, but since these nodes
        are preparsed from a different document, this directive needs to
        manually "note" the footnotes so that the Footnotes transform
        (`docutils.transforms.references.Footnotes`) can process it.
        """
        if node['backrefs']:
            document.note_footnote(node)
        else:
            # The footnote is likely autonumbered.
            if node['names']:
                # The autofootnote transform need an empty names attribute
                # here. It might be non-empty because the node came from
                # the original page.
                node['names'] = []
            document.note_autofootnote(node)

    def _process_footnote_reference(self, node, document):
        """Process a ``footnote_reference`` node that appears in the example
        content.

        This calls the ``note_footnote_ref`` or ``note_autofootnote_ref``
        methods on the document (`docutils.nodes.document`). These methods are
        normally called when the reStructuredText is parsed, but since these
        nodes are preparsed from a different document, this directive needs to
        manually "note" the footnote references so that the Footnotes transform
        (`docutils.transforms.references.Footnotes`) can process it.
        """
        if 'refid' not in node:
            # The footnote_reference is likely autonumbered.
            document.note_autofootnote_ref(node)
        else:
            document.note_footnote_ref(node)
