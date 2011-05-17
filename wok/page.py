import os
from collections import namedtuple
from datetime import datetime

import jinja2
import yaml
import re

from wok import util
from wok import renderers

class Page(object):
    """
    A single page on the website in all it's form, as well as it's
    associated metadata.
    """

    class Author(object):
        """Smartly manages a author with name and email"""
        parse_author_regex = re.compile(r'([^<>]*)( +<(.*@.*)>)$')

        def __init__(self, raw='', name=None, email=None):
            self.raw = raw
            self.name = name
            self.email = email

        @classmethod
        def parse(cls, raw):
            a = cls(raw)
            a.name, _, a.email = cls.parse_author_regex.match(raw).groups()

        def __str__(self):
            if not self.name:
                return self.raw
            if not self.email:
                return self.name

            return "{0} <{1}>".format(self.name, self.email)

    def __init__(self, path, options, renderer=None):
        """
        Load a file from disk, and parse the metadata from it.

        Note that you still need to call `render` and `write` to do anything
        interesting.
        """
        self.header = None
        self.original = None
        self.parsed = None
        self.options = options
        self.renderer = renderer if renderer else renderers.Plain
        self.subpages = []

        # TODO: It's not good to make a new environment every time, but we if
        # we pass the options in each time, its possible it will change per
        # instance. Fix this.
        self.tmpl_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(
                self.options.get('template_dir', 'templates')))

        self.path = path
        _, self.filename = os.path.split(path)

        with open(path) as f:
            self.original = f.read()
            # Maximum of one split, so --- in the content doesn't get split.
            splits = self.original.split('---', 1)

            # Handle the case where no meta data was provided
            if len(splits) == 1:
                self.original = splits[0]
            else:
                header = splits[0]
                self.original = splits[1]
                self.meta = yaml.load(header)

        self.build_meta()
        util.out.info('Page', 'Rendering {0} with {1}'.format(
            self.slug, self.renderer))
        self.content = self.renderer.render(self.original)

    def build_meta(self):
        """
        Ensures the guarantees about metadata for documents are valid.

        `page.title` - will exist and will be a string.
        `page.slug` - will exist and will be a string.
        `page.author` - will exist, and contain fields `name` and `email`.
        `page.category` - will be a list.
        `page.published` - will exist.
        `page.datetime` - will be a datetime.
        `page.tags` - will be a list.
        `page.url` - will be the url of the page, relative to the web root.
        """

        if self.meta is None:
            self.meta = {}

        if not 'title' in self.meta:
            self.meta['title'] = '.'.join(self.filename.split('.')[:-1])
            if (self.meta['title'] == ''):
                self.meta['title'] = self.filename

            util.out.warn('metadata',
                "You didn't specify a title in {0}."
                "Using the file name as a title." .format(self.filename))
        # Guarantee: title exists, will be a string.

        if not 'slug' in self.meta:
            self.meta['slug'] = util.slugify(self.meta['title'])
            util.out.debug('metadata',
                'You didn\'t specify a slug, generating it from the title.')
        elif self.meta['slug'] != util.slugify(self.meta['slug']):
            util.out.warn('metadata',
                'Your slug should probably be all lower case,' +
                'and match the regex "[a-z0-9-]*"')
        # Guarantee: slug exists, will be a string.

        if 'author' in self.meta:
            self.meta['author'] = Page.Author.parse(self.meta['author'])
        else:
            self.meta['author'] = Page.Author()
        # Guarantee: author exists, may be (None, None, None).

        if 'category' in self.meta:
            self.meta['category'] = self.meta['category'].split('/')
        else:
            self.meta['category'] = []
        if self.meta['category'] == None:
            self.meta = []
        # Guarantee: category exists, is a list

        if not 'published' in self.meta:
            self.meta['published'] = True
        # Guarantee: published exists, boolean

        for name in ['time', 'date']:
            if name in self.meta:
                self.meta['datetime'] = self.meta[name]
        if not 'datetime' in self.meta:
            self.meta['datetime'] = datetime.now()
        # Guarantee: datetime exists, is a datetime

        if not 'tags' in self.meta:
            self.meta['tags'] = []
        else:
            self.meta['tags'] = [t.strip() for t in
                    self.meta['tags'].split(',')]
        util.out.debug('page.tags', 'Tags for {0}: {1}'.
                format(self.slug, self.meta['tags']))
        # Guarantee: tags exists, is a list

        if not 'url' in self.meta:
            # /category/subcategory/slug.html
            util.out.debug('building the url', self.categories)
            self.meta['url'] = '/'
            for cat in self.category:
                self.meta['url']= os.path.join(self.meta['url'], cat)
            self.meta['url'] = os.path.join(self.meta['url'],
                    self.slug + '.html')

    def render(self, templ_vars=None):
        """
        Renders the page to full html with the template engine.
        """
        type = self.meta.get('type', 'default')
        template = self.tmpl_env.get_template(type + '.html')

        if not templ_vars:
            templ_vars = {}
        templ_vars.update({
            'page': self,
        })
        self.html = template.render(templ_vars)

    def write(self):
        """Write the page to an html file on disk."""

        # Use what we are passed, or the default given, or the current dir
        path = self.options.get('output_dir', '.')
        path += self.url

        try:
            os.makedirs(os.path.dirname(path))
        except OSError as e:
            util.out.debug('writing files', 'makedirs failed for {0}'.format(
                os.path.basename(path)))
            # Probably that the dir already exists, so thats ok.
            # TODO: double check this. Permission errors are something to worry
            # about

        f = open(path, 'w')
        f.write(self.html)
        f.close()

    # Make the public interface ignore the seperation between the meta
    # dictionary and the properies of the Page object.
    def __getattr__(self, name):
        if name in self.meta:
            return self.meta[name]

    def __repr__(self):
        return "&ltwok.page.Page '%s'&gt"%self.slug
